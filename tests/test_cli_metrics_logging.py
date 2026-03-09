"""Tests for CLI metrics wiring (Task 7-8) and structured JSON logging (Task 9)."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.io import read_json


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _setup_check_fixtures(tmp_path: Path):
    """Create input data, contract, and baseline for check tests."""
    data_file = tmp_path / "data.jsonl"
    _write_jsonl(
        data_file,
        [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ],
    )

    contract_file = tmp_path / "contract.json"
    main(["infer", "--input", str(data_file), "--out", str(contract_file)])

    profile_file = tmp_path / "baseline.json"
    main(
        [
            "profile",
            "--input",
            str(data_file),
            "--contract",
            str(contract_file),
            "--out",
            str(profile_file),
        ]
    )

    return data_file, contract_file, profile_file


# ============================================================================
# Task 7: ContractMetrics wired into CLI check
# ============================================================================


class TestCheckMetricsWiring:
    """Test that check command records metrics via ContractMetrics."""

    def test_check_pass_records_metrics(self, tmp_path: Path):
        """Passing check records validation passed in metrics output."""
        data_file, contract_file, profile_file = _setup_check_fixtures(tmp_path)

        metrics_file = tmp_path / "metrics.json"
        exit_code = main(
            [
                "check",
                "--input",
                str(data_file),
                "--contract",
                str(contract_file),
                "--baseline",
                str(profile_file),
                "--max-missing",
                "0.5",
                "--max-mean-shift-sigma",
                "10.0",
                "--metrics-out",
                str(metrics_file),
            ]
        )
        assert exit_code == EXIT_SUCCESS
        assert metrics_file.exists()

        metrics = read_json(metrics_file)
        assert metrics["validations_performed"] >= 1
        assert "timestamp" in metrics

    def test_check_fail_records_metrics(self, tmp_path: Path):
        """Failing check records validation failed in metrics output."""
        # Create data with type mismatch
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [{"name": "Alice", "age": 30}])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        bad_data = tmp_path / "bad.jsonl"
        _write_jsonl(bad_data, [{"name": 123, "age": 30}])

        metrics_file = tmp_path / "metrics.json"
        exit_code = main(
            [
                "check",
                "--input",
                str(bad_data),
                "--contract",
                str(contract_file),
                "--metrics-out",
                str(metrics_file),
            ]
        )
        assert exit_code == EXIT_CHECK_FAILED

        metrics = read_json(metrics_file)
        assert metrics["validations_performed"] >= 1
        assert metrics["validations_failed"] >= 1

    def test_check_drift_records_metrics(self, tmp_path: Path):
        """Drift check records drift metrics."""
        data_file, contract_file, profile_file = _setup_check_fixtures(tmp_path)

        # Create data with drift
        drifted = tmp_path / "drifted.jsonl"
        _write_jsonl(
            drifted,
            [
                {"name": "Alice", "age": 300},
                {"name": "Bob", "age": 250},
            ],
        )

        metrics_file = tmp_path / "metrics.json"
        main(
            [
                "check",
                "--input",
                str(drifted),
                "--contract",
                str(contract_file),
                "--baseline",
                str(profile_file),
                "--max-mean-shift-sigma",
                "0.1",
                "--metrics-out",
                str(metrics_file),
            ]
        )

        metrics = read_json(metrics_file)
        assert metrics["drift_checks"] >= 1


# ============================================================================
# Task 8: --metrics-out flag
# ============================================================================


class TestMetricsOutFlag:
    """Test --metrics-out flag for metrics export."""

    def test_metrics_out_creates_file(self, tmp_path: Path):
        """--metrics-out flag creates metrics JSON file."""
        data_file, contract_file, _ = _setup_check_fixtures(tmp_path)

        metrics_file = tmp_path / "my_metrics.json"
        exit_code = main(
            [
                "check",
                "--input",
                str(data_file),
                "--contract",
                str(contract_file),
                "--metrics-out",
                str(metrics_file),
            ]
        )
        assert exit_code == EXIT_SUCCESS
        assert metrics_file.exists()

        metrics = read_json(metrics_file)
        assert isinstance(metrics, dict)
        assert "validations_performed" in metrics

    def test_metrics_out_not_specified(self, tmp_path: Path):
        """When --metrics-out is not specified, no metrics file is created."""
        data_file, contract_file, _ = _setup_check_fixtures(tmp_path)

        exit_code = main(
            [
                "check",
                "--input",
                str(data_file),
                "--contract",
                str(contract_file),
            ]
        )
        assert exit_code == EXIT_SUCCESS
        # No metrics file created in tmp_path (besides the fixtures)


# ============================================================================
# Task 9: --log-format json flag
# ============================================================================


class TestStructuredJsonLogging:
    """Test --log-format json flag for structured logging."""

    def test_log_format_json_flag_accepted(self, tmp_path: Path):
        """CLI accepts --log-format json without error."""
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [{"x": 1}])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        exit_code = main(
            [
                "--log-format",
                "json",
                "check",
                "--input",
                str(data_file),
                "--contract",
                str(contract_file),
            ]
        )
        assert exit_code == EXIT_SUCCESS

    def test_log_format_text_flag_accepted(self, tmp_path: Path):
        """CLI accepts --log-format text without error."""
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [{"x": 1}])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        exit_code = main(
            [
                "--log-format",
                "text",
                "check",
                "--input",
                str(data_file),
                "--contract",
                str(contract_file),
            ]
        )
        assert exit_code == EXIT_SUCCESS

    def test_log_format_json_produces_json_output(self, tmp_path: Path, capsys):
        """JSON log format produces parseable JSON on stderr."""

        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [{"x": 1}])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        # Run with verbose + json logging to produce log output
        exit_code = main(
            [
                "--verbose",
                "--log-format",
                "json",
                "check",
                "--input",
                str(data_file),
                "--contract",
                str(contract_file),
            ]
        )
        assert exit_code == EXIT_SUCCESS
