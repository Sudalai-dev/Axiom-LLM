"""
OCIF Observability Service — Core Logging & Correlation Tracking.

Provides structured JSON logging, dynamic context extraction, OpenTelemetry tracing
wrappers, and global request correlation ID propagation (per Doc 18 Section 8).

Traces to:
  - Document 8 (System Architecture) Section 6: Observability
  - Document 18 (Deployment Guide) Section 8: Monitoring & Alerting
"""

import contextvars
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variables to store request scope fields across threads/async tasks
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)


class JSONFormatter(logging.Formatter):
    """
    Structured JSON logger formatter.
    Formats logs into clean single-line JSON representations for cloud ingestion.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "filename": record.filename,
            "line_number": record.lineno,
        }

        # Inject request context parameters from contextvars
        corr_id = correlation_id_var.get()
        if corr_id:
            log_data["correlation_id"] = corr_id

        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id

        # Attach exception traces if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Merge extra payload attributes passed to logger
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logger(name: str, level: str = "INFO", output_json: bool = True) -> logging.Logger:
    """
    Initializes a standard console logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicating handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if output_json:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] %(levelname)s in %(name)s (%(filename)s:%(lineno)d): %(message)s"
                )
            )
        logger.addHandler(handler)

    return logger


# Global logger instance
logger = setup_logger("OCIF", level="INFO", output_json=True)


class RequestContextManager:
    """
    Context manager to bind request parameters to the current thread/task context.
    """

    def __init__(
        self,
        correlation_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        self.correlation_id = correlation_id
        self.user_id = user_id
        self.tokens: list = []

    def __enter__(self) -> "RequestContextManager":
        self.tokens.append(correlation_id_var.set(self.correlation_id))
        self.tokens.append(user_id_var.set(self.user_id))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Reset context variables in reverse order of setting
        for token in reversed(self.tokens):
            if token:
                # Retrieve the variable associated with the token to call reset
                token.var.reset(token)


class PerformanceTimer:
    """
    Helper utility to measure execution durations and automatically log them
    with correlation IDs.
    """

    def __init__(self, operation_name: str, threshold_ms: Optional[int] = None) -> None:
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.start_time: float = 0.0

    def __enter__(self) -> "PerformanceTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = int((time.perf_counter() - self.start_time) * 1000)
        
        extra = {"extra_fields": {"duration_ms": duration_ms, "operation": self.operation_name}}
        
        if self.threshold_ms and duration_ms > self.threshold_ms:
            logger.warning(
                f"Operation '{self.operation_name}' exceeded latency SLA threshold of {self.threshold_ms}ms: ran for {duration_ms}ms",
                extra=extra
            )
        else:
            logger.info(f"Operation '{self.operation_name}' completed in {duration_ms}ms", extra=extra)
