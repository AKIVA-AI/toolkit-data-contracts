"""
Observability module for Toolkit Data Contracts & Drift Detection.

Provides structured JSON logging, operation-scoped metrics, correlation IDs,
and a health-check endpoint for integration with monitoring infrastructure.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Correlation context
# ---------------------------------------------------------------------------

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    """Generate a new correlation ID and set it for the current context.

    Returns:
        The newly generated correlation ID string.
    """
    cid = uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Return the current correlation ID (empty string if unset)."""
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    """Explicitly set the correlation ID for the current context."""
    _correlation_id.set(cid)


# ---------------------------------------------------------------------------
# Structured JSON formatter
# ---------------------------------------------------------------------------


class StructuredJsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Each log entry contains:
        timestamp, level, logger, message, correlation_id,
        and optionally exception details.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = get_correlation_id()
        if cid:
            entry["correlation_id"] = cid

        if record.exc_info and record.exc_info[1]:
            entry["exception_type"] = type(record.exc_info[1]).__name__
            entry["exception"] = str(record.exc_info[1])

        # Propagate extra fields attached via `extra=` on log calls
        for key in ("operation", "duration_ms", "record_count", "issue_count", "drift_detected"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        return json.dumps(entry, default=str)


# ---------------------------------------------------------------------------
# Operation timer
# ---------------------------------------------------------------------------


@dataclass
class OperationTimer:
    """Context-manager that measures wall-clock duration of an operation.

    Usage::

        with OperationTimer("validate") as t:
            do_work()
        print(t.duration_ms)
    """

    operation: str
    start: float = field(default=0.0, init=False)
    duration_ms: float = field(default=0.0, init=False)

    def __enter__(self) -> OperationTimer:
        self.start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        self.duration_ms = (time.monotonic() - self.start) * 1000.0


# ---------------------------------------------------------------------------
# Aggregate operation metrics
# ---------------------------------------------------------------------------


@dataclass
class OperationMetrics:
    """Accumulates counts and timings across multiple operations.

    Thread-safety note: this class is *not* thread-safe.  For single-process
    CLI usage that is acceptable.
    """

    schema_checks: int = 0
    schema_checks_passed: int = 0
    schema_checks_failed: int = 0
    drift_checks: int = 0
    drift_detected_count: int = 0
    profiles_computed: int = 0
    contracts_inferred: int = 0
    total_records_processed: int = 0
    _timings: dict[str, list[float]] = field(default_factory=dict)

    # -- recording helpers ---------------------------------------------------

    def record_schema_check(self, *, passed: bool, record_count: int = 0) -> None:
        """Record a schema validation run."""
        self.schema_checks += 1
        if passed:
            self.schema_checks_passed += 1
        else:
            self.schema_checks_failed += 1
        self.total_records_processed += record_count

    def record_drift_check(self, *, drift_detected: bool) -> None:
        """Record a drift check run."""
        self.drift_checks += 1
        if drift_detected:
            self.drift_detected_count += 1

    def record_profile(self, *, record_count: int = 0) -> None:
        """Record a profiling run."""
        self.profiles_computed += 1
        self.total_records_processed += record_count

    def record_infer(self, *, record_count: int = 0) -> None:
        """Record contract inference."""
        self.contracts_inferred += 1
        self.total_records_processed += record_count

    def record_timing(self, operation: str, duration_ms: float) -> None:
        """Append a timing sample for *operation*."""
        self._timings.setdefault(operation, []).append(duration_ms)

    # -- snapshot ------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of all metrics."""
        snap: dict[str, Any] = {
            "schema_checks": self.schema_checks,
            "schema_checks_passed": self.schema_checks_passed,
            "schema_checks_failed": self.schema_checks_failed,
            "drift_checks": self.drift_checks,
            "drift_detected_count": self.drift_detected_count,
            "profiles_computed": self.profiles_computed,
            "contracts_inferred": self.contracts_inferred,
            "total_records_processed": self.total_records_processed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._timings:
            timing_summary: dict[str, dict[str, float]] = {}
            for op, samples in self._timings.items():
                timing_summary[op] = {
                    "count": len(samples),
                    "total_ms": round(sum(samples), 2),
                    "avg_ms": round(sum(samples) / len(samples), 2),
                    "min_ms": round(min(samples), 2),
                    "max_ms": round(max(samples), 2),
                }
            snap["timings"] = timing_summary
        return snap

    def reset(self) -> None:
        """Reset all counters and timings."""
        self.schema_checks = 0
        self.schema_checks_passed = 0
        self.schema_checks_failed = 0
        self.drift_checks = 0
        self.drift_detected_count = 0
        self.profiles_computed = 0
        self.contracts_inferred = 0
        self.total_records_processed = 0
        self._timings.clear()


# ---------------------------------------------------------------------------
# Module-level singleton + convenience accessors
# ---------------------------------------------------------------------------

_global_metrics = OperationMetrics()


def get_operation_metrics() -> OperationMetrics:
    """Return the global ``OperationMetrics`` singleton."""
    return _global_metrics


def reset_operation_metrics() -> None:
    """Reset the global operation metrics."""
    _global_metrics.reset()


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


def health_probe() -> dict[str, Any]:
    """Lightweight health probe suitable for /healthz or CLI ``--health``.

    Returns a dict with status, version, and current metric snapshot.
    """
    try:
        from . import __version__

        return {
            "status": "healthy",
            "version": __version__,
            "metrics": _global_metrics.snapshot(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
