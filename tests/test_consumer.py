from unittest import mock

import pytest

from spanreed import consumer
from spanreed.backend import get_backend
from spanreed.const import QueueType
from spanreed.consumer import fetch_and_process_messages, listen_for_messages, message_handler
from spanreed.exceptions import ConfigurationError, IgnoreException, RetryException


@mock.patch('tests.models._user_created_handler', autospec=True)
def test_handle_message(mock_handler, message):
    message_handler(message)
    mock_handler.assert_called_once_with(message.data, message.metadata)


@mock.patch('tests.tasks._send_email', autospec=True)
def test_handle_task(mock_task, task_message):
    message_handler(task_message)
    mock_task.assert_called_once_with(
        *task_message.data.args,
        **task_message.data.kwargs,
        metadata=task_message.metadata,
    )


@mock.patch('tests.models._user_created_handler', autospec=True)
class TestMessageHandler:
    def test_success(self, mock_call_task, message):
        message_handler(message)
        mock_call_task.assert_called_once_with(message.data, message.metadata)

    def test_fails_on_task_failure(self, mock_call_task, message):
        mock_call_task.side_effect = Exception
        with pytest.raises(mock_call_task.side_effect):
            message_handler(message)

    def test_special_handling_retry_error(self, mock_call_task, message):
        mock_call_task.side_effect = RetryException
        with pytest.raises(mock_call_task.side_effect), mock.patch.object(consumer.logger, 'info') as logging_mock:
            message_handler(message)
        logging_mock.assert_called_once()

    def test_special_handling_ignore_exception(self, mock_call_task, message):
        mock_call_task.side_effect = IgnoreException
        # no exception raised
        with mock.patch.object(consumer.logger, 'info') as logging_mock:
            message_handler(message)

            logging_mock.assert_called_once()

    def test_validate_missing_callback(self, mock_call_task, message):
        mock_call_task.side_effect = ConfigurationError
        with pytest.raises(ConfigurationError):
            message_handler(message)


pre_process_hook = mock.MagicMock()
post_process_hook = mock.MagicMock()
post_deserialize_hook = mock.MagicMock()


@mock.patch('spanreed.consumer.message_handler', autospec=True)
class TestFetchAndProcessMessages:
    def test_success(self, mock_message_handler):
        be = get_backend()
        queue = mock.MagicMock()
        num_messages = 3
        visibility_timeout = 4

        with mock.patch.object(be, 'receive_messages') as mock_get_messages, mock.patch.object(be, 'ack') as mock_ack:
            mock_get_messages.return_value = [mock.MagicMock(), mock.MagicMock()]
            fetch_and_process_messages(queue, num_messages, visibility_timeout)

            mock_message_handler.assert_has_calls([mock.call(x) for x in mock_get_messages.return_value])
            for message in mock_get_messages.return_value:
                mock_ack.assert_has_calls(message)

    def test_preserves_messages(self, mock_message_handler):
        be = get_backend()
        queue_name = 'my-queue'
        queue = mock.MagicMock()

        mock_message_handler.side_effect = Exception

        with mock.patch.object(be, 'receive_messages') as mock_get_messages, mock.patch.object(be, 'ack') as mock_ack:
            mock_get_messages.return_value = [mock.MagicMock()]
            fetch_and_process_messages(queue_name, queue)
            mock_ack.assert_not_called()

    def test_ignore_delete_error(self, mock_message_handler):
        be = get_backend()
        queue_name = 'my-queue'
        queue = mock.MagicMock()

        with mock.patch.object(be, 'receive_messages') as mock_get_messages, mock.patch.object(be, 'ack') as mock_ack:
            mock_get_messages.return_value = [mock.MagicMock()]
            mock_ack.side_effect = Exception

            with mock.patch.object(consumer.logger, 'exception') as logging_mock:
                fetch_and_process_messages(queue_name, queue)
                logging_mock.assert_called_once()

            mock_ack.assert_has_calls(mock_get_messages.return_value[0])

    def test_pre_process_hook(self, mock_message_handler, settings):
        be = get_backend()
        queue_name = 'my-queue'
        queue = mock.MagicMock()
        settings.SPANREED_PRE_PROCESS_HOOK = pre_process_hook

        with mock.patch.object(be, 'receive_messages') as mock_get_messages:
            mock_get_messages.return_value = [mock.MagicMock(), mock.MagicMock()]
            fetch_and_process_messages(queue_name, queue)

        pre_process_hook.assert_has_calls([mock.call(message=x) for x in mock_get_messages.return_value])

    def test_post_process_hook(self, mock_message_handler, settings):
        be = get_backend()
        queue_name = 'my-queue'
        queue = mock.MagicMock()
        settings.SPANREED_POST_PROCESS_HOOK = post_process_hook

        with mock.patch.object(be, 'receive_messages') as mock_get_messages:
            mock_get_messages.return_value = [mock.MagicMock(), mock.MagicMock()]
            fetch_and_process_messages(queue_name, queue)

        post_process_hook.assert_has_calls([mock.call(message=x) for x in mock_get_messages.return_value])

    def test_post_process_hook_exception_raised(self, mock_message_handler, settings):
        be = get_backend()
        queue_name = 'my-queue'
        queue = mock.MagicMock()
        settings.SPANREED_POST_PROCESS_HOOK = post_process_hook

        with mock.patch.object(be, 'receive_messages') as mock_get_messages, mock.patch.object(be, 'ack') as mock_ack:
            mock_message = mock.MagicMock()
            mock_get_messages.return_value = [mock_message]

            post_process_hook.reset_mock()
            post_process_hook.side_effect = RuntimeError('fail')

            fetch_and_process_messages(queue_name, queue)

        post_process_hook.assert_called_once_with(message=mock_message)
        mock_ack.assert_not_called()


@mock.patch('spanreed.backend.redis.RedisBackend', autospec=True)
@mock.patch('spanreed.consumer.fetch_and_process_messages', autospec=True)
class TestListenForMessages:
    def test_listen_for_messages(self, mock_fetch_and_process, mock_be):
        mock_fetch_and_process.side_effect = [None, RuntimeError]

        num_messages = 3
        visibility_timeout_s = 4

        with pytest.raises(RuntimeError):
            listen_for_messages(num_messages, visibility_timeout_s)

        assert mock_fetch_and_process.call_count == 2
        mock_fetch_and_process.assert_has_calls(
            [mock.call(QueueType.task, num_messages=num_messages, visibility_timeout=visibility_timeout_s)],
        )
