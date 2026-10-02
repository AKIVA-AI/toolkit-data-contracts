"""Nested objects: inference, validation and CLI checks at nested paths."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.contract import infer_contract, validate_records


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _issues(contract, records, **kw):
    return [
        (i.kind, i.field, i.message)
        for i in validate_records(contract=contract, records=records, **kw)
    ]


class TestInferNestedProperties:
    def test_object_field_records_its_keys(self):
        c = infer_contract([{"meta": {"a": 1, "b": "x"}}, {"meta": {"a": 2}}])
        meta = c["schema"]["properties"]["meta"]
        assert meta["properties"] == {"a": {"type": "integer"}, "b": {"type": "string"}}
        assert meta["required"] == ["a"]

    def test_non_object_field_has_no_properties(self):
        c = infer_contract([{"x": 1}])
        assert c["schema"]["properties"]["x"] == {"type": "integer"}

    def test_required_is_relative_to_object_occurrences(self):
        """A nullable object field: sub-key required counts only object values."""
        c = infer_contract([{"m": {"k": 1}}, {"m": None}])
        m = c["schema"]["properties"]["m"]
        assert m["required"] == ["k"]
        assert m["type"] == ["null", "object"]

    def test_every_level_is_described(self):
        c = infer_contract([{"m": {"inner": {"deep": 1}}}])
        inner = c["schema"]["properties"]["m"]["properties"]["inner"]
        assert inner == {
            "type": "object",
            "properties": {"deep": {"type": "integer"}},
            "required": ["deep"],
            "additionalProperties": True,
        }


class TestValidateNested:
    def test_verdict_probe_nested_key_change_is_detected(self):
        """emb: {"a": 1} changed to {"zzz": "str"} used to pass silently."""
        c = infer_contract([{"emb": {"a": 1}}])
        issues = _issues(c, [{"emb": {"zzz": "str"}}])
        assert ("missing_required", "emb.a", "missing_required") in issues

    def test_nested_type_change_is_detected(self):
        c = infer_contract([{"emb": {"a": 1}}])
        assert _issues(c, [{"emb": {"a": "one"}}]) == [
            ("type_mismatch", "emb.a", "type_mismatch:string")
        ]

    def test_nested_numeric_compat(self):
        c = infer_contract([{"emb": {"a": 1}}])
        assert _issues(c, [{"emb": {"a": 1.5}}]) == []
        assert _issues(c, [{"emb": {"a": 1.5}}], strict_integer=True) == [
            ("type_mismatch", "emb.a", "type_mismatch:number")
        ]

    def test_new_nested_key_rejected_when_extras_disallowed(self):
        c = infer_contract([{"emb": {"a": 1}}], allow_extra_fields=False)
        issues = _issues(c, [{"emb": {"a": 1, "zzz": 2}}])
        assert issues == [("unexpected_field", "emb.zzz", "unexpected_field")]

    def test_new_nested_key_allowed_by_default(self):
        c = infer_contract([{"emb": {"a": 1}}])
        assert _issues(c, [{"emb": {"a": 1, "zzz": 2}}]) == []

    def test_optional_nested_key_may_be_absent(self):
        c = infer_contract([{"m": {"a": 1, "b": 2}}, {"m": {"a": 1}}])
        assert _issues(c, [{"m": {"a": 5}}]) == []

    def test_null_object_value_skips_nested_checks(self):
        c = infer_contract([{"m": {"k": 1}}, {"m": None}])
        assert _issues(c, [{"m": None}]) == []

    def test_old_contract_without_properties_still_validates(self):
        c = {
            "version": 1,
            "allow_extra_fields": True,
            "fields": {"m": {"types": ["object"], "required": True}},
        }
        assert _issues(c, [{"m": {"anything": 1}}]) == []

    def test_issue_counts_aggregate_across_records(self):
        c = infer_contract([{"emb": {"a": 1}}])
        issues = validate_records(contract=c, records=[{"emb": {}}, {"emb": {}}])
        assert [(i.field, i.count) for i in issues] == [("emb.a", 2)]


class TestCliNested:
    def test_check_fails_on_nested_change(self, tmp_path: Path):
        sample = tmp_path / "sample.jsonl"
        _write_jsonl(sample, [{"emb": {"a": 1}}])
        contract = tmp_path / "contract.json"
        assert main(["infer", "--input", str(sample), "--out", str(contract)]) == EXIT_SUCCESS
        batch = tmp_path / "batch.jsonl"
        _write_jsonl(batch, [{"emb": {"zzz": "str"}}])
        code = main(["check", "--input", str(batch), "--contract", str(contract)])
        assert code == EXIT_CHECK_FAILED

    def test_check_passes_on_same_nested_shape(self, tmp_path: Path):
        sample = tmp_path / "sample.jsonl"
        _write_jsonl(sample, [{"emb": {"a": 1}}])
        contract = tmp_path / "contract.json"
        assert main(["infer", "--input", str(sample), "--out", str(contract)]) == EXIT_SUCCESS
        code = main(["check", "--input", str(sample), "--contract", str(contract)])
        assert code == EXIT_SUCCESS
