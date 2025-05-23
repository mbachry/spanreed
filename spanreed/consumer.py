import logging

from spanreed.backend import get_backend
from spanreed.conf import settings
from spanreed.const import QueueType
from spanreed.exceptions import IgnoreException, RetryException
from spanreed.models import Message, run_message_handler

WAIT_TIME_SECONDS = 20

logger = logging.getLogger(__name__)


def message_handler(message: Message) -> None:
    try:
        logger.debug('received message', extra={'received_message': message})
        run_message_handler(message)
    except IgnoreException:
        logger.info(f'Ignoring task {message.metadata.id}')
        return
    except RetryException:
        # Retry without logging exception
        logger.info('Retrying due to exception')
        # let it bubble up so message ends up in DLQ
        raise
    except Exception:
        logger.exception('Exception while processing message')
        # let it bubble up so message ends up in DLQ
        raise


def fetch_and_process_messages(
    queue_type: QueueType,
    num_messages: int = 1,
    visibility_timeout: int | None = None,
) -> None:
    be = get_backend()

    for message in be.receive_messages(
        queue_type,
        num_messages=num_messages,
        wait_timeout_s=WAIT_TIME_SECONDS,
        visibility_timeout=visibility_timeout,
    ):
        settings.SPANREED_PRE_PROCESS_HOOK(message=message)

        try:
            message_handler(message)
            try:
                settings.SPANREED_POST_PROCESS_HOOK(message=message)
            except Exception:
                logger.exception('Exception in post process hook for message')
                raise
            try:
                be.ack(message.metadata)
            except Exception:
                logger.exception('Exception while acking message')
        except Exception:  # noqa: S110
            # already logged in message_handler
            pass


def listen_for_messages(
    num_messages: int = 1,
    visibility_timeout_s: int = None,
    queue_type: QueueType = QueueType.task,
) -> None:
    while True:
        fetch_and_process_messages(
            queue_type,
            num_messages=num_messages,
            visibility_timeout=visibility_timeout_s,
        )
