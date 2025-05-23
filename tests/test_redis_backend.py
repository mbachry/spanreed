import json

import pytest

from spanreed.backend.redis import (
    RedisBackend,
    get_consumer_group,
    get_consumer_group_stream,
    get_dlq_stream,
    get_stream,
)
from spanreed.const import QueueType
from spanreed.models import message_from_data
from spanreed.publisher import publish


@pytest.fixture(autouse=True)
def redis_setup(redisdb, redis_proc, settings):
    from spanreed.backend.redis import get_redis_client

    settings.SPANREED_REDIS_URL = f'redis://{redis_proc.host}:{redis_proc.port}'
    get_redis_client.cache_clear()
    get_consumer_group.cache_clear()


@pytest.mark.parametrize('func_name', ('broadcast', 'publish'))
def test_broadcast_and_publish(message, func_name):
    be = RedisBackend()
    func = getattr(be, func_name)
    func(message)

    stream = get_stream(message)
    messages = stream.read(block=1000)
    assert len(messages) == 1
    data = json.loads(messages[0][1][b'message'])

    assert message_from_data(data) == message


@pytest.mark.parametrize(
    'task_name,queue_type',
    (
        ('tests.tasks.send_email', QueueType.task),
        ('tests.tasks.send_email_low', QueueType.task_low),
        ('tests.tasks.send_email_high', QueueType.task_high),
        ('tests.tasks.send_email_bulk', QueueType.task_bulk),
    ),
)
def test_publish_task(task_message, task_name, queue_type):
    be = RedisBackend()
    task_message.data.task = task_name
    be.publish(task_message)

    received_messages = list(be.receive_messages(queue_type, 1, wait_timeout_s=0, visibility_timeout=5))
    assert len(received_messages) == 1

    assert received_messages[0].data == task_message.data


def test_receive_messages(message):
    be = RedisBackend()
    num_messages = 3

    for _ in range(num_messages):
        message.data.publish()

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, num_messages, wait_timeout_s=0, visibility_timeout=5),
    )

    assert [m.data.model_dump_json() for m in received_messages] == [message.data.model_dump_json()] * num_messages

    cg = get_consumer_group(message.metadata.queue_type)
    cg_stream = get_consumer_group_stream(cg, get_stream(message).key)
    assert len(cg_stream.pending()) == 3

    assert not list(
        be.receive_messages(message.metadata.queue_type, num_messages, wait_timeout_s=0, visibility_timeout=5),
    )


def test_receive_messages_task(task_message):
    be = RedisBackend()
    num_messages = 3

    for _ in range(num_messages):
        publish(task_message)

    received_messages = list(
        be.receive_messages(task_message.metadata.queue_type, num_messages, wait_timeout_s=0, visibility_timeout=0),
    )

    assert [m.model_dump_json() for m in received_messages] == [task_message.model_dump_json()] * num_messages

    cg = get_consumer_group(task_message.metadata.queue_type)
    cg_stream = get_consumer_group_stream(cg, get_stream(task_message).key)
    assert len(cg_stream.pending()) == 3


def test_receive_messages_bad_json(message):
    be = RedisBackend()
    stream = get_stream(message)
    stream.add({'message': 'foo'})

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
    )
    assert not received_messages

    cg = get_consumer_group(message.metadata.queue_type)
    cg_stream = get_consumer_group_stream(cg, get_stream(message).key)
    assert len(cg_stream.pending()) == 1


def test_receive_messages_bad_data(message):
    be = RedisBackend()

    stream = get_stream(message)
    message.metadata.id = None
    stream.add({'message': message.model_dump_json()})

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
    )
    assert not received_messages

    cg = get_consumer_group(message.metadata.queue_type)
    cg_stream = get_consumer_group_stream(cg, get_stream(message).key)
    assert len(cg_stream.pending()) == 1


def test_ack(message):
    be = RedisBackend()
    message.data.publish()

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
    )
    assert len(received_messages) == 1

    be.ack(received_messages[0].metadata)

    cg = get_consumer_group(message.metadata.queue_type)
    cg_stream = get_consumer_group_stream(cg, get_stream(message).key)
    assert len(cg_stream.pending()) == 0


def test_visibility_timeout_default(message):
    be = RedisBackend()
    message.data.publish()

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
    )
    assert len(received_messages) == 1

    # should be visible again immediately
    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
    )
    assert len(received_messages) == 1


def test_visibility_timeout_custom(task_message):
    be = RedisBackend()
    task_message.data.task = 'tests.tasks.send_email_visibility'
    publish(task_message)

    received_messages = list(
        be.receive_messages(task_message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=None),
    )
    assert len(received_messages) == 1

    # should be visible again immediately
    received_messages = list(
        be.receive_messages(task_message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=None),
    )
    assert len(received_messages) == 1


def test_dlq(message, settings):
    settings.SPANREED_REDIS_DLQ_MAX_UNACKED = 2

    be = RedisBackend()
    message.data.publish()

    stream = get_stream(message)
    dlq_stream = get_dlq_stream(stream.key)

    for _ in range(settings.SPANREED_REDIS_DLQ_MAX_UNACKED + 1):
        received_messages = list(
            be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
        )
        assert len(received_messages) == 1
        assert len(dlq_stream) == 0

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=0),
    )
    assert len(received_messages) == 0
    assert len(dlq_stream) == 1
    dlq_message = json.loads(dlq_stream.read(count=1)[0][1][b'message'])
    assert message_from_data(dlq_message).data == message.data


def test_requeue_dead_letter(message):
    be = RedisBackend()

    stream = get_stream(message)
    dlq_stream = get_dlq_stream(stream.key)
    dlq_stream.add({'message': message.model_dump_json()})

    be.requeue_dead_letter(message.metadata.queue_type)

    assert len(dlq_stream) == 0

    received_messages = list(
        be.receive_messages(message.metadata.queue_type, 1, wait_timeout_s=0, visibility_timeout=None),
    )
    assert len(received_messages) == 1

    assert received_messages[0].data == message.data
