import logging

from spanreed.backend import get_backend
from spanreed.models import Message

logger = logging.getLogger(__name__)


def broadcast(message: Message) -> None:
    """
    Publishes a message to multiple consumers
    """
    get_backend().broadcast(message)
    logger.debug('Sent message', extra={'sent_message': message})


def publish(message: Message) -> None:
    """
    Publishes a message to a single consumer
    """
    get_backend().publish(message)
    logger.debug('Sent message', extra={'sent_message': message})
