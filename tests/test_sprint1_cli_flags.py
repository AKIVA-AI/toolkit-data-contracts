"""Tests for Sprint 1 CLI additions: --version flag and --format flag."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit_data_contracts_drift import __version__
from toolkit_data_contracts_drift.cli import main


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class TestVersionFlag:
    """Test --version CLI flag."""

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--version prints version string and exits."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_version_contains_semver(self) -> None:
        """Version string looks like semver."""
        parts = __version__.split(".")
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit()


class TestFormatFlag:
    """Test --format flag on check command."""

    @pytest.fixture()
    def setup_files(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Create input JSONL, contract, and baseline files."""
        data_path = tmp_path / "data.jsonl"
        _write_jsonl(data_path, [
            {"name": "Alice", "score": 90},
            {"name": "Bob", "score": 85},
        ])
        contract_path = tmp_path / "contract.json"
        assert main(["infer", "--input", str(data_path), "--out", str(contract_path)]) == 0

        profile_path = tmp_path / "baseline.json"
        assert main([
            "profile",
            "--input", str(data_path),
            "--contract", str(contract_path),
            "--out", str(profile_path),
        ]) == 0
        return data_path, contract_path, profile_path

    def test_format_json_default(
        self, tmp_path: Path, setup_files: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Default format is JSON."""
        data_path, contract_path, profile_path = setup_files
        code = main([
            "check",
            "--input", str(data_path),
            "--contract", str(contract_path),
            "--baseline", str(profile_path),
            "--max-missing", "0.5",
            "--max-mean-shift-sigma", "10.0",
        ])
        assert code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["ok"] is True

    def test_format_json_explicit(
        self, tmp_path: Path, setup_files: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--format json produces valid JSON output."""
        data_path, contract_path, profile_path = setup_files
        code = main([
            "check",
            "--input", str(data_path),
            "--contract", str(contract_path),
            "--baseline", str(profile_path),
            "--max-missing", "0.5",
            "--max-mean-shift-sigma", "10.0",
            "--format", "json",
        ])
        assert code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["ok"] is True

    def test_format_table(
        self, tmp_path: Path, setup_files: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--format table produces human-readable table."""
        data_path, contract_path, profile_path = setup_files
        code = main([
            "check",
            "--input", str(data_path),
            "--contract", str(contract_path),
            "--baseline", str(profile_path),
            "--max-missing", "0.5",
            "--max-mean-shift-sigma", "10.0",
            "--format", "table",
        ])
        assert code == 0
        captured = capsys.readouterr()
        assert "Status: PASS" in captured.out
        assert "Validation: OK" in captured.out
        assert "Drift: OK" in captured.out

    def test_format_table_with_failures(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--format table shows issues when check fails."""
        data_path = tmp_path / "data.jsonl"
        _write_jsonl(data_path, [{"name": "Alice", "score": 90}])
        contract_path = tmp_path / "contract.json"
        assert main(["infer", "--input", str(data_path), "--out", str(contract_path)]) == 0

        bad_path = tmp_path / "bad.jsonl"
        _write_jsonl(bad_path, [{"name": 123, "score": 90}])

        code = main([
            "check",
            "--input", str(bad_path),
            "--contract", str(contract_path),
            "--format", "table",
        ])
        assert code == 4
        captured = capsys.readouterr()
        assert "Status: FAIL" in captured.out
        assert "Validation Issues:" in captured.out
        assert "type_mismatch" in captured.out

    def test_format_table_to_file(
        self, tmp_path: Path, setup_files: tuple[Path, Path, Path]
    ) -> None:
        """--format table writes table to file with --out."""
        data_path, contract_path, profile_path = setup_files
        out_path = tmp_path / "report.txt"
        code = main([
            "check",
            "--input", str(data_path),
            "--contract", str(contract_path),
            "--baseline", str(profile_path),
            "--max-missing", "0.5",
            "--max-mean-shift-sigma", "10.0",
            "--format", "table",
            "--out", str(out_path),
        ])
        assert code == 0
        content = out_path.read_text(encoding="utf-8")
        assert "Status: PASS" in content
