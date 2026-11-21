"""Logging configuration with secret redaction."""
import logging
import re
import sys
import threading

_REDACTED = "***"
# Header/param style secrets that may appear in exception texts or debug output.
_PATTERNS = [
    re.compile(r"(?i)(api[-_]?key[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]+)"),
    re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?(?:bearer\s+)?)([^\s\"',;&]+)"),
    re.compile(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]+)"),
]

_known_secrets: set[str] = set()
_lock = threading.Lock()


def register_secret(value: str | None) -> None:
    """Remember a secret value so that it is replaced by *** in every log record."""
    if value and len(value) >= 6:
        with _lock:
            _known_secrets.add(value)


def redact(text: str) -> str:
    for secret in tuple(_known_secrets):
        if secret in text:
            text = text.replace(secret, _REDACTED)
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + _REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        if record.exc_info and not record.exc_text:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # httpx logs full URLs at INFO level; keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
