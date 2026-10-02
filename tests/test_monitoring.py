"""Tests for monitoring.ContractMetrics (the --metrics-out counters)."""

from __future__ import annotations

from toolkit_data_contracts_drift.monitoring import ContractMetrics

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
