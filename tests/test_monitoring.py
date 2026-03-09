"""Tests for monitoring.py — Task 2: HealthCheck, ContractMetrics, get_health_status.
Also covers Task 10: datetime.utcnow() deprecation fix verification.
"""

from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.monitoring import (
    ContractMetrics,
    HealthCheck,
    get_health_status,
    get_metrics,
)

# ============================================================================
# HealthCheck Tests
# ============================================================================


class TestHealthCheckSystem:
    """Test HealthCheck.check_system()."""

    def test_check_system_healthy(self):
        """System health check returns healthy status."""
        result = HealthCheck.check_system()
        assert result["status"] == "healthy"
        assert "version" in result
        assert "timestamp" in result

    def test_check_system_has_version(self):
        """System health check includes package version."""
        result = HealthCheck.check_system()
        assert result["version"] == "0.1.0"

    def test_check_system_timestamp_is_iso(self):
        """Timestamp is valid ISO format."""
        result = HealthCheck.check_system()
        # Should not raise
        from datetime import datetime

        datetime.fromisoformat(result["timestamp"])


class TestHealthCheckContract:
    """Test HealthCheck.check_contract()."""

    def test_check_contract_valid(self, tmp_path: Path):
        """Valid contract returns 'valid' status."""
        contract_path = tmp_path / "contract.json"
        contract_path.write_text(
            json.dumps({"version": 1, "fields": {"a": {"types": ["string"]}}}),
            encoding="utf-8",
        )
        result = HealthCheck.check_contract(contract_path)
        assert result["status"] == "valid"
        assert result["version"] == 1
        assert result["fields"] == 1

    def test_check_contract_not_found(self, tmp_path: Path):
        """Non-existent contract returns 'not_found' status."""
        result = HealthCheck.check_contract(tmp_path / "missing.json")
        assert result["status"] == "not_found"

    def test_check_contract_invalid_json(self, tmp_path: Path):
        """Invalid JSON returns 'invalid_json' status."""
        contract_path = tmp_path / "bad.json"
        contract_path.write_text("not json at all", encoding="utf-8")
        result = HealthCheck.check_contract(contract_path)
        assert result["status"] == "invalid_json"
        assert "error" in result

    def test_check_contract_missing_fields(self, tmp_path: Path):
        """Contract missing required keys returns 'invalid' status."""
        contract_path = tmp_path / "incomplete.json"
        contract_path.write_text(json.dumps({"name": "test"}), encoding="utf-8")
        result = HealthCheck.check_contract(contract_path)
        assert result["status"] == "invalid"
        assert "version" in result["missing_fields"]
        assert "fields" in result["missing_fields"]

    def test_check_contract_missing_version_only(self, tmp_path: Path):
        """Contract missing only version."""
        contract_path = tmp_path / "no_version.json"
        contract_path.write_text(json.dumps({"fields": {"a": {}}}), encoding="utf-8")
        result = HealthCheck.check_contract(contract_path)
        assert result["status"] == "invalid"
        assert "version" in result["missing_fields"]
        assert "fields" not in result["missing_fields"]


# ============================================================================
# ContractMetrics Tests
# ============================================================================


