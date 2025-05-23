import pytest

import spanreed.conf
from spanreed.const import QueueType
from spanreed.models import message_from_data
from tests import tasks  # noqa: F401
from tests.factories import MessageFactory, TaskDataFactory


@pytest.fixture
def settings(monkeypatch):
    """
    Use this fixture to override settings. Changes are automatically reverted
    """

    class Wrapped:
        def __getattr__(self, key):
            return getattr(spanreed.conf.settings, key)

        def __setattr__(self, key, value):
            monkeypatch.setattr(spanreed.conf.settings, key, value)

    return Wrapped()


@pytest.fixture(name='message_data')
def _message_data():
    return MessageFactory.build(metadata__type='tests.models.UserCreated', metadata__queue_type=QueueType.message.name)


@pytest.fixture
def message(message_data):
    return message_from_data(message_data)


@pytest.fixture
def task_message():
    data = MessageFactory.build(
        metadata__type='_task_dispatched',
        metadata__queue_type=QueueType.task.name,
        data=TaskDataFactory(),
    )
    return message_from_data(data)


@pytest.fixture(autouse=True)
def clean_caches():
    from spanreed.backend import get_backend

    get_backend.cache_clear()
    spanreed.conf.user_settings.cache_clear()
