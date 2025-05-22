import enum


class QueueType(enum.Enum):
    """
    Task priority. This may be used to differentiate batch jobs from other tasks for example.
    """

    message = 'message'
    task = 'task'
    task_high = 'task_high'
    task_low = 'task_low'
    task_bulk = 'task_bulk'


def default_headers_hook(*args, **kwargs) -> dict[str, str]:
    return {}


def noop_hook(*args, **kwargs) -> None:
    pass
