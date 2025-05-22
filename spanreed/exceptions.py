class RetryException(Exception):
    """
    Special exception that does not log an exception when it is received.
    This is a retryable error.
    """


class IgnoreException(Exception):
    """
    Indicates that this task should be ignored.
    """

    pass


class ConfigurationError(Exception):
    """
    There was some problem with settings
    """

    pass
