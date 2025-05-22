from spanreed.models import BaseMessage, Metadata


def _user_created_handler(data, metadata):
    print('got message', data, metadata)


class UserCreated(BaseMessage):
    message_topic = 'dev-user-created'
    user_id: str
    booking_id: str
    city: str
    address_id: str

    def handle(self, meta: Metadata):
        _user_created_handler(self, meta)


class UserCreatedV2(UserCreated):
    pass


def booking_handler(message):
    pass


class BookingCreated(BaseMessage):
    def handle(self):
        booking_handler(self)
