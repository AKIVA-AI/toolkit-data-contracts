"""Fail-closed input handling: full-file inference, non-finite numbers, output paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit_data_contracts_drift.cli import EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.io import read_json, read_jsonl


class TestInferReadsWholeFile:
    def test_optional_field_after_row_5000_is_not_required(self, tmp_path: Path):
        """infer used to stop at 5000 rows and mark later-optional fields required."""
        rows = [{"id": i, "opt": 1} for i in range(6000)]
        del rows[5500]["opt"]
        data = tmp_path / "data.jsonl"
        data.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        out = tmp_path / "contract.json"
        assert main(["infer", "--input", str(data), "--out", str(out)]) == EXIT_SUCCESS
        assert "opt" not in read_json(out)["schema"]["required"]

    def test_explicit_limit_still_applies(self, tmp_path: Path):
        rows = [{"a": 1}, {"a": 1}, {"b": 1}]
        data = tmp_path / "data.jsonl"
        data.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        out = tmp_path / "contract.json"
        assert main(["infer", "--input", str(data), "--out", str(out), "--limit", "2"]) == 0
        assert set(read_json(out)["schema"]["properties"]) == {"a"}


class TestNonFiniteNumbersRejected:
    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
    def test_read_jsonl_rejects_non_finite(self, tmp_path: Path, literal: str):
        data = tmp_path / "data.jsonl"
        data.write_text('{"x": 1}\n{"x": ' + literal + "}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="line 2"):
            list(read_jsonl(data))

    def test_read_json_rejects_nan(self, tmp_path: Path):
        p = tmp_path / "profile.json"
        p.write_text('{"version": 1, "field_stats": {"x": {"numeric": {"mean": NaN}}}}')
        with pytest.raises(ValueError):
            read_json(p)

    def test_check_with_nan_batch_is_cli_error(self, tmp_path: Path):
        sample = tmp_path / "sample.jsonl"
        sample.write_text('{"x": 1}\n{"x": 2}\n', encoding="utf-8")
        contract = tmp_path / "contract.json"
        assert main(["infer", "--input", str(sample), "--out", str(contract)]) == EXIT_SUCCESS
        batch = tmp_path / "batch.jsonl"
        batch.write_text('{"x": NaN}\n', encoding="utf-8")
        code = main(["check", "--input", str(batch), "--contract", str(contract)])
        assert code == EXIT_CLI_ERROR


class TestCheckOutPathPolicy:
    def test_check_out_uses_same_path_policy_as_other_outputs(self, tmp_path: Path):
        """check --out bypassed the '..' guard that infer/profile --out apply."""
        sample = tmp_path / "sample.jsonl"
        sample.write_text('{"x": 1}\n', encoding="utf-8")
        contract = tmp_path / "contract.json"
        assert main(["infer", "--input", str(sample), "--out", str(contract)]) == EXIT_SUCCESS
        (tmp_path / "sub").mkdir()
        traversal = str(tmp_path / "sub" / ".." / "report.json")
        code = main(
            ["check", "--input", str(sample), "--contract", str(contract), "--out", traversal]
        )
        assert code == EXIT_CLI_ERROR
        assert not (tmp_path / "report.json").exists()
