"""Tests for the observability module: structured logging, correlation IDs,
operation timers, OperationMetrics, and health_probe.
"""

from __future__ import annotations

import json
import logging
import time

from toolkit_data_contracts_drift.observability import (
    OperationMetrics,
    OperationTimer,
    StructuredJsonFormatter,
    get_correlation_id,
    get_operation_metrics,
    health_probe,
    new_correlation_id,
    reset_operation_metrics,
    set_correlation_id,
)

# ---------------------------------------------------------------------------
# Correlation ID
# ---------------------------------------------------------------------------


class TestCorrelationId:
    """Test correlation-ID context variable helpers."""

    def test_new_correlation_id_returns_string(self):
        cid = new_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) == 12

    def test_get_after_new(self):
        cid = new_correlation_id()
        assert get_correlation_id() == cid

    def test_set_and_get(self):
        set_correlation_id("custom-abc")
        assert get_correlation_id() == "custom-abc"

    def test_default_is_empty_string(self):
        """After resetting, default is empty string."""
        set_correlation_id("")
        assert get_correlation_id() == ""

    def test_new_replaces_previous(self):
        cid1 = new_correlation_id()
        cid2 = new_correlation_id()
        assert cid1 != cid2
        assert get_correlation_id() == cid2


# ---------------------------------------------------------------------------
# StructuredJsonFormatter
# ---------------------------------------------------------------------------


