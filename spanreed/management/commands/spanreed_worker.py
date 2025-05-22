import importlib

from django.conf import settings
from django.core.management.base import BaseCommand

from spanreed.consumer import listen_for_messages
from spanreed.models import QueueType


class Command(BaseCommand):
    help = 'Spanreed worker'

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue-type', type=QueueType, choices=list(QueueType), required=True, help='Spanreed queue'
        )
        parser.add_argument('--num-messages', type=int, default=10)
        parser.add_argument('--visibility-timeout', type=int, required=False, help='Visibility timeout in seconds')

    @staticmethod
    def import_all_tasks():
        for app in settings.INSTALLED_APPS:
            try:
                importlib.import_module(f'{app}.tasks')
            except ModuleNotFoundError:
                pass

    def handle(self, *args, **options):
        self.import_all_tasks()
        listen_for_messages(
            queue_type=options['queue_type'],
            num_messages=options['num_messages'],
            visibility_timeout_s=options['visibility_timeout'],
        )
