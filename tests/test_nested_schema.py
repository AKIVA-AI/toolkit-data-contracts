"""Contract v2: JSON Schema subset with nested objects, arrays, enums, ranges,
patterns and nullability; drift on nested and array-item paths; streaming."""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from toolkit_data_contracts_drift.cli import (
    EXIT_CHECK_FAILED,
    EXIT_CLI_ERROR,
    EXIT_SUCCESS,
    main,
)
from toolkit_data_contracts_drift.contract import (
    drift_check,
    infer_contract,
    load_contract,
    profile_records,
    validate_records,
)
from toolkit_data_contracts_drift.schema import SchemaError


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _issues(contract, records, **kw):
    return [
        (i.kind, i.field, i.message, i.count)
        for i in validate_records(contract=contract, records=records, **kw)
    ]


CHAT = [
    {
        "id": "a1",
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!", "score": 0.5},
        ],
        "meta": {"source": "web", "turns": 2},
    },
    {
        "id": "a2",
        "messages": [{"role": "user", "content": "Bye"}],
        "meta": {"source": "app", "turns": 1, "lang": None},
    },
]


class TestInference:
    def test_arrays_of_objects_get_item_schemas(self):
        schema = infer_contract(CHAT)["schema"]
        msgs = schema["properties"]["messages"]
        assert msgs["type"] == "array"
        item = msgs["items"]
        assert item["type"] == "object"
        assert item["required"] == ["content", "role"]
        assert item["properties"]["score"] == {"type": "number"}
        assert schema["properties"]["meta"]["properties"]["lang"] == {"type": "null"}

    def test_integer_and_number_merge_to_number(self):
        schema = infer_contract([{"x": 1}, {"x": 2.5}])["schema"]
        assert schema["properties"]["x"] == {"type": "number"}

    def test_enum_inference_is_opt_in(self):
        rows = [{"role": r} for r in ["user", "assistant", "user"]]
        assert "enum" not in infer_contract(rows)["schema"]["properties"]["role"]
        role = infer_contract(rows, enum_max=5)["schema"]["properties"]["role"]
        assert role["enum"] == ["assistant", "user"]
        assert "enum" not in infer_contract(rows, enum_max=1)["schema"]["properties"]["role"]

    def test_nullable_enum_includes_null(self):
        rows = [{"r": "a"}, {"r": None}]
        r = infer_contract(rows, enum_max=5)["schema"]["properties"]["r"]
        assert r == {"type": ["null", "string"], "enum": ["a", None]}

    def test_inferred_schema_accepts_its_sample_under_reference_validator(self):
        """The reference jsonschema validator must accept every sampled record."""
        rng = random.Random(7)
        rows = []
        for i in range(200):
            row: dict[str, object] = {"id": i, "tags": [rng.choice("abc") for _ in range(3)]}
            if rng.random() < 0.5:
                row["meta"] = {"w": rng.random(), "k": rng.choice([None, "x", 3])}
            rows.append(row)
        schema = infer_contract(rows, enum_max=3)["schema"]
        ref = Draft202012Validator(schema)
        assert all(ref.is_valid(r) for r in rows)
        assert (
            validate_records(contract={"schema": schema}, records=rows, strict_integer=True) == []
        )


