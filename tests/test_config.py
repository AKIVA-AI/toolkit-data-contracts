"""Tests for config.py — Task 1: Config.validate, get_config_dict, env var parsing."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestConfigValidate:
    """Test Config.validate() method."""

    _DEFAULT_ENV = {
        "DEFAULT_SAMPLE_SIZE": "1000",
        "DEFAULT_CONFIDENCE_THRESHOLD": "0.95",
        "DEFAULT_DRIFT_THRESHOLD": "0.1",
        "ENABLE_STATISTICAL_TESTS": "true",
        "ALLOW_EXTRA_FIELDS": "false",
        "STRICT_TYPE_CHECKING": "true",
        "LOG_LEVEL": "INFO",
        "BATCH_SIZE": "10000",
        "MAX_WORKERS": "4",
        "OUTPUT_FORMAT": "json",
        "VERBOSE": "false",
    }

    def _fresh_config(self, env_overrides: dict[str, str] | None = None):
        """Import Config with fresh env vars. Raises on import if validation fails."""
        import importlib
        import toolkit_data_contracts_drift.config as cfg_mod

        env = {**self._DEFAULT_ENV}
        if env_overrides:
            env.update(env_overrides)
        with patch.dict(os.environ, env, clear=False):
            importlib.reload(cfg_mod)
        return cfg_mod.Config

    def _reload_expecting_error(self, env_overrides: dict[str, str], match: str):
        """Reload config expecting ValueError on import (validation runs at import time)."""
        import importlib
        import toolkit_data_contracts_drift.config as cfg_mod

        env = {**self._DEFAULT_ENV, **env_overrides}
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match=match):
                importlib.reload(cfg_mod)
        # Restore valid config so other tests aren't broken
        with patch.dict(os.environ, self._DEFAULT_ENV, clear=False):
            importlib.reload(cfg_mod)

    def test_validate_defaults_pass(self):
        """Default configuration passes validation."""
        Config = self._fresh_config()
        Config.validate()

    def test_validate_confidence_threshold_too_high(self):
        """Confidence threshold > 1 raises ValueError."""
        self._reload_expecting_error(
            {"DEFAULT_CONFIDENCE_THRESHOLD": "1.5"},
            "DEFAULT_CONFIDENCE_THRESHOLD",
        )

    def test_validate_confidence_threshold_too_low(self):
        """Confidence threshold < 0 raises ValueError."""
        self._reload_expecting_error(
            {"DEFAULT_CONFIDENCE_THRESHOLD": "-0.1"},
            "DEFAULT_CONFIDENCE_THRESHOLD",
        )

    def test_validate_drift_threshold_too_high(self):
        """Drift threshold > 1 raises ValueError."""
        self._reload_expecting_error(
            {"DEFAULT_DRIFT_THRESHOLD": "2.0"},
            "DEFAULT_DRIFT_THRESHOLD",
        )

    def test_validate_drift_threshold_too_low(self):
        """Drift threshold < 0 raises ValueError."""
        self._reload_expecting_error(
            {"DEFAULT_DRIFT_THRESHOLD": "-0.5"},
            "DEFAULT_DRIFT_THRESHOLD",
        )

    def test_validate_sample_size_zero(self):
        """Sample size of 0 raises ValueError."""
        self._reload_expecting_error(
            {"DEFAULT_SAMPLE_SIZE": "0"},
            "DEFAULT_SAMPLE_SIZE",
        )

    def test_validate_sample_size_negative(self):
        """Negative sample size raises ValueError."""
        self._reload_expecting_error(
            {"DEFAULT_SAMPLE_SIZE": "-1"},
            "DEFAULT_SAMPLE_SIZE",
        )

    def test_validate_batch_size_zero(self):
        """Batch size of 0 raises ValueError."""
        self._reload_expecting_error({"BATCH_SIZE": "0"}, "BATCH_SIZE")

    def test_validate_max_workers_zero(self):
        """Max workers of 0 raises ValueError."""
        self._reload_expecting_error({"MAX_WORKERS": "0"}, "MAX_WORKERS")

    def test_validate_invalid_log_level(self):
        """Invalid log level raises ValueError."""
        self._reload_expecting_error({"LOG_LEVEL": "TRACE"}, "LOG_LEVEL")

    def test_validate_valid_log_levels(self):
        """All valid log levels pass validation."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            Config = self._fresh_config({"LOG_LEVEL": level})
            Config.validate()


