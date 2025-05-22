import logging

import spanreed
from spanreed.const import QueueType
from spanreed.models import Metadata


def _send_email(to: str, subject: str, from_email: str = None, metadata: Metadata = None) -> None:
    # inner fn to help w mocking
    pass


@spanreed.task
def send_email(to: str, subject: str, from_email: str = None, metadata: Metadata = None) -> None:
    headers = metadata.headers
    logging.info(f"Going to send email for request: {headers['request_id']} with id: {metadata.id}")
    _send_email(to, subject, from_email=from_email, metadata=metadata)
    logging.info(f"Sent email to {to}, with subject: {subject}, from: {from_email or 'default@email.com'}")


@spanreed.task(visibility_timeout_s=0)
def send_email_visibility(to: str, subject: str) -> None:
    _send_email(to, subject)


@spanreed.task(queue_type=QueueType.task_low)
def send_email_low(to: str, subject: str) -> None:
    _send_email(to, subject)


@spanreed.task(queue_type=QueueType.task_high)
def send_email_high(to: str, subject: str) -> None:
    _send_email(to, subject)


@spanreed.task(queue_type=QueueType.task_bulk)
def send_email_bulk(to: str, subject: str) -> None:
    _send_email(to, subject)