class TestContractMetrics:
    """Test ContractMetrics class."""

    def test_initial_metrics_zero(self):
        """New metrics instance has all zeros."""
        m = ContractMetrics()
        metrics = m.get_metrics()
        assert metrics["contracts_created"] == 0
        assert metrics["validations_performed"] == 0
        assert metrics["validations_passed"] == 0
        assert metrics["validations_failed"] == 0
        assert metrics["drift_checks"] == 0
        assert metrics["drift_detected"] == 0

    def test_record_contract_creation(self):
        """Recording contract creation increments counter."""
        m = ContractMetrics()
        m.record_contract_creation()
        m.record_contract_creation()
        assert m.get_metrics()["contracts_created"] == 2

    def test_record_validation_passed(self):
        """Recording passed validation updates correct counters."""
        m = ContractMetrics()
        m.record_validation(passed=True)
        metrics = m.get_metrics()
        assert metrics["validations_performed"] == 1
        assert metrics["validations_passed"] == 1
        assert metrics["validations_failed"] == 0

    def test_record_validation_failed(self):
        """Recording failed validation updates correct counters."""
        m = ContractMetrics()
        m.record_validation(passed=False)
        metrics = m.get_metrics()
        assert metrics["validations_performed"] == 1
        assert metrics["validations_passed"] == 0
        assert metrics["validations_failed"] == 1

    def test_record_drift_check_no_drift(self):
        """Recording drift check with no drift."""
        m = ContractMetrics()
        m.record_drift_check(drift_detected=False)
        metrics = m.get_metrics()
        assert metrics["drift_checks"] == 1
        assert metrics["drift_detected"] == 0

    def test_record_drift_check_with_drift(self):
        """Recording drift check with drift detected."""
        m = ContractMetrics()
        m.record_drift_check(drift_detected=True)
        metrics = m.get_metrics()
        assert metrics["drift_checks"] == 1
        assert metrics["drift_detected"] == 1

    def test_validation_success_rate(self):
        """Success rate calculated correctly."""
        m = ContractMetrics()
        m.record_validation(passed=True)
        m.record_validation(passed=True)
        m.record_validation(passed=False)
        metrics = m.get_metrics()
        assert abs(metrics["validation_success_rate"] - 2.0 / 3.0) < 1e-9

    def test_validation_success_rate_no_validations(self):
        """Success rate is 0 when no validations performed."""
        m = ContractMetrics()
        assert m.get_metrics()["validation_success_rate"] == 0.0

    def test_drift_detection_rate(self):
        """Drift detection rate calculated correctly."""
        m = ContractMetrics()
        m.record_drift_check(drift_detected=True)
        m.record_drift_check(drift_detected=False)
        metrics = m.get_metrics()
        assert abs(metrics["drift_detection_rate"] - 0.5) < 1e-9

    def test_drift_detection_rate_no_checks(self):
        """Drift detection rate is 0 when no checks performed."""
        m = ContractMetrics()
        assert m.get_metrics()["drift_detection_rate"] == 0.0

    def test_reset(self):
        """Reset clears all metrics to zero."""
        m = ContractMetrics()
        m.record_contract_creation()
        m.record_validation(passed=True)
        m.record_drift_check(drift_detected=True)
        m.reset()
        metrics = m.get_metrics()
        assert metrics["contracts_created"] == 0
        assert metrics["validations_performed"] == 0
        assert metrics["drift_checks"] == 0

    def test_get_metrics_has_timestamp(self):
        """Metrics include timestamp."""
        m = ContractMetrics()
        metrics = m.get_metrics()
        assert "timestamp" in metrics


# ============================================================================
# Module-Level Function Tests
# ============================================================================


class TestGetMetrics:
    """Test get_metrics() module function."""

    def test_get_metrics_returns_dict(self):
        """get_metrics returns a dict with expected keys."""
        result = get_metrics()
        assert isinstance(result, dict)
        assert "contracts_created" in result
        assert "timestamp" in result


class TestGetHealthStatus:
    """Test get_health_status() function."""

    def test_health_status_without_contract(self):
        """Health status without contract path."""
        result = get_health_status()
        assert "system" in result
        assert "metrics" in result
        assert "contract" not in result

    def test_health_status_with_contract(self, tmp_path: Path):
        """Health status with valid contract path."""
        contract_path = tmp_path / "contract.json"
        contract_path.write_text(json.dumps({"version": 1, "fields": {}}), encoding="utf-8")
        result = get_health_status(contract_path=contract_path)
        assert "system" in result
        assert "metrics" in result
        assert "contract" in result
        assert result["contract"]["status"] == "valid"

    def test_health_status_with_missing_contract(self, tmp_path: Path):
        """Health status with missing contract path still returns system/metrics."""
        result = get_health_status(contract_path=tmp_path / "missing.json")
        assert "system" in result
        assert "metrics" in result
        assert result["contract"]["status"] == "not_found"
