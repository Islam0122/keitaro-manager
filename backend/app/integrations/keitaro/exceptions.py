"""Exceptions raised by the Keitaro API client."""


class KeitaroError(Exception):
    """Base class for all Keitaro integration errors."""


class KeitaroNotConfiguredError(KeitaroError):
    def __init__(self, message: str = "Подключение к Keitaro не настроено. Укажите API URL и API Key в настройках."):
        super().__init__(message)


class KeitaroConnectionError(KeitaroError):
    """Network level error (DNS, refused connection, TLS...)."""


class KeitaroTimeoutError(KeitaroConnectionError):
    """Request exceeded the configured timeout."""


class KeitaroAPIError(KeitaroError):
    """Keitaro answered with an error status or an invalid body."""

    def __init__(self, message: str, status_code: int | None = None, payload: object | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class KeitaroAuthError(KeitaroAPIError):
    """401/403 — wrong or insufficient API key."""


class KeitaroNotFoundError(KeitaroAPIError):
    """404 — requested entity does not exist in Keitaro."""


class KeitaroValidationError(KeitaroAPIError):
    """400/422 — Keitaro rejected the payload."""


class KeitaroRateLimitError(KeitaroAPIError):
    """429 — too many requests."""

    def __init__(self, message: str, retry_after: float | None = None, payload: object | None = None):
        super().__init__(message, 429, payload)
        self.retry_after = retry_after


class KeitaroServerError(KeitaroAPIError):
    """5xx — Keitaro itself failed."""
