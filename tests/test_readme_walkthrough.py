"""The README's five-minute walkthrough, run on the committed UltraChat sample."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_SUCCESS, main

SAMPLE = Path(__file__).parents[1] / "examples" / "data" / "ultrachat_200k_test_sft_40.jsonl"


def _degrade(src: Path, dst: Path) -> None:
    """Same edit as the README: cut assistant answers, add a system turn."""
    with src.open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as out:
        for line in fin:
            row = json.loads(line)
            for m in row["messages"]:
                if m["role"] == "assistant":
                    m["content"] = m["content"][:20]
            row["messages"].insert(0, {"role": "system", "content": "You are terse."})
            out.write(json.dumps(row) + "\n")


def test_walkthrough(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sample = str(SAMPLE)
    assert main(["check", "--input", sample, "--preset", "sft", "--format", "table"]) == 0
    assert capsys.readouterr().out.startswith("Status: PASS")

    contract, baseline = tmp_path / "chat.contract.json", tmp_path / "baseline.profile.json"
    assert main(["infer", "--input", sample, "--out", str(contract), "--enum-max", "3"]) == 0
    role = json.loads(contract.read_text(encoding="utf-8"))["schema"]["properties"]["messages"][
        "items"
    ]["properties"]["role"]
    assert role == {"type": "string", "enum": ["assistant", "user"]}
    assert (
        main(["profile", "--input", sample, "--contract", str(contract), "--out", str(baseline)])
        == EXIT_SUCCESS
    )

    bad = tmp_path / "bad.jsonl"
    _degrade(SAMPLE, bad)
    code = main(
        [
            "check",
            "--input",
            str(bad),
            "--contract",
            str(contract),
            "--baseline",
            str(baseline),
            "--format",
            "table",
        ]
    )
    assert code == EXIT_CHECK_FAILED
    out = capsys.readouterr().out
    assert "enum_mismatch             messages[].role          40  enum" in out
    assert "drift_text_length         messages[].content        1  psi=5.707" in out
    assert "drift_token_count         messages[].content        1  psi=5.642" in out
    assert "drift_categorical         messages[].role           1  psi=0.941" in out

    odcs = tmp_path / "chat.odcs.yaml"
    args = [
        "odcs",
        "export",
        "--contract",
        str(contract),
        "--out",
        str(odcs),
        "--name",
        "ultrachat",
    ]
    assert main(args) == EXIT_SUCCESS
    assert "apiVersion: v3.1.0" in odcs.read_text(encoding="utf-8")
