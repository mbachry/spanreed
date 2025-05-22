from unittest import mock

import pytest

from spanreed import task
from spanreed.const import QueueType
from spanreed.exceptions import ConfigurationError
from spanreed.models import Metadata
from spanreed.task_manager import ALL_TASKS, Task, TaskDispatch, find_by_name
from tests.tasks import send_email


def test_task_decorator():
    @task
    def f():
        pass

    assert f.task.name == 'tests.test_task_manager.f'
    assert callable(f.dispatch)
    assert 'tests.test_task_manager.f' in ALL_TASKS


def test_task_decorator_custom_name():
    @task(name='foo')
    def f():
        pass

    assert f.task.name == 'foo'
    assert 'foo' in ALL_TASKS


def test_task_decorator_custom_name_conflict():
    def make_tasks():
        @task(name='foo')
        def f():
            pass

        @task(name='foo')
        def g():
            pass

    with pytest.raises(ConfigurationError):
        make_tasks()


def test_task_decorator_queue_type():
    @task(queue_type=QueueType.task_high, name='test_task_decorator_queue_type')
    def f():
        pass

    assert f.task.queue_type == QueueType.task_high
    assert callable(f.dispatch)
    assert 'test_task_decorator_queue_type' in ALL_TASKS


def test_task_decorator_visibility():
    @task(name='test_task_decorator_visibility', visibility_timeout_s=10)
    def f():
        pass

    assert callable(f.dispatch)
    t = ALL_TASKS.get('test_task_decorator_visibility')
    assert t is not None
    assert t.visibility_timeout_s == 10


class CustomTask(Task):
    pass


def test_task_decorator_custom_task_class(settings):
    settings.SPANREED_TASK_CLASS = CustomTask

    @task(name='test_task_decorator_custom_task_class')
    def f():
        pass

    assert isinstance(f.task, CustomTask)


def default_headers() -> dict:
    return {'request_id': 'mockuuid'}


@mock.patch('spanreed.task_manager.publish', autospec=True)
def test_async_invocation_dispatch(mock_publish, message):
    @task
    def f_test_dispatch(from_email, subject, **kwargs):
        pass

    args = ('example@email.com', 'Hello!')
    kwargs = {'from_email': 'example@spammer.com'}

    f_test_dispatch.dispatch('example@email.com', 'Hello!', from_email='example@spammer.com')

    assert mock_publish.call_count == 1
    message = mock_publish.call_args.args[0]
    assert message.data == TaskDispatch(task=f_test_dispatch.task.name, args=args, kwargs=kwargs)
    assert message.metadata.type == '_task_dispatched'
    assert message.metadata.queue_type == QueueType.task
    assert message.metadata.visibility_timeout_s is None


@mock.patch('spanreed.task_manager.publish', autospec=True)
def test_async_invocation_dispatch_custom_queue_type(mock_publish):
    @task(queue_type=QueueType.task_high)
    def f_custom_qt(from_email, subject, **kwargs):
        pass

    args = ('example@email.com', 'Hello!')
    kwargs = {'from_email': 'example@spammer.com'}

    f_custom_qt.dispatch('example@email.com', 'Hello!', from_email='example@spammer.com')

    assert mock_publish.call_count == 1
    message = mock_publish.call_args.args[0]
    assert message.data == TaskDispatch(task=f_custom_qt.task.name, args=args, kwargs=kwargs)
    assert message.metadata.type == '_task_dispatched'
    assert message.metadata.queue_type == QueueType.task_high
    assert message.metadata.visibility_timeout_s is None


@mock.patch('spanreed.task_manager.publish', autospec=True)
def test_async_invocation_dispatch_default_headers(mock_publish, settings):
    @task
    def f_headers(from_email, subject, **kwargs):
        pass

    settings.SPANREED_DEFAULT_HEADERS = default_headers

    f_headers.dispatch('example@email.com', 'Hello!', from_email='example@spammer.com')

    mock_publish.assert_called_once()
    msg = mock_publish.call_args[0][0]
    assert msg.metadata.headers == {'request_id': 'mockuuid'}


class TestTask:
    @staticmethod
    def f(a, b, c=1):
        pass

    @mock.patch('spanreed.task_manager.publish', autospec=True)
    def test_dispatch(self, mock_publish):
        task_obj = Task(fn=TestTask.f, name='name', queue_type=QueueType.task, visibility_timeout_s=None)
        task_obj.dispatch(1, 2)
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][0].data.args == [1, 2]

    def test_call(self, task_message):
        _f = mock.MagicMock()

        @task(name='test_call')
        def f(to: str, subject: str, from_email: str = None):
            _f(to, subject, from_email=from_email)

        task_obj = f.task
        task_obj.call(task_message.data, task_message.metadata)
        _f.assert_called_once_with(*task_message.data.args, **task_message.data.kwargs)

    def test_call_message(self, task_message):
        _f = mock.MagicMock()

        @task(name='test_call_metadata')
        def f(to: str, subject: str, metadata: Metadata = None, from_email: str = None):
            _f(to, subject, metadata, from_email=from_email)

        task_obj = f.task
        task_obj.call(task_message.data, task_message.metadata)
        _f.assert_called_once_with(*task_message.data.args, task_message.metadata, **task_message.data.kwargs)

    def test_find_by_name(self):
        assert find_by_name('tests.tasks.send_email') == send_email.task

    def test_find_by_name_fail(self):
        with pytest.raises(ConfigurationError):
            find_by_name('invalid')
