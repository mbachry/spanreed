import inspect
import time
import typing
import uuid
from functools import cache

from pydantic import BaseModel, Field, PrivateAttr, ValidationError

from spanreed.conf import settings
from spanreed.const import QueueType
from spanreed.exceptions import ConfigurationError


class BaseMessage(BaseModel):
    message_topic: typing.ClassVar[str] = 'message'

    @classmethod
    def get_message_type(cls):
        return f'{cls.__module__}.{cls.__name__}'

    def publish(self):
        """
        Publishes a message to multiple consumers
        """
        from spanreed.publisher import broadcast

        metadata = Metadata(type=self.get_message_type(), queue_type=QueueType.message)
        message = Message(data=self, metadata=metadata)
        broadcast(message)


class Metadata(BaseModel):
    type: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    publisher: str = Field(default_factory=lambda: settings.SPANREED_PUBLISHER)
    headers: dict = Field(default_factory=lambda: settings.SPANREED_DEFAULT_HEADERS())
    queue_type: QueueType = QueueType.message
    visibility_timeout_s: int | None = None
    _backend_handle: object | None = PrivateAttr()


class Message[DataType](BaseModel):
    data: DataType
    metadata: Metadata


def run_message_handler(message: Message):
    kwargs = {}
    param_name = accepts_metadata_param(message.data.handle)
    if param_name:
        kwargs[param_name] = message.metadata
    message.data.handle(**kwargs)


def message_from_data(data: dict) -> Message:
    meta = data.get('metadata')
    if not meta:
        raise ValidationError('missing_metadata', [])

    headers = {**settings.SPANREED_DEFAULT_HEADERS(), **meta['headers']}
    meta['headers'] = headers

    cls = get_message_model(meta['type'])
    return Message[cls].model_validate(data)


def get_message_model(msg_type: str) -> BaseModel:
    from spanreed import task_manager

    if msg_type == '_task_dispatched':
        return task_manager.TaskDispatch
    model_class = get_callbacks().get(msg_type)
    if not model_class:
        raise ConfigurationError(f'callback not found for {msg_type}')
    return model_class


@cache
def get_callbacks():
    callbacks = {m.get_message_type(): m for m in settings.SPANREED_MODELS}
    assert len(callbacks) == len(settings.SPANREED_MODELS)
    return callbacks


@cache
def accepts_metadata_param(func) -> str:
    signature = inspect.signature(func)
    for p in signature.parameters.values():
        # if **kwargs is specified, just pass all things by default
        # since function can always inspect arg names
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            return 'metadata'
        if p.annotation is Metadata:
            return p.name
    return None
