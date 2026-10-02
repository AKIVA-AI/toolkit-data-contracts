"""JSON has one numeric type. A field inferred from whole-number samples must
accept 10.5, and a "number" field must accept 7, unless strict integer mode is on.
"""

from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.contract import infer_contract, validate_records


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class TestIntegerNumberCompatibility:
    def test_float_accepted_on_field_inferred_from_integers(self):
        contract = infer_contract([{"price": 10}, {"price": 12}])
        issues = validate_records(contract=contract, records=[{"price": 10.5}])
        assert issues == []

    def test_integer_accepted_on_number_field(self):
        contract = infer_contract([{"score": 0.5}, {"score": 1.5}])
        issues = validate_records(contract=contract, records=[{"score": 7}])
        assert issues == []

    def test_string_still_rejected_on_numeric_field(self):
        contract = infer_contract([{"price": 10}])
        issues = validate_records(contract=contract, records=[{"price": "10"}])
        assert [(i.kind, i.field, i.message) for i in issues] == [
            ("type_mismatch", "price", "type_mismatch:string")
        ]

    def test_boolean_still_rejected_on_numeric_field(self):
        contract = infer_contract([{"price": 10}])
        issues = validate_records(contract=contract, records=[{"price": True}])
        assert issues[0].message == "type_mismatch:boolean"

    def test_strict_integer_rejects_float(self):
        contract = infer_contract([{"count": 3}])
        issues = validate_records(contract=contract, records=[{"count": 3.5}], strict_integer=True)
        assert [(i.kind, i.field, i.message) for i in issues] == [
            ("type_mismatch", "count", "type_mismatch:number")
        ]

    def test_strict_integer_still_accepts_integer_on_number_field(self):
        """Every integer is a JSON number, even in strict mode."""
        contract = infer_contract([{"score": 0.5}])
        issues = validate_records(contract=contract, records=[{"score": 2}], strict_integer=True)
        assert issues == []


class TestCliStrictInteger:
    def _setup(self, tmp_path: Path) -> tuple[Path, Path]:
        sample = tmp_path / "sample.jsonl"
        _write_jsonl(sample, [{"n": 1}, {"n": 2}])
        contract = tmp_path / "contract.json"
        assert main(["infer", "--input", str(sample), "--out", str(contract)]) == EXIT_SUCCESS
        batch = tmp_path / "batch.jsonl"
        _write_jsonl(batch, [{"n": 10.5}])
        return contract, batch

    def test_check_passes_float_by_default(self, tmp_path: Path):
        contract, batch = self._setup(tmp_path)
        code = main(["check", "--input", str(batch), "--contract", str(contract)])
        assert code == EXIT_SUCCESS

    def test_check_fails_float_with_strict_integer(self, tmp_path: Path):
        contract, batch = self._setup(tmp_path)
        code = main(
            ["check", "--input", str(batch), "--contract", str(contract), "--strict-integer"]
        )
        assert code == EXIT_CHECK_FAILED
