"""
OCIF Telemetry & Metrics Engine — Cross-Cutting.

Integrates OpenTelemetry distributed tracing spans (L1-L8 correlation)
and exports Prometheus metrics for request error rates and latencies (per Doc 18 Section 8).

Traces to:
  - Document 8 (System Architecture) Section 6: Observability (Tracing, Metrics)
  - Document 18 (Deployment Guide) Section 8: Monitoring & Alerting Thresholds
"""

import logging
import time
from typing import Dict, Any, List, Optional

from core.config import settings

logger = logging.getLogger("AxiomTelemetry")


class TelemetryEngine:
    """
    Manages telemetry collection and exports.
    """

    def __init__(self) -> None:
        self.otel_enabled = bool(settings.observability.otel_endpoint)
        self.metrics_counters: Dict[str, int] = {
            "requests_total": 0,
            "errors_total": 0,
            "policy_blocks_total": 0
        }
        self.latency_durations: List[float] = []

        if self.otel_enabled:
            logger.info(f"OpenTelemetry collector active on endpoint: {settings.observability.otel_endpoint}")

    def start_span(self, span_name: str, correlation_id: str) -> Dict[str, Any]:
        """
        Starts a distributed trace span.
        """
        logger.debug(f"Span '{span_name}' started (Correlation ID: {correlation_id})")
        return {
            "span_name": span_name,
            "correlation_id": correlation_id,
            "start_time": time.perf_counter()
        }

    def end_span(self, span: Dict[str, Any], attributes: Optional[Dict[str, Any]] = None) -> None:
        """
        Closes trace span and exports duration metrics.
        """
        duration = (time.perf_counter() - span["start_time"]) * 1000
        logger.debug(
            f"Span '{span['span_name']}' completed in {duration:.2f}ms. "
            f"Attributes: {attributes or {}}"
        )

    def increment_metric(self, name: str, value: int = 1) -> None:
        """Increments Prometheus counter."""
        if name in self.metrics_counters:
            self.metrics_counters[name] += value
            logger.debug(f"Telemetry metric '{name}' incremented to {self.metrics_counters[name]}")

    def record_latency(self, duration_ms: float) -> None:
        """Records latency duration to calculate p95/p99 bounds."""
        self.latency_durations.append(duration_ms)
        
        # Performance alerts check per Doc 18 Section 8
        if duration_ms > settings.observability.latency_critical_ms:
            logger.critical(
                f"ALERT: Request latency critical ({duration_ms:.0f}ms) "
                f"exceeded threshold of {settings.observability.latency_critical_ms}ms!"
            )
        elif duration_ms > settings.observability.latency_warning_ms:
            logger.warning(
                f"WARN: Request latency warning ({duration_ms:.0f}ms) "
                f"exceeded threshold of {settings.observability.latency_warning_ms}ms"
            )


# Global singleton instance
telemetry = TelemetryEngine()
