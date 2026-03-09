"""Tests for profile CLI subcommand — Task 5: Exercise profile command end-to-end."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.cli import EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.io import read_json


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class TestProfileCLI:
    """Test the profile CLI subcommand end-to-end."""

    def test_profile_success(self, tmp_path: Path):
        """Profile command succeeds with valid input and contract."""
        # Create input data
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [
            {"name": "Alice", "age": 30, "score": 95.5},
            {"name": "Bob", "age": 25, "score": 88.0},
            {"name": "Charlie", "age": 35, "score": 92.3},
        ])

        # Create contract
        contract_file = tmp_path / "contract.json"
        exit_code = main(["infer", "--input", str(data_file), "--out", str(contract_file)])
        assert exit_code == EXIT_SUCCESS

        # Run profile
        profile_file = tmp_path / "profile.json"
        exit_code = main([
            "profile",
            "--input", str(data_file),
            "--contract", str(contract_file),
            "--out", str(profile_file),
        ])
        assert exit_code == EXIT_SUCCESS
        assert profile_file.exists()

        # Verify profile structure
        profile = read_json(profile_file)
        assert profile["version"] == 1
        assert "field_stats" in profile
        assert "name" in profile["field_stats"]
        assert "age" in profile["field_stats"]
        assert "score" in profile["field_stats"]

    def test_profile_numeric_stats(self, tmp_path: Path):
        """Profile computes numeric stats for numeric fields."""
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [
            {"value": 10},
            {"value": 20},
            {"value": 30},
        ])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        profile_file = tmp_path / "profile.json"
        exit_code = main([
            "profile",
            "--input", str(data_file),
            "--contract", str(contract_file),
            "--out", str(profile_file),
        ])
        assert exit_code == EXIT_SUCCESS

        profile = read_json(profile_file)
        numeric = profile["field_stats"]["value"]["numeric"]
        assert numeric["count"] == 3
        assert numeric["mean"] == 20.0
        assert numeric["min"] == 10
        assert numeric["max"] == 30

    def test_profile_with_limit(self, tmp_path: Path):
        """Profile command respects --limit flag."""
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [{"x": i} for i in range(100)])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        profile_file = tmp_path / "profile.json"
        exit_code = main([
            "profile",
            "--input", str(data_file),
            "--contract", str(contract_file),
            "--out", str(profile_file),
            "--limit", "10",
        ])
        assert exit_code == EXIT_SUCCESS

    def test_profile_contract_not_found(self, tmp_path: Path):
        """Profile fails when contract file doesn't exist."""
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [{"x": 1}])

        exit_code = main([
            "profile",
            "--input", str(data_file),
            "--contract", str(tmp_path / "missing.json"),
            "--out", str(tmp_path / "profile.json"),
        ])
        assert exit_code == EXIT_CLI_ERROR

    def test_profile_input_not_found(self, tmp_path: Path):
        """Profile fails when input file doesn't exist."""
        contract_file = tmp_path / "contract.json"
        contract_file.write_text(
            json.dumps({"version": 1, "fields": {"x": {"types": ["integer"]}}}),
            encoding="utf-8",
        )

        exit_code = main([
            "profile",
            "--input", str(tmp_path / "missing.jsonl"),
            "--contract", str(contract_file),
            "--out", str(tmp_path / "profile.json"),
        ])
        assert exit_code == EXIT_CLI_ERROR

    def test_profile_missing_rate(self, tmp_path: Path):
        """Profile computes missing rate for partially-present fields."""
        data_file = tmp_path / "data.jsonl"
        _write_jsonl(data_file, [
            {"name": "Alice", "age": 30},
            {"name": "Bob"},
            {"name": "Charlie", "age": 35},
        ])

        contract_file = tmp_path / "contract.json"
        main(["infer", "--input", str(data_file), "--out", str(contract_file)])

        profile_file = tmp_path / "profile.json"
        exit_code = main([
            "profile",
            "--input", str(data_file),
            "--contract", str(contract_file),
            "--out", str(profile_file),
        ])
        assert exit_code == EXIT_SUCCESS

        profile = read_json(profile_file)
        # "age" is missing from 1 out of 3 records
        age_missing = profile["field_stats"]["age"]["missing_rate"]
        assert abs(age_missing - 1.0 / 3.0) < 1e-9