class TestStructuredJsonFormatter:
    """Test the JSON log formatter."""

    def _make_record(
        self,
        msg: str = "test message",
        level: int = logging.INFO,
        **extra: object,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_output_is_valid_json(self):
        fmt = StructuredJsonFormatter()
        record = self._make_record()
        line = fmt.format(record)
        parsed = json.loads(line)
        assert parsed["message"] == "test message"

    def test_includes_core_fields(self):
        fmt = StructuredJsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"

    def test_includes_correlation_id_when_set(self):
        set_correlation_id("corr-123")
        fmt = StructuredJsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        assert parsed["correlation_id"] == "corr-123"
        set_correlation_id("")

    def test_omits_correlation_id_when_empty(self):
        set_correlation_id("")
        fmt = StructuredJsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        assert "correlation_id" not in parsed

    def test_exception_info(self):
        fmt = StructuredJsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = self._make_record()
            record.exc_info = sys.exc_info()
        parsed = json.loads(fmt.format(record))
        assert parsed["exception_type"] == "ValueError"
        assert "boom" in parsed["exception"]

    def test_extra_fields_propagated(self):
        fmt = StructuredJsonFormatter()
        record = self._make_record(
            operation="validate",
            duration_ms=42.5,
            record_count=100,
            issue_count=3,
            drift_detected=True,
        )
        parsed = json.loads(fmt.format(record))
        assert parsed["operation"] == "validate"
        assert parsed["duration_ms"] == 42.5
        assert parsed["record_count"] == 100
        assert parsed["issue_count"] == 3
        assert parsed["drift_detected"] is True

    def test_warning_level(self):
        fmt = StructuredJsonFormatter()
        record = self._make_record(level=logging.WARNING)
        parsed = json.loads(fmt.format(record))
        assert parsed["level"] == "WARNING"

    def test_error_level(self):
        fmt = StructuredJsonFormatter()
        record = self._make_record(level=logging.ERROR)
        parsed = json.loads(fmt.format(record))
        assert parsed["level"] == "ERROR"


# ---------------------------------------------------------------------------
# OperationTimer
# ---------------------------------------------------------------------------


class TestOperationTimer:
    """Test the OperationTimer context manager."""

    def test_measures_duration(self):
        with OperationTimer("test") as t:
            time.sleep(0.05)
        assert t.duration_ms >= 0
        assert t.operation == "test"

    def test_zero_work_duration(self):
        with OperationTimer("noop") as t:
            pass
        assert t.duration_ms >= 0

    def test_operation_name_preserved(self):
        with OperationTimer("infer_contract") as t:
            pass
        assert t.operation == "infer_contract"


# ---------------------------------------------------------------------------
# OperationMetrics
# ---------------------------------------------------------------------------


class TestOperationMetrics:
    """Test the OperationMetrics dataclass."""

    def test_initial_state(self):
        m = OperationMetrics()
        snap = m.snapshot()
        assert snap["schema_checks"] == 0
        assert snap["drift_checks"] == 0
        assert snap["profiles_computed"] == 0
        assert snap["contracts_inferred"] == 0
        assert snap["total_records_processed"] == 0

    def test_record_schema_check_pass(self):
        m = OperationMetrics()
        m.record_schema_check(passed=True, record_count=50)
        snap = m.snapshot()
        assert snap["schema_checks"] == 1
        assert snap["schema_checks_passed"] == 1
        assert snap["schema_checks_failed"] == 0
        assert snap["total_records_processed"] == 50

    def test_record_schema_check_fail(self):
        m = OperationMetrics()
        m.record_schema_check(passed=False, record_count=10)
        snap = m.snapshot()
        assert snap["schema_checks"] == 1
        assert snap["schema_checks_passed"] == 0
        assert snap["schema_checks_failed"] == 1

    def test_record_drift_check_no_drift(self):
        m = OperationMetrics()
        m.record_drift_check(drift_detected=False)
        assert m.snapshot()["drift_checks"] == 1
        assert m.snapshot()["drift_detected_count"] == 0

    def test_record_drift_check_with_drift(self):
        m = OperationMetrics()
        m.record_drift_check(drift_detected=True)
        assert m.snapshot()["drift_detected_count"] == 1

    def test_record_profile(self):
        m = OperationMetrics()
        m.record_profile(record_count=200)
        assert m.snapshot()["profiles_computed"] == 1
        assert m.snapshot()["total_records_processed"] == 200

    def test_record_infer(self):
        m = OperationMetrics()
        m.record_infer(record_count=75)
        assert m.snapshot()["contracts_inferred"] == 1
        assert m.snapshot()["total_records_processed"] == 75

    def test_record_timing(self):
        m = OperationMetrics()
        m.record_timing("validate", 10.0)
        m.record_timing("validate", 20.0)
        snap = m.snapshot()
        assert "timings" in snap
        t = snap["timings"]["validate"]
        assert t["count"] == 2
        assert t["avg_ms"] == 15.0
        assert t["min_ms"] == 10.0
        assert t["max_ms"] == 20.0
        assert t["total_ms"] == 30.0

    def test_snapshot_no_timings_key_when_empty(self):
        m = OperationMetrics()
        snap = m.snapshot()
        assert "timings" not in snap

    def test_snapshot_has_timestamp(self):
        m = OperationMetrics()
        snap = m.snapshot()
        assert "timestamp" in snap

    def test_reset(self):
        m = OperationMetrics()
        m.record_schema_check(passed=True, record_count=10)
        m.record_drift_check(drift_detected=True)
        m.record_profile(record_count=5)
        m.record_infer(record_count=3)
        m.record_timing("x", 1.0)
        m.reset()
        snap = m.snapshot()
        assert snap["schema_checks"] == 0
        assert snap["drift_checks"] == 0
        assert snap["profiles_computed"] == 0
        assert snap["contracts_inferred"] == 0
        assert snap["total_records_processed"] == 0
        assert "timings" not in snap

    def test_cumulative_counts(self):
        m = OperationMetrics()
        m.record_schema_check(passed=True, record_count=10)
        m.record_schema_check(passed=False, record_count=5)
        m.record_schema_check(passed=True, record_count=3)
        assert m.snapshot()["schema_checks"] == 3
        assert m.snapshot()["schema_checks_passed"] == 2
        assert m.snapshot()["schema_checks_failed"] == 1
        assert m.snapshot()["total_records_processed"] == 18

    def test_record_schema_check_no_record_count(self):
        """record_count defaults to 0."""
        m = OperationMetrics()
        m.record_schema_check(passed=True)
        assert m.snapshot()["total_records_processed"] == 0


# ---------------------------------------------------------------------------
# Global singleton accessors
# ---------------------------------------------------------------------------


class TestGlobalMetrics:
    """Test module-level get/reset functions."""

    def test_get_operation_metrics_returns_instance(self):
        m = get_operation_metrics()
        assert isinstance(m, OperationMetrics)

    def test_reset_operation_metrics(self):
        m = get_operation_metrics()
        m.record_schema_check(passed=True, record_count=1)
        reset_operation_metrics()
        assert m.snapshot()["schema_checks"] == 0


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


class TestHealthProbe:
    """Test health_probe() function."""

    def test_returns_healthy(self):
        result = health_probe()
        assert result["status"] == "healthy"
        assert "version" in result
        assert "metrics" in result
        assert "timestamp" in result

    def test_metrics_is_dict(self):
        result = health_probe()
        assert isinstance(result["metrics"], dict)
        assert "schema_checks" in result["metrics"]

    def test_json_serializable(self):
        """Health probe output is JSON-serializable."""
        result = health_probe()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)
