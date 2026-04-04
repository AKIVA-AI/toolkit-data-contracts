"""Tests for schema validation edge cases, contract inference boundaries,
Profile serialisation round-trips, and IO error paths.

Targets uncovered branches in contract.py, cli.py, and io.py to raise
the Testing dimension from 6 to 7+.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from toolkit_data_contracts_drift.cli import (
    EXIT_CHECK_FAILED,
    EXIT_CLI_ERROR,
    EXIT_SUCCESS,
    _format_table,
    _JsonLogFormatter,
    build_parser,
    main,
)
from toolkit_data_contracts_drift.contract import (
    Profile,
    drift_check,
    infer_contract,
    profile_records,
    validate_records,
)
from toolkit_data_contracts_drift.io import (
    read_json,
    read_jsonl,
    validate_path_for_write,
    write_json,
)
from toolkit_data_contracts_drift.types import ValidationIssue


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


# ============================================================================
# Contract inference edge cases
# ============================================================================


class TestInferContractEdgeCases:
    """Edge cases for infer_contract()."""

    def test_empty_records(self):
        """Inferring from empty list yields empty fields."""
        c = infer_contract([])
        assert c["fields"] == {}
        assert c["version"] == 1

    def test_single_record(self):
        """Single record: all fields required."""
        c = infer_contract([{"a": 1}])
        assert c["fields"]["a"]["required"] is True
        assert "integer" in c["fields"]["a"]["types"]

    def test_mixed_types_in_same_field(self):
        """Field with multiple types across records."""
        c = infer_contract([{"x": 1}, {"x": "hello"}, {"x": None}])
        types = set(c["fields"]["x"]["types"])
        assert types == {"integer", "string", "null"}

    def test_optional_field(self):
        """Field present in only some records is not required."""
        c = infer_contract([{"a": 1, "b": 2}, {"a": 3}])
        assert c["fields"]["a"]["required"] is True
        assert c["fields"]["b"]["required"] is False

    def test_disallow_extra_fields(self):
        c = infer_contract([{"a": 1}], allow_extra_fields=False)
        assert c["allow_extra_fields"] is False

    def test_allow_extra_fields_default(self):
        c = infer_contract([{"a": 1}])
        assert c["allow_extra_fields"] is True

    def test_boolean_not_integer(self):
        """Python bools are int subclasses but should map to boolean."""
        c = infer_contract([{"flag": True}])
        assert "boolean" in c["fields"]["flag"]["types"]
        assert "integer" not in c["fields"]["flag"]["types"]

    def test_nested_objects_and_arrays(self):
        """Nested dicts/lists map to object/array types."""
        c = infer_contract([{"obj": {"nested": 1}, "arr": [1, 2]}])
        assert "object" in c["fields"]["obj"]["types"]
        assert "array" in c["fields"]["arr"]["types"]

    def test_many_fields(self):
        """Contract with many fields."""
        record = {f"field_{i}": i for i in range(50)}
        c = infer_contract([record])
        assert len(c["fields"]) == 50

    def test_null_only_field(self):
        """Field that is always None."""
        c = infer_contract([{"x": None}, {"x": None}])
        assert c["fields"]["x"]["types"] == ["null"]
        assert c["fields"]["x"]["required"] is True


# ============================================================================
# Validate records edge cases
# ============================================================================


class TestValidateRecordsEdgeCases:
    """Edge cases for validate_records()."""

    def test_no_records(self):
        """Empty records list yields no issues."""
        contract = {
            "version": 1,
            "allow_extra_fields": True,
            "fields": {"a": {"types": ["integer"], "required": True}},
        }
        issues = validate_records(contract=contract, records=[])
        assert issues == []

    def test_missing_required_field(self):
        """Required field absent raises missing_required issue."""
        contract = {
            "version": 1,
            "allow_extra_fields": True,
            "fields": {"a": {"types": ["string"], "required": True}},
        }
        issues = validate_records(contract=contract, records=[{"b": 1}])
        assert len(issues) == 1
        assert issues[0].kind == "missing_required"
        assert issues[0].field == "a"

    def test_unexpected_field_when_disallowed(self):
        """Extra field when allow_extra_fields=False raises unexpected_field."""
        contract = {
            "version": 1,
            "allow_extra_fields": False,
            "fields": {"a": {"types": ["string"], "required": False}},
        }
        issues = validate_records(contract=contract, records=[{"a": "ok", "extra": 1}])
        unexpected = [i for i in issues if i.kind == "unexpected_field"]
        assert len(unexpected) == 1
        assert unexpected[0].field == "extra"

    def test_unexpected_field_allowed(self):
        """Extra field when allow_extra_fields=True yields no issue."""
        contract = {
            "version": 1,
            "allow_extra_fields": True,
            "fields": {"a": {"types": ["string"], "required": False}},
        }
        issues = validate_records(contract=contract, records=[{"a": "ok", "extra": 1}])
        assert issues == []

    def test_type_mismatch_count_aggregated(self):
        """Multiple type mismatches for same field aggregate into count."""
        contract = {
            "version": 1,
            "allow_extra_fields": True,
            "fields": {"a": {"types": ["integer"], "required": False}},
        }
        issues = validate_records(contract=contract, records=[{"a": "x"}, {"a": "y"}, {"a": "z"}])
        assert len(issues) == 1
        assert issues[0].count == 3

    def test_multiple_issue_types(self):
        """A single record can produce multiple issue types."""
        contract = {
            "version": 1,
            "allow_extra_fields": False,
            "fields": {
                "name": {"types": ["string"], "required": True},
                "age": {"types": ["integer"], "required": True},
            },
        }
        records = [{"age": "wrong_type", "unexpected": True}]
        issues = validate_records(contract=contract, records=records)
        kinds = {i.kind for i in issues}
        assert "missing_required" in kinds
        assert "type_mismatch" in kinds
        assert "unexpected_field" in kinds

    def test_contract_with_no_fields_key(self):
        """Contract with missing fields key uses empty dict."""
        contract = {"version": 1, "allow_extra_fields": True}
        issues = validate_records(contract=contract, records=[{"a": 1}])
        assert issues == []

    def test_field_with_no_types_key(self):
        """Field contract with missing types key uses empty set."""
        contract = {"version": 1, "allow_extra_fields": True, "fields": {"a": {"required": False}}}
        issues = validate_records(contract=contract, records=[{"a": 1}])
        # integer not in empty set -> type_mismatch
        assert len(issues) == 1
        assert issues[0].kind == "type_mismatch"


# ============================================================================
# Profile serialisation
# ============================================================================


class TestProfileSerialisation:
    """Test Profile.to_json / from_json round-trip and error paths."""

    def test_round_trip(self):
        p = Profile(version=1, field_stats={"age": {"missing_rate": 0.0}})
        j = p.to_json()
        p2 = Profile.from_json(j)
        assert p2.version == p.version
        assert p2.field_stats == p.field_stats

    def test_from_json_not_dict(self):
        with pytest.raises(ValueError, match="profile_not_object"):
            Profile.from_json("not a dict")

    def test_from_json_missing_field_stats(self):
        with pytest.raises(ValueError, match="profile_missing_field_stats"):
            Profile.from_json({"version": 1})

    def test_from_json_field_stats_not_dict(self):
        with pytest.raises(ValueError, match="profile_missing_field_stats"):
            Profile.from_json({"version": 1, "field_stats": "bad"})

    def test_from_json_no_version_defaults_to_zero(self):
        p = Profile.from_json({"field_stats": {"x": {"missing_rate": 0.0}}})
        assert p.version == 0

    def test_to_json_types(self):
        p = Profile(version=1, field_stats={"x": {"a": 1}})
        j = p.to_json()
        assert isinstance(j["version"], int)
        assert isinstance(j["field_stats"], dict)


# ============================================================================
# Profile records edge cases
# ============================================================================


class TestProfileRecordsExtended:
    """Extended tests for profile_records."""

    def test_mixed_numeric_and_string(self):
        """Field with mix of numeric and string values only profiles numeric ones."""
        contract = {"version": 1, "fields": {"val": {"types": ["integer", "string"]}}}
        records = [{"val": 10}, {"val": "abc"}, {"val": 20}]
        prof = profile_records(contract=contract, records=records)
        stats = prof.field_stats["val"]
        assert stats["numeric"]["count"] == 2
        assert stats["numeric"]["mean"] == 15.0

    def test_float_values(self):
        """Float values are captured as numeric."""
        contract = {"version": 1, "fields": {"val": {"types": ["number"]}}}
        records = [{"val": 1.5}, {"val": 2.5}]
        prof = profile_records(contract=contract, records=records)
        assert prof.field_stats["val"]["numeric"]["mean"] == 2.0

    def test_type_counts(self):
        """Type counts are correctly tracked."""
        contract = {"version": 1, "fields": {"x": {"types": ["integer", "string"]}}}
        records = [{"x": 1}, {"x": 2}, {"x": "a"}]
        prof = profile_records(contract=contract, records=records)
        tc = prof.field_stats["x"]["type_counts"]
        assert tc["integer"] == 2
        assert tc["string"] == 1

    def test_field_not_in_contract_ignored(self):
        """Fields in records but not in contract are ignored by profile."""
        contract = {"version": 1, "fields": {"a": {"types": ["integer"]}}}
        records = [{"a": 1, "b": 2}]
        prof = profile_records(contract=contract, records=records)
        assert "b" not in prof.field_stats


# ============================================================================
# Drift check extended
# ============================================================================


class TestDriftCheckExtended:
    """Additional drift_check scenarios."""

    def test_both_missing_and_mean_shift(self):
        """A single field can trigger both missing rate and mean shift drift."""
        baseline = Profile(
            version=1,
            field_stats={
                "x": {
                    "missing_rate": 0.0,
                    "numeric": {"count": 100, "mean": 10.0, "std": 1.0, "min": 0, "max": 20},
                }
            },
        )
        current = Profile(
            version=1,
            field_stats={
                "x": {
                    "missing_rate": 0.5,
                    "numeric": {"count": 50, "mean": 50.0, "std": 1.0, "min": 0, "max": 100},
                }
            },
        )
        issues = drift_check(
            baseline=baseline,
            current=current,
            max_missing_rate=0.01,
            max_mean_shift_sigma=3.0,
        )
        kinds = {i.kind for i in issues}
        assert "drift_missing_rate" in kinds
        assert "drift_mean_shift" in kinds

    def test_custom_thresholds(self):
        """Custom thresholds change detection sensitivity."""
        baseline = Profile(
            version=1,
            field_stats={
                "x": {
                    "missing_rate": 0.0,
                    "numeric": {"count": 100, "mean": 10.0, "std": 2.0, "min": 0, "max": 20},
                }
            },
        )
        current = Profile(
            version=1,
            field_stats={
                "x": {
                    "missing_rate": 0.0,
                    "numeric": {"count": 100, "mean": 15.0, "std": 2.0, "min": 0, "max": 30},
                }
            },
        )
        # 5 / 2 = 2.5 sigma -> below 3.0
        no_issues = drift_check(baseline=baseline, current=current, max_mean_shift_sigma=3.0)
        assert len(no_issues) == 0
        # 5 / 2 = 2.5 sigma -> above 2.0
        with_issues = drift_check(baseline=baseline, current=current, max_mean_shift_sigma=2.0)
        assert len(with_issues) == 1

    def test_multiple_fields_drift(self):
        """Drift detected across multiple fields."""
        num_a = {"count": 10, "mean": 10, "std": 1, "min": 0, "max": 20}
        num_b = {"count": 10, "mean": 20, "std": 1, "min": 0, "max": 40}
        baseline = Profile(
            version=1,
            field_stats={
                "a": {"missing_rate": 0.0, "numeric": num_a},
                "b": {"missing_rate": 0.0, "numeric": num_b},
            },
        )
        cur_a = {"count": 10, "mean": 100, "std": 1, "min": 0, "max": 200}
        cur_b = {"count": 10, "mean": 200, "std": 1, "min": 0, "max": 400}
        current = Profile(
            version=1,
            field_stats={
                "a": {"missing_rate": 0.0, "numeric": cur_a},
                "b": {"missing_rate": 0.0, "numeric": cur_b},
            },
        )
        issues = drift_check(
            baseline=baseline,
            current=current,
            max_mean_shift_sigma=3.0,
        )
        fields_with_drift = {i.field for i in issues}
        assert "a" in fields_with_drift
        assert "b" in fields_with_drift


# ============================================================================
# ValidationIssue
# ============================================================================


class TestValidationIssue:
    """Test the ValidationIssue dataclass."""

    def test_default_count(self):
        v = ValidationIssue(kind="test", field="f", message="msg")
        assert v.count == 1

    def test_frozen(self):
        v = ValidationIssue(kind="test", field="f", message="msg")
        with pytest.raises(AttributeError):
            v.kind = "changed"  # type: ignore[misc]


# ============================================================================
# CLI _JsonLogFormatter
# ============================================================================


class TestJsonLogFormatterCli:
    """Test the CLI-level _JsonLogFormatter."""

    def _make_record(self, msg: str = "hi") -> logging.LogRecord:
        return logging.LogRecord(
            name="cli",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_output_is_json(self):
        fmt = _JsonLogFormatter()
        rec = self._make_record()
        parsed = json.loads(fmt.format(rec))
        assert parsed["message"] == "hi"
        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "cli"

    def test_with_exception(self):
        fmt = _JsonLogFormatter()
        try:
            raise RuntimeError("err")
        except RuntimeError:
            import sys

            rec = self._make_record()
            rec.exc_info = sys.exc_info()
        parsed = json.loads(fmt.format(rec))
        assert parsed["exception"] == "err"

    def test_no_exception(self):
        fmt = _JsonLogFormatter()
        rec = self._make_record()
        parsed = json.loads(fmt.format(rec))
        assert "exception" not in parsed


# ============================================================================
# CLI _format_table
# ============================================================================


class TestFormatTable:
    """Test _format_table helper."""

    def test_pass_no_issues(self):
        report = {"ok": True, "validation_issues": [], "drift_issues": []}
        text = _format_table(report)
        assert "Status: PASS" in text
        assert "Validation: OK" in text
        assert "Drift: OK" in text

    def test_fail_with_validation_issues(self):
        report = {
            "ok": False,
            "validation_issues": [
                {
                    "kind": "type_mismatch",
                    "field": "age",
                    "count": 2,
                    "message": "type_mismatch:string",
                },
            ],
            "drift_issues": [],
        }
        text = _format_table(report)
        assert "Status: FAIL" in text
        assert "Validation Issues:" in text
        assert "type_mismatch" in text
        assert "age" in text

    def test_fail_with_drift_issues(self):
        report = {
            "ok": False,
            "validation_issues": [],
            "drift_issues": [
                {"kind": "drift_mean_shift", "field": "score", "count": 1, "message": "shift"},
            ],
        }
        text = _format_table(report)
        assert "Drift Issues:" in text
        assert "drift_mean_shift" in text


# ============================================================================
# CLI build_parser
# ============================================================================


class TestBuildParser:
    """Test CLI argument parser construction."""

    def test_parser_has_subcommands(self):
        p = build_parser()
        # Parsing with no args should fail (cmd is required)
        with pytest.raises(SystemExit):
            p.parse_args([])

    def test_infer_subcommand(self):
        p = build_parser()
        args = p.parse_args(["infer", "--input", "in.jsonl", "--out", "out.json"])
        assert args.cmd == "infer"
        assert args.input == "in.jsonl"

    def test_profile_subcommand(self):
        p = build_parser()
        args = p.parse_args(
            [
                "profile",
                "--input",
                "in.jsonl",
                "--contract",
                "c.json",
                "--out",
                "p.json",
            ]
        )
        assert args.cmd == "profile"

    def test_check_subcommand_defaults(self):
        p = build_parser()
        args = p.parse_args(["check", "--input", "in.jsonl", "--contract", "c.json"])
        assert args.cmd == "check"
        assert args.max_missing == "0.01"
        assert args.max_mean_shift_sigma == "3.0"

    def test_verbose_flag(self):
        p = build_parser()
        args = p.parse_args(["--verbose", "infer", "--input", "in.jsonl", "--out", "out.json"])
        assert args.verbose is True

    def test_log_format_flag(self):
        p = build_parser()
        args = p.parse_args(
            [
                "--log-format",
                "json",
                "infer",
                "--input",
                "in.jsonl",
                "--out",
                "out.json",
            ]
        )
        assert args.log_format == "json"


# ============================================================================
# CLI end-to-end error paths
# ============================================================================


class TestCliErrorPaths:
    """Test CLI error handling paths."""

    def test_infer_disallow_extra(self, tmp_path: Path):
        """--disallow-extra flag sets allow_extra_fields=False."""
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"a": 1}])
        out = tmp_path / "contract.json"
        code = main(["infer", "--input", str(data), "--out", str(out), "--disallow-extra"])
        assert code == EXIT_SUCCESS
        c = read_json(out)
        assert c["allow_extra_fields"] is False

    def test_infer_with_limit(self, tmp_path: Path):
        """--limit restricts number of records processed."""
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"x": i} for i in range(100)])
        out = tmp_path / "contract.json"
        code = main(["infer", "--input", str(data), "--out", str(out), "--limit", "5"])
        assert code == EXIT_SUCCESS

    def test_check_baseline_not_found(self, tmp_path: Path):
        """Check with missing baseline returns CLI error."""
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"x": 1}])
        contract = tmp_path / "contract.json"
        main(["infer", "--input", str(data), "--out", str(contract)])

        code = main(
            [
                "check",
                "--input",
                str(data),
                "--contract",
                str(contract),
                "--baseline",
                str(tmp_path / "missing_baseline.json"),
            ]
        )
        assert code == EXIT_CLI_ERROR

    def test_check_with_out_file(self, tmp_path: Path):
        """Check writes report to --out file."""
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"x": 1}])
        contract = tmp_path / "contract.json"
        main(["infer", "--input", str(data), "--out", str(contract)])

        report = tmp_path / "report.json"
        code = main(
            [
                "check",
                "--input",
                str(data),
                "--contract",
                str(contract),
                "--out",
                str(report),
            ]
        )
        assert code == EXIT_SUCCESS
        r = read_json(report)
        assert r["ok"] is True

    def test_check_returns_exit_check_failed_on_issues(self, tmp_path: Path):
        """Check returns EXIT_CHECK_FAILED when validation issues found."""
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"x": 1}])
        contract = tmp_path / "contract.json"
        main(["infer", "--input", str(data), "--out", str(contract)])

        bad = tmp_path / "bad.jsonl"
        _write_jsonl(bad, [{"x": "not_an_int"}])
        code = main(["check", "--input", str(bad), "--contract", str(contract)])
        assert code == EXIT_CHECK_FAILED


# ============================================================================
# IO edge cases
# ============================================================================


class TestIOEdgeCases:
    """Test IO edge cases for uncovered branches."""

    def test_write_json_non_serializable(self, tmp_path: Path):
        """write_json raises ValueError for non-JSON-serializable objects."""
        with pytest.raises(ValueError, match="not JSON serializable"):
            write_json(tmp_path / "out.json", {1, 2, 3})

    def test_validate_path_for_write_parent_not_dir(self, tmp_path: Path):
        """Parent path that is a file raises ValueError."""
        file_as_parent = tmp_path / "parent_file"
        file_as_parent.write_text("data", encoding="utf-8")
        with pytest.raises(ValueError, match="Parent path is not a directory"):
            validate_path_for_write(file_as_parent / "child.json")

    def test_read_jsonl_file_not_found(self):
        """read_jsonl raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            list(read_jsonl(Path("/nonexistent.jsonl")))

    def test_read_json_file_not_found(self):
        """read_json raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            read_json(Path("/nonexistent.json"))
