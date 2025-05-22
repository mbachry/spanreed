import importlib
import os
from functools import cache

from pydantic import ConfigDict, ImportString, RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SPANREED_REDIS_URL: RedisDsn
    SPANREED_PUBLISHER: str
    SPANREED_QUEUE: str = None
    SPANREED_BACKEND_CLASS: ImportString = 'spanreed.backend.redis.RedisBackend'
    SPANREED_REDIS_DLQ_MAX_UNACKED: int = 5
    SPANREED_MODELS: list[ImportString] = []
    SPANREED_DEFAULT_HEADERS: ImportString = 'spanreed.const.default_headers_hook'
    SPANREED_PRE_PROCESS_HOOK: ImportString = 'spanreed.const.noop_hook'
    SPANREED_POST_PROCESS_HOOK: ImportString = 'spanreed.const.noop_hook'
    SPANREED_TASK_CLASS: ImportString = 'spanreed.task_manager.Task'

    model_config = ConfigDict(extra='allow')


@cache
def user_settings():
    have_django = False
    if 'DJANGO_SETTINGS_MODULE' in os.environ:
        try:
            from django.conf import settings as setting_vars

            # "evaluate" settings to make django initialize them
            dir(setting_vars)
            setting_vars = setting_vars._wrapped
            have_django = True
        except ImportError:
            pass
    if not have_django:
        if 'SPANREED_SETTINGS_MODULE' not in os.environ:
            raise ImportError('No settings module found to import')
        setting_vars = importlib.import_module(os.environ['SPANREED_SETTINGS_MODULE'], package=None)
    setting_vars = {k: v for k, v in setting_vars.__dict__.items() if k.startswith('SPANREED_')}
    return Settings(**setting_vars)


class LazySettings:
    def __getattr__(self, key):
        return getattr(user_settings(), key)


settings = LazySettings()