class TestValidation:
    SCHEMA = {
        "type": "object",
        "required": ["id", "messages"],
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z][0-9]+$"},
            "messages": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["role", "content"],
                    "properties": {
                        "role": {"enum": ["system", "user", "assistant"]},
                        "content": {"type": ["string", "null"], "maxLength": 20},
                        "score": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "additionalProperties": False,
                },
            },
        },
    }

    def test_valid_records_pass(self):
        assert _issues({"schema": self.SCHEMA}, CHAT) == []

    def test_each_keyword_reports_a_path(self):
        bad = {
            "id": "Z9",
            "messages": [
                {"role": "robot", "content": "x" * 21, "score": 1.5},
                {"role": "user", "content": None, "extra": 1},
                {"content": "hi"},
            ],
        }
        assert _issues({"schema": self.SCHEMA}, [bad]) == [
            ("enum_mismatch", "messages[].role", "enum", 1),
            ("length_violation", "messages[].content", "maxLength:20", 1),
            ("missing_required", "messages[].role", "missing_required", 1),
            ("pattern_mismatch", "id", "pattern:^[a-z][0-9]+$", 1),
            ("range_violation", "messages[].score", "maximum:1", 1),
            ("unexpected_field", "messages[].extra", "unexpected_field", 1),
        ]

    def test_empty_array_violates_min_items(self):
        assert _issues({"schema": self.SCHEMA}, [{"id": "a1", "messages": []}]) == [
            ("length_violation", "messages", "minItems:1", 1)
        ]

    def test_matches_reference_validator_on_random_instances(self):
        """Validity agrees with the jsonschema reference implementation."""
        ref = Draft202012Validator(self.SCHEMA)
        rng = random.Random(11)
        roles = ["system", "user", "assistant", "robot"]
        for _ in range(300):
            msgs = [
                {
                    k: v
                    for k, v in {
                        "role": rng.choice(roles),
                        "content": rng.choice([None, "ok", "y" * 25, 3]),
                        "score": rng.choice([0, 0.5, 2, -1, "x"]),
                        "extra": 1,
                    }.items()
                    if rng.random() < 0.8
                }
                for _ in range(rng.randint(0, 3))
            ]
            inst = {"id": rng.choice(["a1", "B2", "c33", 4]), "messages": msgs}
            ours = validate_records(contract=self.SCHEMA, records=[inst], strict_integer=True)
            assert (not ours) == ref.is_valid(inst), inst


class TestLoadContract:
    def test_bare_json_schema_is_accepted(self):
        c = load_contract({"type": "object", "properties": {"a": {"type": "string"}}})
        assert c["version"] == 2

    def test_unsupported_keyword_fails_loudly(self):
        with pytest.raises(SchemaError, match="unevaluatedProperties"):
            load_contract({"schema": {"type": "object", "unevaluatedProperties": False}})

    def test_remote_ref_fails_loudly(self):
        with pytest.raises(SchemaError, match="same-document"):
            load_contract({"schema": {"$ref": "https://example.com/s.json"}})

    def test_bad_pattern_fails_loudly(self):
        with pytest.raises(SchemaError, match="pattern"):
            load_contract({"schema": {"type": "string", "pattern": "("}})

    def test_not_a_contract(self):
        with pytest.raises(ValueError):
            load_contract({"hello": 1})


class TestNestedDrift:
    def _drift(self, base, cur, **kw):
        contract = infer_contract(base)
        return [
            (d.kind, d.field)
            for d in drift_check(
                baseline=profile_records(contract=contract, records=base),
                current=profile_records(contract=contract, records=cur),
                **kw,
            )
        ]

    def test_array_item_categorical_drift(self):
        base = [{"messages": [{"role": "user"}, {"role": "assistant"}]}] * 50
        cur = [{"messages": [{"role": "system"}, {"role": "system"}]}] * 50
        assert ("drift_categorical", "messages[].role") in self._drift(base, cur)

    def test_nested_numeric_mean_shift(self):
        base = [{"meta": {"score": 10 + (i % 3)}} for i in range(60)]
        cur = [{"meta": {"score": 50}} for _ in range(60)]
        assert self._drift(base, cur) == [("drift_mean_shift", "meta.score")]

    def test_nested_missing_rate_is_relative_to_parent(self):
        base = [{"meta": {"source": "web"}}] * 20 + [{"other": 1}] * 20
        cur = [{"meta": {}}] * 20 + [{"other": 1}] * 20
        assert self._drift(base, cur) == [("drift_missing_rate", "meta.source")]
        prof = profile_records(contract=infer_contract(base), records=cur)
        assert prof.field_stats["meta.source"]["missing_rate"] == 1.0
        assert prof.field_stats["meta"]["missing_rate"] == 0.5

    def test_no_drift_on_identical_nested_batches(self):
        assert self._drift(CHAT * 10, CHAT * 10) == []


