from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.cli import main
from toolkit_data_contracts_drift.io import read_json


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_infer_profile_and_check_pass(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    _write_jsonl(
        baseline,
        [
            {"country": "US", "age": 10},
            {"country": "US", "age": 11},
            {"country": "CA", "age": 12},
        ],
    )
    contract_path = tmp_path / "contract.json"
    assert main(["infer", "--input", str(baseline), "--out", str(contract_path)]) == 0

    prof_path = tmp_path / "baseline.profile.json"
    assert (
        main(
            [
                "profile",
                "--input",
                str(baseline),
                "--contract",
                str(contract_path),
                "--out",
                str(prof_path),
            ]
        )
        == 0
    )

    new_batch = tmp_path / "new.jsonl"
    _write_jsonl(new_batch, [{"country": "US", "age": 12}, {"country": "CA", "age": 13}])
    assert (
        main(
            [
                "check",
                "--input",
                str(new_batch),
                "--contract",
                str(contract_path),
                "--baseline",
                str(prof_path),
                "--max-missing",
                "0.5",
                "--max-mean-shift-sigma",
                "10.0",
            ]
        )
        == 0
    )


def test_check_fails_on_type_mismatch(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    _write_jsonl(baseline, [{"country": "US", "age": 10}])
    contract_path = tmp_path / "contract.json"
    assert main(["infer", "--input", str(baseline), "--out", str(contract_path)]) == 0

    bad = tmp_path / "bad.jsonl"
    _write_jsonl(bad, [{"country": 123, "age": 10}])

    out = tmp_path / "report.json"
    code = main(
        [
            "check",
            "--input",
            str(bad),
            "--contract",
            str(contract_path),
            "--out",
            str(out),
        ]
    )
    assert code == 4
    rep = read_json(out)
    assert rep["ok"] is False
    assert rep["validation_issues"]
