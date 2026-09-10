import json
import logging

# Attributes the request/response logging middleware attaches via `extra=...`.
_REQUEST_EXTRA_KEYS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "client_ip",
    "user_id",
)


class JSONFormatter(logging.Formatter):
    """Renders each log record as a single-line JSON object for stdout.

    Structured logs are what a container platform's log pipeline expects; the
    request/response middleware's ``extra`` fields are promoted to top-level
    keys so they stay queryable.
    """

    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in _REQUEST_EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
