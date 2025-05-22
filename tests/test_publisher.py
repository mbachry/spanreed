from unittest import mock

from spanreed.publisher import broadcast, publish


@mock.patch('spanreed.publisher.get_backend', autospec=True)
def test_broadcast(mock_be, message):
    broadcast(message)
    mock_be.return_value.broadcast.assert_called_once_with(message)


@mock.patch('spanreed.publisher.get_backend', autospec=True)
def test_publish(mock_be, message):
    publish(message)
    mock_be.return_value.publish.assert_called_once_with(message)
