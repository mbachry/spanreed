import typing

from pydantic import BaseModel

from spanreed.const import QueueType
from spanreed.exceptions import ConfigurationError
from spanreed.models import BaseMessage, Message, Metadata, accepts_metadata_param
from spanreed.publisher import publish

ALL_TASKS: dict = {}


class TaskDispatch(BaseMessage):
    task: str
    args: list
    kwargs: dict

    def handle(self, metadata: Metadata):
        task = find_by_name(self.task)
        task.call(self, metadata)


class Task(BaseModel):
    fn: typing.Callable
    name: str
    queue_type: QueueType
    visibility_timeout_s: int | None

    def dispatch(self, *args, **kwargs) -> None:
        meta = Metadata(
            type='_task_dispatched',
            queue_type=self.queue_type,
            visibility_timeout_s=self.visibility_timeout_s,
        )
        message = Message(data=TaskDispatch(task=self.name, args=args, kwargs=kwargs), metadata=meta)
        publish(message)

    def call(self, data: TaskDispatch, metadata: Metadata) -> None:
        args = data.args
        kwargs = data.kwargs
        extra = {'metadata': metadata} if accepts_metadata_param(self.fn) else {}
        self.fn(*args, **kwargs, **extra)


def find_by_name(name: str) -> Task:
    task = ALL_TASKS.get(name)
    if task is None:
        raise ConfigurationError(f'task not found: {name}')
    return task


def find_by_queue_type(queue_type: QueueType) -> list[Task]:
    return [t for t in ALL_TASKS.values() if t.queue_type == queue_type]


def task(
    *args,
    queue_type: QueueType = QueueType.task,
    name: str = None,
    visibility_timeout_s: int = None,
) -> typing.Callable:
    from spanreed.conf import settings
    from spanreed.task_manager import ALL_TASKS

    def _decorator(fn: typing.Callable) -> typing.Callable:
        task_name = name or f'{fn.__module__}.{fn.__name__}'
        existing_task = ALL_TASKS.get(task_name)
        if existing_task is not None:
            func = existing_task.fn
            raise ConfigurationError(f'Task named "{task_name}" already exists: {func.__module__}.{func.__name__}')

        fn.task = settings.SPANREED_TASK_CLASS(
            fn=fn,
            name=task_name,
            queue_type=queue_type,
            visibility_timeout_s=visibility_timeout_s,
        )
        fn.dispatch = fn.task.dispatch
        ALL_TASKS[fn.task.name] = fn.task
        return fn

    if len(args) == 1 and callable(args[0]):
        # No arguments, this is the decorator
        return _decorator(args[0])

    return _decorator
