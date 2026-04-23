"""Bootstrap exception types."""


class UnsupportedOSError(RuntimeError):
    """Raised when platform.system() is neither Darwin nor Linux."""
