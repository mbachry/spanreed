import time
import uuid

import factory

from spanreed.conf import settings
from spanreed.const import QueueType
from spanreed.models import Message, message_from_data


class HeadersFactory(factory.DictFactory):
    request_id = factory.Faker('uuid4')


class MetadataFactory(factory.DictFactory):
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    type = 'tests.models.UserCreated'
    timestamp = factory.LazyFunction(lambda: int(time.time() * 1000))
    publisher = settings.SPANREED_PUBLISHER
    headers = factory.SubFactory(HeadersFactory)
    queue_type = QueueType.message.name
    visibility_timeout_s = None


class DataFactory(factory.DictFactory):
    user_id = '1234567890123456'
    booking_id = 'abcdef00abcdef00abcdef00'
    city = '00000000000000000'
    address_id = '1234567890123456'


class TaskDataFactory(factory.DictFactory):
    message_type = '_task_dispatched'
    task = 'tests.tasks.send_email'
    args = ['example@email.com', 'Hello!']
    kwargs = {'from_email': 'hello@spammer.com'}


class MessageFactory(factory.DictFactory):
    metadata = factory.SubFactory(MetadataFactory)
    data = factory.SubFactory(DataFactory)

    @classmethod
    def _create(cls, model_class: Message, *args, **kwargs) -> Message:
        return message_from_data(cls._build(model_class, *args, **kwargs))