class TestConfigGetConfigDict:
    """Test Config.get_config_dict() method."""

    _DEFAULT_ENV = TestConfigValidate._DEFAULT_ENV

    def _fresh_config(self, env_overrides: dict[str, str] | None = None):
        import importlib
        import toolkit_data_contracts_drift.config as cfg_mod

        env = {**self._DEFAULT_ENV}
        if env_overrides:
            env.update(env_overrides)
        with patch.dict(os.environ, env, clear=False):
            importlib.reload(cfg_mod)
        return cfg_mod.Config

    def test_get_config_dict_structure(self):
        """Config dict has expected top-level keys."""
        Config = self._fresh_config()
        d = Config.get_config_dict()
        assert "inference" in d
        assert "drift_detection" in d
        assert "validation" in d
        assert "performance" in d
        assert "logging" in d

    def test_get_config_dict_default_values(self):
        """Config dict reflects default values."""
        Config = self._fresh_config()
        d = Config.get_config_dict()
        assert d["inference"]["sample_size"] == 1000
        assert d["inference"]["confidence_threshold"] == 0.95
        assert d["drift_detection"]["threshold"] == 0.1
        assert d["drift_detection"]["statistical_tests"] is True
        assert d["validation"]["allow_extra_fields"] is False
        assert d["validation"]["strict_type_checking"] is True
        assert d["performance"]["batch_size"] == 10000
        assert d["performance"]["max_workers"] == 4
        assert d["logging"]["level"] == "INFO"

    def test_get_config_dict_custom_env_vars(self):
        """Config dict reflects custom env var values."""
        Config = self._fresh_config({
            "DEFAULT_SAMPLE_SIZE": "500",
            "DEFAULT_CONFIDENCE_THRESHOLD": "0.99",
            "ENABLE_STATISTICAL_TESTS": "false",
            "ALLOW_EXTRA_FIELDS": "true",
        })
        d = Config.get_config_dict()
        assert d["inference"]["sample_size"] == 500
        assert d["inference"]["confidence_threshold"] == 0.99
        assert d["drift_detection"]["statistical_tests"] is False
        assert d["validation"]["allow_extra_fields"] is True


class TestConfigEnvVarParsing:
    """Test env var parsing at class level."""

    _DEFAULT_ENV = TestConfigValidate._DEFAULT_ENV

    def _fresh_config(self, env_overrides: dict[str, str] | None = None):
        import importlib
        import toolkit_data_contracts_drift.config as cfg_mod

        env = {**self._DEFAULT_ENV}
        if env_overrides:
            env.update(env_overrides)
        with patch.dict(os.environ, env, clear=False):
            importlib.reload(cfg_mod)
        return cfg_mod.Config

    def test_boolean_env_true(self):
        """Boolean env vars parse 'true' correctly."""
        Config = self._fresh_config({"VERBOSE": "true"})
        assert Config.VERBOSE is True

    def test_boolean_env_false(self):
        """Boolean env vars parse 'false' correctly."""
        Config = self._fresh_config({"VERBOSE": "false"})
        assert Config.VERBOSE is False

    def test_boolean_env_case_insensitive(self):
        """Boolean env vars are case-insensitive."""
        Config = self._fresh_config({"VERBOSE": "TRUE"})
        assert Config.VERBOSE is True

    def test_log_file_none_by_default(self):
        """LOG_FILE is None when not set."""
        Config = self._fresh_config()
        assert Config.LOG_FILE is None

    def test_log_file_set(self):
        """LOG_FILE reflects env var."""
        Config = self._fresh_config({"LOG_FILE": "/tmp/test.log"})
        assert Config.LOG_FILE == "/tmp/test.log"

    def test_output_format_default(self):
        """OUTPUT_FORMAT defaults to 'json'."""
        Config = self._fresh_config()
        assert Config.OUTPUT_FORMAT == "json"