class TestStreaming:
    def test_generators_are_read_once(self):
        rows = CHAT * 5
        contract = infer_contract(r for r in rows)
        assert validate_records(contract=contract, records=(r for r in rows)) == []
        prof = profile_records(contract=contract, records=(r for r in rows))
        assert prof.records == 10

    def test_streaming_std_matches_statistics_stdev(self):
        """Welford variance agrees with the stdlib reference (statistics.stdev)."""
        rng = random.Random(3)
        xs = [rng.gauss(100, 15) for _ in range(5000)]
        rows = [{"x": x} for x in xs]
        num = profile_records(contract=infer_contract(rows), records=rows).field_stats["x"][
            "numeric"
        ]
        assert num["mean"] == pytest.approx(statistics.fmean(xs), rel=1e-12)
        assert num["std"] == pytest.approx(statistics.stdev(xs), rel=1e-9)
        assert (num["min"], num["max"]) == (min(xs), max(xs))


class TestCli:
    def test_hand_written_schema_contract(self, tmp_path: Path):
        contract = tmp_path / "contract.json"
        contract.write_text(json.dumps(TestValidation.SCHEMA), encoding="utf-8")
        good = tmp_path / "good.jsonl"
        _write_jsonl(good, [{"id": "a1", "messages": [{"role": "user", "content": "hi"}]}])
        assert main(["check", "--input", str(good), "--contract", str(contract)]) == EXIT_SUCCESS
        bad = tmp_path / "bad.jsonl"
        _write_jsonl(bad, [{"id": "a1", "messages": [{"role": "bot", "content": "hi"}]}])
        assert main(["check", "--input", str(bad), "--contract", str(contract)]) == (
            EXIT_CHECK_FAILED
        )

    def test_unsupported_contract_is_an_error_report(self, tmp_path: Path):
        contract = tmp_path / "contract.json"
        contract.write_text(json.dumps({"schema": {"unevaluatedItems": False}}), encoding="utf-8")
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"a": 1}])
        out = tmp_path / "r.json"
        code = main(["check", "--input", str(data), "--contract", str(contract), "--out", str(out)])
        assert code == EXIT_CLI_ERROR
        env = json.loads(out.read_text(encoding="utf-8"))
        assert env["predicate"]["verdict"] == "error"
        assert "unevaluatedItems" in env["predicate"]["details"]["error"]

    def test_infer_enum_max_flag(self, tmp_path: Path):
        data = tmp_path / "d.jsonl"
        _write_jsonl(data, [{"role": "user"}, {"role": "assistant"}])
        out = tmp_path / "c.json"
        assert main(["infer", "--input", str(data), "--out", str(out), "--enum-max", "4"]) == 0
        schema = json.loads(out.read_text(encoding="utf-8"))["schema"]
        assert schema["properties"]["role"]["enum"] == ["assistant", "user"]

    def test_nested_drift_end_to_end(self, tmp_path: Path):
        base = tmp_path / "base.jsonl"
        _write_jsonl(base, [{"messages": [{"role": "user"}, {"role": "assistant"}]}] * 30)
        cur = tmp_path / "cur.jsonl"
        _write_jsonl(cur, [{"messages": [{"role": "tool"}]}] * 30)
        contract, prof, out = tmp_path / "c.json", tmp_path / "p.json", tmp_path / "r.json"
        assert main(["infer", "--input", str(base), "--out", str(contract)]) == 0
        assert (
            main(["profile", "--input", str(base), "--contract", str(contract), "--out", str(prof)])
            == 0
        )
        code = main(
            [
                "check",
                "--input",
                str(cur),
                "--contract",
                str(contract),
                "--baseline",
                str(prof),
                "--out",
                str(out),
            ]
        )
        assert code == EXIT_CHECK_FAILED
        drift = json.loads(out.read_text(encoding="utf-8"))["predicate"]["details"]["drift_issues"]
        # "tool" is also longer than "user"/"assistant", so text-length drift fires too.
        assert {(d["kind"], d["field"]) for d in drift} == {
            ("drift_categorical", "messages[].role"),
            ("drift_text_length", "messages[].role"),
        }
