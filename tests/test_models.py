import time
import uuid
from unittest import mock

import pytest
from pydantic import ValidationError

from spanreed.conf import settings
from spanreed.const import QueueType
from spanreed.models import Metadata, message_from_data
from tests.factories import MetadataFactory
from tests.models import UserCreated


class TestMetadata:
    def test_new(self):
        data = MetadataFactory(type='tests.models.UserCreated')
        data['queue_type'] = QueueType[data['queue_type']]
        metadata = Metadata(**data)
        assert metadata.timestamp == data['timestamp']
        assert metadata.headers == data['headers']
        assert metadata.publisher == data['publisher']


class TestMessageMethods:
    publisher = 'myapi'

    def test_constructor(self):
        message_data = {
            'metadata': {
                'id': str(uuid.uuid4()),
                'type': 'tests.models.UserCreated',
                'timestamp': 1460868253255,
                'publisher': 'myapp',
                'headers': {'request_id': str(uuid.uuid4())},
                'queue_type': QueueType.message.name,
                'backend_handle': None,
                'visibility_timeout_s': None,
            },
            'data': {
                'address_id': '1234567890123456',
                'user_id': '1234567890123456',
                'booking_id': 'id',
                'city': 'foo',
            },
        }

        message = message_from_data(message_data)
        assert message.metadata == Metadata(**{**message_data['metadata'], 'queue_type': QueueType.message})
        assert message.data == UserCreated(**message_data['data'])

    @mock.patch('spanreed.models.time.time', autospec=True)
    def test_metadata_new(self, mock_time, message_data):
        mock_time.return_value = time.time()

        metadata = Metadata(
            type='tests.models.UserCreated',
            id=message_data['metadata']['id'],
            headers=message_data['metadata']['headers'],
        )

        assert metadata.id == message_data['metadata']['id']
        assert metadata.headers == message_data['metadata']['headers']
        assert metadata.timestamp == int(mock_time.return_value * 1000)
        assert metadata.publisher == settings.SPANREED_PUBLISHER
        assert metadata.queue_type == QueueType.message

    @pytest.mark.parametrize('missing_data', ['metadata', 'data'])
    def test_validate_missing_data(self, missing_data, message_data):
        message_data[missing_data] = None

        with pytest.raises(ValidationError):
            message_from_data(message_data)


def default_headers_hook():
    return {'mickey': 'mouse'}


def test_default_headers_hook(message_data, settings):
    settings.SPANREED_DEFAULT_HEADERS = default_headers_hook

    message = message_from_data(message_data)

    assert 'mickey' in message.metadata.headers
    assert message.metadata.headers['mickey'] == 'mouse'
