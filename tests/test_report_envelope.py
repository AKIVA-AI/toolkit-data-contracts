"""`check` writes the shared report envelope v1 (an in-toto Statement v1).

The envelope is validated against the committed JSON Schema
(`schemas/report-envelope.v1.json`) with the reference `jsonschema` validator.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from toolkit_data_contracts_drift import __version__
from toolkit_data_contracts_drift.cli import (
    EXIT_CHECK_FAILED,
    EXIT_CLI_ERROR,
    EXIT_SUCCESS,
    main,
)
from toolkit_data_contracts_drift.report import (
    PREDICATE_TYPE,
    build_envelope,
    canonical_json,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "report-envelope.v1.json").read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def contract_and_profile(tmp_path: Path) -> tuple[Path, Path, Path]:
    data = tmp_path / "base.jsonl"
    _write_jsonl(data, [{"country": "US", "age": 10}, {"country": "CA", "age": 12}] * 10)
    contract = tmp_path / "contract.json"
    profile = tmp_path / "profile.json"
    assert main(["infer", "--input", str(data), "--out", str(contract)]) == 0
    assert (
        main(["profile", "--input", str(data), "--contract", str(contract), "--out", str(profile)])
        == 0
    )
    return data, contract, profile


def test_pass_report_is_a_schema_valid_canonical_statement(
    tmp_path: Path, contract_and_profile: tuple[Path, Path, Path]
) -> None:
    data, contract, profile = contract_and_profile
    out = tmp_path / "report.json"
    code = main(
        [
            "check",
            "--input",
            str(data),
            "--contract",
            str(contract),
            "--baseline",
            str(profile),
            "--out",
            str(out),
        ]
    )
    assert code == EXIT_SUCCESS
    raw = out.read_bytes().decode("utf-8")
    env = json.loads(raw)
    _validator().validate(env)

    # Canonical form: sorted keys, no insignificant whitespace, one trailing newline.
    assert raw == json.dumps(env, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"

    assert env["_type"] == "https://in-toto.io/Statement/v1"
    assert env["predicateType"] == PREDICATE_TYPE
    assert env["subject"] == [{"name": str(data), "digest": {"sha256": _sha256(data)}}]
    pred = env["predicate"]
    assert pred["tool"] == {"name": "toolkit-data-contracts", "version": __version__}
    assert pred["kind"] == "data.check"
    assert pred["verdict"] == "pass" and pred["exit_code"] == 0
    assert {i["name"]: i["digest"]["sha256"] for i in pred["inputs"]} == {
        str(contract): _sha256(contract),
        str(profile): _sha256(profile),
    }
    assert pred["summary"] == {
        "ok": True,
        "records": 20,
        "validation_issues": 0,
        "invalid_records": 0,
        "invalid_occurrences": 0,
        "drift_checked": True,
        "drift_issues": 0,
    }
    assert pred["details"]["thresholds"]["max_psi"] == 0.25


def test_fail_report_carries_issues_and_exit_code(
    tmp_path: Path, contract_and_profile: tuple[Path, Path, Path]
) -> None:
    _, contract, _ = contract_and_profile
    bad = tmp_path / "bad.jsonl"
    _write_jsonl(bad, [{"country": 1, "age": 10}, {"country": 2, "age": 11}])
    out = tmp_path / "report.json"
    code = main(["check", "--input", str(bad), "--contract", str(contract), "--out", str(out)])
    assert code == EXIT_CHECK_FAILED
    env = json.loads(out.read_text(encoding="utf-8"))
    _validator().validate(env)
    pred = env["predicate"]
    assert pred["verdict"] == "fail" and pred["exit_code"] == EXIT_CHECK_FAILED
    assert pred["summary"]["invalid_occurrences"] == 2
    assert pred["details"]["validation_issues"] == [
        {
            "kind": "type_mismatch",
            "field": "country",
            "message": "type_mismatch:integer",
            "count": 2,
        }
    ]


def test_malformed_input_gives_error_report_never_pass(
    tmp_path: Path, contract_and_profile: tuple[Path, Path, Path]
) -> None:
    _, contract, _ = contract_and_profile
    bad = tmp_path / "broken.jsonl"
    bad.write_text('{"country": "US"}\n{not json\n', encoding="utf-8")
    out = tmp_path / "report.json"
    code = main(["check", "--input", str(bad), "--contract", str(contract), "--out", str(out)])
    assert code == EXIT_CLI_ERROR
    env = json.loads(out.read_text(encoding="utf-8"))
    _validator().validate(env)
    assert env["predicate"]["verdict"] == "error"
    assert env["predicate"]["exit_code"] == EXIT_CLI_ERROR
    assert "line 2" in env["predicate"]["details"]["error"]


def test_missing_input_writes_no_report(
    tmp_path: Path, contract_and_profile: tuple[Path, Path, Path]
) -> None:
    _, contract, _ = contract_and_profile
    out = tmp_path / "report.json"
    code = main(
        [
            "check",
            "--input",
            str(tmp_path / "nope.jsonl"),
            "--contract",
            str(contract),
            "--out",
            str(out),
        ]
    )
    assert code == EXIT_CLI_ERROR
    assert not out.exists()


def test_source_date_epoch_makes_report_reproducible(
    tmp_path: Path,
    contract_and_profile: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, contract, _ = contract_and_profile
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1790000000")
    out1, out2 = tmp_path / "r1.json", tmp_path / "r2.json"
    for out in (out1, out2):
        main(["check", "--input", str(data), "--contract", str(contract), "--out", str(out)])
    assert out1.read_bytes() == out2.read_bytes()
    # 1790000000 seconds after the Unix epoch is 2026-09-21T14:13:20Z.
    assert json.loads(out1.read_text())["predicate"]["created_at"] == "2026-09-21T14:13:20Z"


def test_stdout_default_is_envelope(
    contract_and_profile: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    data, contract, _ = contract_and_profile
    assert main(["check", "--input", str(data), "--contract", str(contract)]) == 0
    env = json.loads(capsys.readouterr().out)
    _validator().validate(env)


def test_json_legacy_format_keeps_pre_1_0_shape(
    contract_and_profile: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    data, contract, _ = contract_and_profile
    code = main(
        ["check", "--input", str(data), "--contract", str(contract), "--format", "json-legacy"]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "validation_issues": [],
        "drift_issues": [],
    }


def test_markdown_format(
    tmp_path: Path,
    contract_and_profile: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, contract, _ = contract_and_profile
    bad = tmp_path / "bad.jsonl"
    _write_jsonl(bad, [{"country": 1, "age": 10}])
    code = main(["check", "--input", str(bad), "--contract", str(contract), "--format", "markdown"])
    assert code == EXIT_CHECK_FAILED
    out = capsys.readouterr().out
    assert out.startswith("### Data contract check: FAIL")
    assert "| type_mismatch | `country` | 1 | type_mismatch:integer |" in out


class TestBuildEnvelope:
    def _build(self, verdict: str, exit_code: int) -> dict[str, object]:
        return build_envelope(
            kind="data.check",
            subject=[{"name": "x", "digest": {"sha256": "0" * 64}}],
            inputs=[],
            verdict=verdict,  # type: ignore[arg-type]
            exit_code=exit_code,
            summary={},
            details={},
        )

    @pytest.mark.parametrize(("verdict", "code"), [("pass", 4), ("fail", 0), ("error", 0)])
    def test_inconsistent_verdict_and_exit_code_rejected(self, verdict: str, code: int) -> None:
        with pytest.raises(ValueError, match="inconsistent"):
            self._build(verdict, code)

    def test_unknown_verdict_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid verdict"):
            self._build("maybe", 1)

    def test_canonical_json_rejects_nan(self) -> None:
        with pytest.raises(ValueError):
            canonical_json({"x": float("nan")})


def test_spec_doc_is_committed() -> None:
    text = (ROOT / "docs" / "report-envelope.md").read_text(encoding="utf-8")
    assert "https://in-toto.io/Statement/v1" in text
