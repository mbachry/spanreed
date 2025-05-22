import functools


@functools.cache
def get_backend():
    from spanreed.conf import settings

    return settings.SPANREED_BACKEND_CLASS()
