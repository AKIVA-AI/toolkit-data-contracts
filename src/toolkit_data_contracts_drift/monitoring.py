"""
Monitoring and health checks for Toolkit Data Contracts & Drift Detection
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class HealthCheck:
    """Health check utilities"""
    
    @staticmethod
    def check_system() -> Dict[str, Any]:
        """Check system health"""
        try:
            from . import __version__
            
            return {
                "status": "healthy",
                "version": __version__,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def check_contract(contract_path: Path) -> Dict[str, Any]:
        """Check if contract file is valid"""
        try:
            if not contract_path.exists():
                return {
                    "status": "not_found",
                    "path": str(contract_path),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            with open(contract_path) as f:
                contract = json.load(f)
            
            required_fields = ["version", "schema"]
            missing = [f for f in required_fields if f not in contract]
            
            if missing:
                return {
                    "status": "invalid",
                    "missing_fields": missing,
                    "path": str(contract_path),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            return {
                "status": "valid",
                "version": contract.get("version"),
                "fields": len(contract.get("schema", {}).get("fields", {})),
                "path": str(contract_path),
                "timestamp": datetime.utcnow().isoformat()
            }
        except json.JSONDecodeError as e:
            return {
                "status": "invalid_json",
                "error": str(e),
                "path": str(contract_path),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "path": str(contract_path),
                "timestamp": datetime.utcnow().isoformat()
            }


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
    
    def get_metrics(self) -> Dict[str, Any]:
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
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def reset(self):
        """Reset all metrics"""
        for key in self.metrics:
            self.metrics[key] = 0


# Global metrics instance
_metrics = ContractMetrics()


def get_metrics() -> Dict[str, Any]:
    """Get global metrics"""
    return _metrics.get_metrics()


def get_health_status(contract_path: Optional[Path] = None) -> Dict[str, Any]:
    """Get comprehensive health status"""
    status = {
        "system": HealthCheck.check_system(),
        "metrics": get_metrics()
    }
    
    if contract_path:
        status["contract"] = HealthCheck.check_contract(contract_path)
    
    return status


