"""
Structured JSON logging for Clearance Check Canary API.
Outputs RFC-compliant structured JSON logs to standard output for container log aggregation.
"""
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class JSONLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": "canary",
            "version": "2.0.1-canary.1",
        }
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_obj["method"] = record.method
        if hasattr(record, "path"):
            log_obj["path"] = record.path
        if hasattr(record, "status_code"):
            log_obj["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
        if hasattr(record, "user"):
            log_obj["user"] = record.user
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def setup_json_logging(level: int = logging.INFO) -> logging.Logger:
    """Configures root logger with JSON stdout stream handler."""
    logger = logging.getLogger("canary")
    logger.setLevel(level)
    # Remove existing handlers to avoid duplicate stdout lines
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONLogFormatter())
    logger.addHandler(handler)
    return logger


logger = setup_json_logging()


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware logging each HTTP transaction as structured JSON."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        extra = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        # Avoid spamming log on health/readiness endpoints if desired, but record at DEBUG/INFO
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
            extra=extra,
        )
        return response
