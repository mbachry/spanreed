import json
import logging
import typing
from dataclasses import dataclass
from functools import lru_cache

import walrus
from pydantic import ValidationError

from spanreed import task_manager
from spanreed.conf import settings
from spanreed.const import QueueType
from spanreed.exceptions import ConfigurationError
from spanreed.models import Message, Metadata, get_callbacks, message_from_data

logger = logging.getLogger(__name__)


DEFAULT_VISIBILITY_TIMEOUT_S = 30


@lru_cache
def get_redis_client() -> walrus.Walrus:
    return walrus.Walrus.from_url(str(settings.SPANREED_REDIS_URL))


def get_task_queue_name(task: task_manager.Task) -> str:
    normalized = task.name.replace('.', '-')
    name = f'spanreed-{settings.SPANREED_QUEUE}-{normalized}'
    if task.queue_type is QueueType.task:
        name += '-default'
    elif task.queue_type is QueueType.task_high:
        name += '-high-priority'
    elif task.queue_type is QueueType.task_low:
        name += '-low-priority'
    elif task.queue_type is QueueType.task_bulk:
        name += '-bulk'
    else:
        raise AssertionError(f'invalid queue_type: {task.queue_type}')
    return name


def get_stream(message: Message) -> walrus.Stream:
    if message.metadata.queue_type == QueueType.message:
        topic = f'spanreed-{message.data.message_topic}'
    else:
        task = task_manager.find_by_name(message.data.task)
        topic = get_task_queue_name(task)
    db = get_redis_client()
    return db.Stream(topic)


def get_dlq_stream(topic: str) -> walrus.Stream:
    db = get_redis_client()
    return db.Stream(f'{topic}-dlq')


@lru_cache
def get_all_task_topics(queue_type: QueueType) -> list[str]:
    return [get_task_queue_name(t) for t in task_manager.find_by_queue_type(queue_type)]


@lru_cache
def get_topic_visibility_timeout_s(topic: str, default: int) -> int:
    vis = {get_task_queue_name(t): t.visibility_timeout_s for t in task_manager.ALL_TASKS.values()}
    timeout = vis.get(topic, default)
    if timeout is None:
        timeout = default
    return timeout


@lru_cache
def get_topics(queue_type: QueueType) -> list[str]:
    if queue_type == QueueType.message:
        topics = ['spanreed-' + model.message_topic for model in get_callbacks().values()]
    else:
        topics = get_all_task_topics(queue_type)
    return list(set(topics))


@lru_cache
def get_consumer_group(queue_type: QueueType) -> walrus.ConsumerGroup:
    topics = get_topics(queue_type)
    if not topics:
        raise ConfigurationError(f'no topics to listen to for queue {queue_type}')
    db = get_redis_client()
    cg = db.consumer_group(settings.SPANREED_PUBLISHER, topics)
    cg.create()
    return cg


def get_consumer_group_stream(cg: walrus.ConsumerGroup, stream_name: str) -> walrus.containers.ConsumerGroupStream:
    stream_attr = stream_name.lower().replace('-', '_')
    return getattr(cg, stream_attr)


@dataclass
class MessageHandle:
    id: str
    stream_name: str
    consumer_group: walrus.ConsumerGroup


class RedisBackend:
    def broadcast(self, message: Message) -> None:
        payload = message.model_dump_json()
        stream = get_stream(message)
        stream.add({'message': payload})

    def publish(self, message: Message) -> None:
        self.broadcast(message)

    def receive_messages(
        self,
        queue_type: QueueType,
        num_messages: int,
        wait_timeout_s: int,
        visibility_timeout: int | None,
    ) -> typing.Generator[Message, None, None]:
        # in redis zero block timeout == forever. pick a very small
        # value to have consistent behavior with other backends
        # (ie. wait_timeout_s == no wait)
        block_timeout = wait_timeout_s * 1000 if wait_timeout_s else 1
        if visibility_timeout is None:
            visibility_timeout = DEFAULT_VISIBILITY_TIMEOUT_S

        cg = get_consumer_group(queue_type)

        for stream_name, results in self._receive_unacked_messages(cg, queue_type, num_messages, visibility_timeout):
            yield from self._process_messages(cg, stream_name, results)
            if results:
                # override block_timeout so we keep looping and clearing
                # pending queue without pauses
                block_timeout = 1

        for stream_name, results in cg.read(count=num_messages, block=block_timeout):
            stream_name = stream_name.decode()
            yield from self._process_messages(cg, stream_name, results)

    def ack(self, metadata: Metadata):
        handle = metadata._backend_handle
        assert handle is not None
        stream = get_consumer_group_stream(handle.consumer_group, handle.stream_name)
        stream.ack(handle.id)

    def _process_messages(self, cg: walrus.ConsumerGroup, stream_name: str, results: list):
        for msg_id, payload in results:
            payload = payload[b'message']
            try:
                message_body = json.loads(payload)
                handle = MessageHandle(id=msg_id, stream_name=stream_name, consumer_group=cg)
                message = message_from_data(message_body)
                message.metadata._backend_handle = handle
                yield message
            except (ValidationError, ValueError):
                logger.warning('Received invalid message', extra={'message_body': payload})

    def _receive_unacked_messages(
        self, cg: walrus.ConsumerGroup, queue_type: QueueType, num_messages: int, visibility_timeout: int
    ):
        for stream_name in get_topics(queue_type):
            stream = get_consumer_group_stream(cg, stream_name)

            pending_ids = []
            dlq_ids = []
            for pending in stream.pending(count=num_messages):
                message_id = pending['message_id']
                if pending['times_delivered'] > settings.SPANREED_REDIS_DLQ_MAX_UNACKED:
                    dlq_ids.append(message_id)
                else:
                    pending_ids.append(message_id)

            if pending_ids:
                vis = get_topic_visibility_timeout_s(stream_name, visibility_timeout)
                results = stream.claim(*pending_ids, min_idle_time=vis * 1000)
                yield stream_name, results

            if dlq_ids:
                dlq_stream = get_dlq_stream(stream_name)
                for msg_id, payload in stream.claim(*dlq_ids):
                    dlq_stream.add(payload)
                    # we have to both ack and delete (to remove from
                    # both consumer group and actual stream)
                    stream.ack(msg_id)
                    stream.delete(msg_id)

    def requeue_dead_letter(
        self, queue_type: QueueType, num_messages: int = 10, visibility_timeout: int = None
    ) -> None:
        db = get_redis_client()

        for stream_name in get_topics(queue_type):
            stream = db.Stream(stream_name)
            dlq_stream = get_dlq_stream(stream_name)
            logging.info(f'Re-queueing messages from {dlq_stream.key} to {stream.key}')

            while True:
                messages = dlq_stream.read(count=num_messages)
                if not messages:
                    break

                logging.info(f'got {len(messages)} messages from dlq')

                for msg_id, message in messages:
                    stream.add(message)
                    dlq_stream.delete(msg_id)

                logging.info(f'Re-queued {len(messages)} messages')
