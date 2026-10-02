"""Run the official JSON-Schema-Test-Suite (draft 2020-12) against schema.py.

Reference: https://github.com/json-schema-org/JSON-Schema-Test-Suite, commit
5b0ee1613e45fcc2bddac00e07c19cd49b00d8a8 (vendored under
tests/fixtures/json_schema_test_suite, MIT license). Every case whose schema
uses a supported feature must give the suite's expected validity. Cases that
rely on unsupported features must be rejected with SchemaError (never silently
passed) and are listed explicitly in UNSUPPORTED below.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit_data_contracts_drift.schema import SchemaError, Validator

SUITE = Path(__file__).parent / "fixtures" / "json_schema_test_suite" / "draft2020-12"

# (file, case description) pairs that use features outside the supported subset:
# unevaluated*, Unicode property escapes in patterns (Python re), remote or
# relative-URI refs, $anchor refs and $id in subschemas.
UNSUPPORTED = {
    ("not.json", "collect annotations inside a 'not', even if collection is disabled"),
    ("pattern.json", "pattern with Unicode property escape requires unicode mode"),
    ("patternProperties.json", "patternProperties with Unicode property escape"),
    ("ref.json", "remote ref, containing refs itself"),
    ("ref.json", "Recursive references between schemas"),
    ("ref.json", "ref creates new scope when adjacent to keywords"),
    ("ref.json", "refs with relative uris and defs"),
    ("ref.json", "relative refs with absolute uris and defs"),
    ("ref.json", "$id must be resolved against nearest parent, not just immediate parent"),
    ("ref.json", "order of evaluation: $id and $ref"),
    ("ref.json", "order of evaluation: $id and $anchor and $ref"),
    ("ref.json", "order of evaluation: $id and $ref on nested schema"),
    ("ref.json", "URN base URI with URN and anchor ref"),
    ("ref.json", "URN ref with nested pointer ref"),
    ("ref.json", "ref to if"),
    ("ref.json", "ref to then"),
    ("ref.json", "ref to else"),
    ("ref.json", "ref with absolute-path-reference"),
}


def _cases() -> list[tuple[str, dict[str, object]]]:
    out = []
    for path in sorted(SUITE.glob("*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")):
            out.append((path.name, case))
    return out


CASES = _cases()


def test_suite_is_vendored() -> None:
    assert len(CASES) > 250


def test_unsupported_cases_fail_loudly_and_list_is_exact() -> None:
    rejected = set()
    for fname, case in CASES:
        try:
            Validator(case["schema"])
        except SchemaError:
            rejected.add((fname, case["description"]))
    assert rejected <= UNSUPPORTED, f"newly rejected: {sorted(rejected - UNSUPPORTED)}"
    stale = {c for c in UNSUPPORTED if c not in rejected}
    # A listed case that now compiles must then pass the validity check below;
    # keep the list honest by removing entries once they are supported.
    assert not stale, f"supported now, remove from UNSUPPORTED: {sorted(stale)}"


@pytest.mark.parametrize(
    ("fname", "case"),
    [c for c in CASES if (c[0], c[1]["description"]) not in UNSUPPORTED],
    ids=[
        f"{c[0]}::{c[1]['description']}"
        for c in CASES
        if (c[0], c[1]["description"]) not in UNSUPPORTED
    ],
)
def test_suite_case(fname: str, case: dict[str, object]) -> None:
    validator = Validator(case["schema"])
    for test in case["tests"]:  # type: ignore[attr-defined]
        got = validator.is_valid(test["data"])
        assert got is test["valid"], f"{fname} / {case['description']} / {test['description']}"
