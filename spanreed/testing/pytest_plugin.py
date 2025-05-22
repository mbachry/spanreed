import pprint
from collections.abc import Generator
from unittest import mock

import pytest
from pydantic import BaseModel

__all__ = ['mock_spanreed_publish']


class AnyModel(dict):
    """An object equal to any pydantic model."""

    def __eq__(self, other):
        return isinstance(other, BaseModel)

    def __repr__(self):
        return f'{type(self).__name__}()'


class SpanreedPublishMock(mock.MagicMock):
    def _message_published(self, msg_type, data: dict | None) -> bool:
        return any(msg.metadata.type == msg_type and msg.data == data for (msg,), _ in self.call_args_list)

    def _error_message(self) -> str:
        return pprint.pformat([(msg.metadata.type, msg.data) for (msg,), _ in self.call_args_list])

    def assert_message_published(self, msg_type, data: dict | None = None) -> None:
        """
        Helper function to check if a message with given type, data
        and schema version was sent.
        """
        data = data or AnyModel()
        assert self._message_published(msg_type, data), self._error_message()

    def assert_message_not_published(self, msg_type, data: dict | None = None) -> None:
        """
        Helper function to check that a message of given type, data
        and schema was NOT sent.
        """
        data = data or AnyModel()
        assert not self._message_published(msg_type, data), self._error_message()


@pytest.fixture()
def mock_spanreed_publish() -> Generator[SpanreedPublishMock, None, None]:
    """
    A pytest fixture that mocks publisher and lets you verify that your test publishes appropriate messages.
    """
    from spanreed.publisher import broadcast

    with (
        mock.patch('spanreed.publisher.broadcast', wraps=broadcast, new_callable=SpanreedPublishMock) as mock_publish,
        mock.patch('spanreed.backend.redis.RedisBackend.broadcast'),
    ):
        yield mock_publish
