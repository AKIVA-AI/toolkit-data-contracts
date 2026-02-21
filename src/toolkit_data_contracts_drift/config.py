"""
Configuration management for Toolkit Data Contracts & Drift Detection
"""

import os
from typing import Optional


class Config:
    """Configuration settings for Data Contracts"""
    
    # Inference Settings
    DEFAULT_SAMPLE_SIZE: int = int(os.getenv("DEFAULT_SAMPLE_SIZE", "1000"))
    DEFAULT_CONFIDENCE_THRESHOLD: float = float(
        os.getenv("DEFAULT_CONFIDENCE_THRESHOLD", "0.95")
    )
    
    # Drift Detection Settings
    DEFAULT_DRIFT_THRESHOLD: float = float(os.getenv("DEFAULT_DRIFT_THRESHOLD", "0.1"))
    ENABLE_STATISTICAL_TESTS: bool = os.getenv("ENABLE_STATISTICAL_TESTS", "true").lower() == "true"
    
    # Validation Settings
    ALLOW_EXTRA_FIELDS: bool = os.getenv("ALLOW_EXTRA_FIELDS", "false").lower() == "true"
    STRICT_TYPE_CHECKING: bool = os.getenv("STRICT_TYPE_CHECKING", "true").lower() == "true"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    
    # Performance
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10000"))
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "4"))
    
    # Output
    OUTPUT_FORMAT: str = os.getenv("OUTPUT_FORMAT", "json")
    VERBOSE: bool = os.getenv("VERBOSE", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings"""
        if not 0 <= cls.DEFAULT_CONFIDENCE_THRESHOLD <= 1:
            raise ValueError("DEFAULT_CONFIDENCE_THRESHOLD must be between 0 and 1")
        
        if not 0 <= cls.DEFAULT_DRIFT_THRESHOLD <= 1:
            raise ValueError("DEFAULT_DRIFT_THRESHOLD must be between 0 and 1")
        
        if cls.DEFAULT_SAMPLE_SIZE < 1:
            raise ValueError("DEFAULT_SAMPLE_SIZE must be positive")
        
        if cls.BATCH_SIZE < 1:
            raise ValueError("BATCH_SIZE must be positive")
        
        if cls.MAX_WORKERS < 1:
            raise ValueError("MAX_WORKERS must be positive")
        
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if cls.LOG_LEVEL.upper() not in valid_log_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_log_levels}")
    
    @classmethod
    def get_config_dict(cls) -> dict:
        """Get configuration as dictionary"""
        return {
            "inference": {
                "sample_size": cls.DEFAULT_SAMPLE_SIZE,
                "confidence_threshold": cls.DEFAULT_CONFIDENCE_THRESHOLD,
            },
            "drift_detection": {
                "threshold": cls.DEFAULT_DRIFT_THRESHOLD,
                "statistical_tests": cls.ENABLE_STATISTICAL_TESTS,
            },
            "validation": {
                "allow_extra_fields": cls.ALLOW_EXTRA_FIELDS,
                "strict_type_checking": cls.STRICT_TYPE_CHECKING,
            },
            "performance": {
                "batch_size": cls.BATCH_SIZE,
                "max_workers": cls.MAX_WORKERS,
            },
            "logging": {
                "level": cls.LOG_LEVEL,
                "file": cls.LOG_FILE,
            },
        }


# Validate configuration on import
Config.validate()


