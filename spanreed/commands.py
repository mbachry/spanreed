import argparse
import os

from spanreed.backend import get_backend
from spanreed.const import QueueType
from spanreed.consumer import listen_for_messages


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue-type', type=QueueType, choices=list(QueueType), required=True)
    parser.add_argument('--num-messages', type=int, default=10)
    parser.add_argument('--visibility-timeout', type=int)
    parser.add_argument('--conf')
    args = parser.parse_args()
    if args.conf:
        os.environ['SPANREED_SETTINGS_MODULE'] = args.conf
    return args


def requeue_dead_letter():
    args = get_args()
    be = get_backend()
    be.requeue_dead_letter(args.queue_type, args.num_messages, args.visibility_timeout)


def spanreed_consumer():
    args = get_args()
    listen_for_messages(
        queue_type=args.queue_type, num_messages=args.num_messages, visibility_timeout_s=args.visibility_timeout
    )
