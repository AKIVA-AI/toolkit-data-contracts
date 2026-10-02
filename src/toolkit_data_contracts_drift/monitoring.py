"""Per-run counters written by ``toolkit-contracts check --metrics-out``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ContractMetrics:
    """Track contract and validation metrics"""

    def __init__(self):
        self.metrics = {
            "contracts_created": 0,
            "validations_performed": 0,
            "validations_passed": 0,
            "validations_failed": 0,
            "drift_checks": 0,
            "drift_detected": 0,
        }

    def record_contract_creation(self):
        """Record contract creation"""
        self.metrics["contracts_created"] += 1

    def record_validation(self, passed: bool):
        """Record validation result"""
        self.metrics["validations_performed"] += 1
        if passed:
            self.metrics["validations_passed"] += 1
        else:
            self.metrics["validations_failed"] += 1

    def record_drift_check(self, drift_detected: bool):
        """Record drift check result"""
        self.metrics["drift_checks"] += 1
        if drift_detected:
            self.metrics["drift_detected"] += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics"""
        return {
            **self.metrics,
            "validation_success_rate": (
                self.metrics["validations_passed"] / self.metrics["validations_performed"]
                if self.metrics["validations_performed"] > 0
                else 0.0
            ),
            "drift_detection_rate": (
                self.metrics["drift_detected"] / self.metrics["drift_checks"]
                if self.metrics["drift_checks"] > 0
                else 0.0
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self):
        """Reset all metrics"""
        for key in self.metrics:
            self.metrics[key] = 0
