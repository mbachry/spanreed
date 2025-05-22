from unittest import mock

import django
import pytest

from spanreed.conf import settings, user_settings
from spanreed.const import QueueType


@pytest.fixture(autouse=True)
def django_settings(monkeypatch):
    monkeypatch.setenv('DJANGO_SETTINGS_MODULE', 'tests.django_settings')
    user_settings.cache_clear()


def test_settings_from_django():
    assert settings.SPANREED_QUEUE == 'DJANGO-DEV-MYAPP'
    assert settings.SPANREED_PUBLISHER == 'django-myapp'


@mock.patch('spanreed.consumer.fetch_and_process_messages', autospec=True)
def test_worker_management_command(mock_fetch_and_process):
    django.setup()
    mock_fetch_and_process.side_effect = [None, RuntimeError]
    with pytest.raises(RuntimeError):
        django.core.management.call_command('spanreed_worker', '--queue-type', 'task')

    assert mock_fetch_and_process.call_count == 2
    mock_fetch_and_process.assert_has_calls([mock.call(QueueType.task, num_messages=10, visibility_timeout=None)])
