"""Contract diff: breaking vs non-breaking classification.

Each direction claim is backed by witness records checked with the reference
``jsonschema`` validator: a ``tightens`` change has a record the old contract
accepts and the new one rejects; a ``loosens`` change has the reverse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.diff import diff_contracts, summarize


def obj(props: dict, required: list[str] | None = None, extra: object = True) -> dict:
    s: dict = {"type": "object", "properties": props, "additionalProperties": extra}
    if required:
        s["required"] = required
    return s


MSGS = {
    "type": "array",
    "items": obj({"role": {"enum": ["user", "assistant"]}, "content": {"type": "string"}}),
}

# (id, old, new, expected (path, change, direction), witness)
# witness: (record, valid_under_old, valid_under_new) or None for annotations.
CASES = [
    (
        "became-required",
        obj({"a": {"type": "string"}}),
        obj({"a": {"type": "string"}}, ["a"]),
        ("a", "became required", "tightens"),
        ({}, True, False),
    ),
    (
        "no-longer-required",
        obj({"a": {"type": "string"}}, ["a"]),
        obj({"a": {"type": "string"}}),
        ("a", "no longer required", "loosens"),
        ({}, False, True),
    ),
    (
        "nullable",
        obj({"a": {"type": "string"}}),
        obj({"a": {"type": ["null", "string"]}}),
        ("a", "became nullable", "loosens"),
        ({"a": None}, False, True),
    ),
    (
        "integer-to-number",
        obj({"a": {"type": "integer"}}),
        obj({"a": {"type": "number"}}),
        ("a", "type changed", "loosens"),
        ({"a": 1.5}, False, True),
    ),
    (
        "number-to-integer",
        obj({"a": {"type": "number"}}),
        obj({"a": {"type": "integer"}}),
        ("a", "type changed", "tightens"),
        ({"a": 1.5}, True, False),
    ),
    (
        "enum-value-added",
        obj({"messages": MSGS}),
        obj(
            {
                "messages": {
                    "type": "array",
                    "items": obj(
                        {
                            "role": {"enum": ["user", "assistant", "tool"]},
                            "content": {"type": "string"},
                        }
                    ),
                }
            }
        ),
        ("messages[].role", "enum values added", "loosens"),
        ({"messages": [{"role": "tool"}]}, False, True),
    ),
    (
        "enum-value-removed",
        obj({"messages": MSGS}),
        obj(
            {
                "messages": {
                    "type": "array",
                    "items": obj({"role": {"enum": ["user"]}, "content": {"type": "string"}}),
                }
            }
        ),
        ("messages[].role", "enum values removed", "tightens"),
        ({"messages": [{"role": "assistant"}]}, True, False),
    ),
    (
        "max-length-lowered",
        obj({"a": {"type": "string", "maxLength": 10}}),
        obj({"a": {"type": "string", "maxLength": 5}}),
        ("a", "maxLength changed", "tightens"),
        ({"a": "abcdefg"}, True, False),
    ),
    (
        "minimum-lowered",
        obj({"a": {"type": "integer", "minimum": 0}}),
        obj({"a": {"type": "integer", "minimum": -5}}),
        ("a", "minimum changed", "loosens"),
        ({"a": -1}, False, True),
    ),
    (
        "closed-object",
        obj({"a": {"type": "string"}}),
        obj({"a": {"type": "string"}}, extra=False),
        ("$", "additionalProperties changed", "tightens"),
        ({"zzz": 1}, True, False),
    ),
    (
        "field-added-to-closed-object",
        obj({"a": {"type": "string"}}, extra=False),
        obj({"a": {"type": "string"}, "b": {"type": "integer"}}, extra=False),
        ("b", "field added", "loosens"),
        ({"b": 1}, False, True),
    ),
    (
        "field-added-to-open-object",
        obj({"a": {"type": "string"}}),
        obj({"a": {"type": "string"}, "b": {"type": "string"}}),
        ("b", "field added", "tightens"),
        ({"b": 1}, True, False),
    ),
    (
        "field-removed-from-closed-object",
        obj({"a": {"type": "string"}, "b": {"type": "string"}}, extra=False),
        obj({"a": {"type": "string"}}, extra=False),
        ("b", "field removed", "tightens"),
        ({"b": "x"}, True, False),
    ),
    (
        "field-removed-from-open-object",
        obj({"a": {"type": "string"}, "b": {"type": "string"}}),
        obj({"a": {"type": "string"}}),
        ("b", "field removed", "loosens"),
        ({"b": 1}, False, True),
    ),
    (
        "pattern-changed",
        obj({"a": {"type": "string", "pattern": "^a"}}),
        obj({"a": {"type": "string", "pattern": "^b"}}),
        ("a", "pattern changed", "both"),
        ({"a": "abc"}, True, False),
    ),
    (
        "anyof-changed",
        obj({"a": {"anyOf": [{"type": "string"}, {"type": "integer"}]}}),
        obj({"a": {"anyOf": [{"type": "string"}, {"type": "boolean"}]}}),
        ("a", "anyOf changed (not analysed)", "both"),
        ({"a": 1}, True, False),
    ),
    (
        "description-only",
        obj({"a": {"type": "string", "description": "old"}}),
        obj({"a": {"type": "string", "description": "new"}}),
        ("a", "description changed", "annotation"),
        None,
    ),
]


@pytest.mark.parametrize(
    ("old", "new", "expected", "witness"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_classification_with_witness(old, new, expected, witness):
    changes = diff_contracts(old, new)
    assert [(c.path, c.change, c.direction) for c in changes] == [expected]
    if witness is not None:
        record, ok_old, ok_new = witness
        assert Draft202012Validator(old).is_valid(record) is ok_old
        assert Draft202012Validator(new).is_valid(record) is ok_new


def test_identical_and_ref_equivalent_contracts_have_no_changes():
    inline = obj({"m": obj({"k": {"type": "string"}}, ["k"])})
    with_ref = {
        "type": "object",
        "additionalProperties": True,
        "properties": {"m": {"$ref": "#/$defs/M"}},
        "$defs": {"M": obj({"k": {"type": "string"}}, ["k"])},
    }
    assert diff_contracts(inline, inline) == []
    assert diff_contracts(inline, with_ref) == []


def test_modes_decide_what_is_breaking():
    old = obj({"a": {"type": "string"}, "r": {"enum": ["x", "y"]}})
    new = obj({"a": {"type": ["null", "string"]}, "r": {"enum": ["x"]}}, ["a"])
    changes = diff_contracts(old, new)
    directions = sorted(c.direction for c in changes)
    assert directions == ["loosens", "tightens", "tightens"]
    assert summarize(changes, "backward")["breaking"] == 2
    assert summarize(changes, "forward")["breaking"] == 1
    assert summarize(changes, "full")["breaking"] == 3
    with pytest.raises(ValueError):
        summarize(changes, "sideways")


def test_v1_contract_against_v2():
    v1 = {
        "version": 1,
        "allow_extra_fields": True,
        "fields": {"a": {"types": ["string"], "required": True}},
    }
    v2 = {"version": 2, "schema": obj({"a": {"type": "string"}}, ["a"])}
    assert diff_contracts(v1, v2) == []


def _write(path: Path, schema: dict) -> Path:
    path.write_text(json.dumps({"version": 2, "schema": schema}), encoding="utf-8")
    return path


class TestCli:
    def test_breaking_diff_fails_with_envelope(self, tmp_path: Path):
        old = _write(tmp_path / "old.json", obj({"a": {"type": "string"}}))
        new = _write(tmp_path / "new.json", obj({"a": {"type": "string"}}, ["a"]))
        out = tmp_path / "r.json"
        code = main(["diff", "--old", str(old), "--new", str(new), "--out", str(out)])
        assert code == EXIT_CHECK_FAILED
        env = json.loads(out.read_text(encoding="utf-8"))
        schema = json.loads(
            (Path(__file__).parents[1] / "schemas" / "report-envelope.v1.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(env)
        pred = env["predicate"]
        assert pred["kind"] == "data.diff" and pred["verdict"] == "fail"
        assert pred["summary"] == {
            "mode": "backward",
            "changes": 1,
            "breaking": 1,
            "non_breaking": 0,
            "ok": False,
        }
        assert pred["details"]["changes"][0]["breaking"] is True
        forward = ["diff", "--old", str(old), "--new", str(new), "--mode", "forward"]
        assert main(forward) == EXIT_SUCCESS

    def test_markdown_and_github_formats(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        old = _write(tmp_path / "old.json", obj({"a": {"type": "string"}}))
        new = _write(tmp_path / "new.json", obj({"a": {"type": "string", "maxLength": 3}}))
        main(["diff", "--old", str(old), "--new", str(new), "--format", "markdown"])
        md = capsys.readouterr().out
        assert md.startswith("### Contract diff (backward): BREAKING")
        assert "| breaking | `a` | maxLength changed | tightens |" in md
        main(["diff", "--old", str(old), "--new", str(new), "--format", "github"])
        gh = capsys.readouterr().out.splitlines()
        assert gh[0] == (
            f"::error file={new},title=Breaking contract change::a: maxLength changed (tightens)"
        )

    def test_unreadable_contract_is_an_error(self, tmp_path: Path):
        new = _write(tmp_path / "new.json", obj({}))
        code = main(["diff", "--old", str(tmp_path / "missing.json"), "--new", str(new)])
        assert code == EXIT_CLI_ERROR
