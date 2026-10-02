"""Parquet and CSV input through pyarrow (optional ``parquet`` extra).

The reference for every conversion is pyarrow itself: files are written with
``pyarrow`` from known rows and must read back as the same JSON values.
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.json as pajson
import pyarrow.parquet as pq
import pytest

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.io import read_jsonl
from toolkit_data_contracts_drift.readers import detect_format, read_records

SAMPLE = Path(__file__).parents[1] / "examples" / "data" / "ultrachat_200k_test_sft_40.jsonl"


def test_detect_format():
    assert detect_format(Path("a.parquet")) == "parquet"
    assert detect_format(Path("a.CSV")) == "csv"
    assert detect_format(Path("a.ndjson")) == "jsonl"
    assert detect_format(Path("a.txt")) == "jsonl"
    assert detect_format(Path("a.txt"), "csv") == "csv"
    with pytest.raises(ValueError):
        detect_format(Path("a"), "xml")


def test_parquet_nested_rows_round_trip(tmp_path: Path):
    rows = [
        {"id": 1, "messages": [{"role": "user", "content": "hi"}], "score": 0.5, "tag": None},
        {"id": 2, "messages": [], "score": None, "tag": "x"},
    ]
    path = tmp_path / "d.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    assert list(read_records(path)) == rows


def test_parquet_logical_types_become_json(tmp_path: Path):
    table = pa.table(
        {
            "ts": pa.array([dt.datetime(2026, 9, 26, 12, 30)], pa.timestamp("s")),
            "day": pa.array([dt.date(2026, 9, 26)]),
            "price": pa.array([decimal.Decimal("12.50")], pa.decimal128(10, 2)),
            "count": pa.array([decimal.Decimal("3")], pa.decimal128(10, 0)),
            "blob": pa.array([b"\x00\x01"]),
            "attrs": pa.array([[("a", 1)]], pa.map_(pa.string(), pa.int64())),
        }
    )
    path = tmp_path / "t.parquet"
    pq.write_table(table, path)
    assert list(read_records(path)) == [
        {
            "ts": "2026-09-26T12:30:00",
            "day": "2026-09-26",
            "price": 12.5,
            "count": 3,
            "blob": "AAE=",
            "attrs": {"a": 1},
        }
    ]


def test_parquet_nan_is_rejected(tmp_path: Path):
    path = tmp_path / "nan.parquet"
    pq.write_table(pa.table({"x": [1.0, float("nan")]}), path)
    with pytest.raises(ValueError, match="row 2"):
        list(read_records(path))


def test_parquet_limit(tmp_path: Path):
    path = tmp_path / "many.parquet"
    pq.write_table(pa.table({"i": list(range(5000))}), path)
    assert [r["i"] for r in read_records(path, limit=3)] == [0, 1, 2]


def test_csv_types_follow_pyarrow_inference(tmp_path: Path):
    path = tmp_path / "d.csv"
    path.write_text("id,score,name,flag\n1,0.5,ann,true\n2,,bob,false\n", encoding="utf-8")
    expected = pacsv.read_csv(path).to_pylist()
    assert (
        list(read_records(path))
        == expected
        == [
            {"id": 1, "score": 0.5, "name": "ann", "flag": True},
            {"id": 2, "score": None, "name": "bob", "flag": False},
        ]
    )


def test_sample_as_parquet_matches_jsonl(tmp_path: Path):
    path = tmp_path / "sample.parquet"
    pq.write_table(pajson.read_json(SAMPLE), path)
    assert list(read_records(path)) == list(read_jsonl(SAMPLE))


class TestCli:
    def test_infer_from_parquet_and_check_csv(self, tmp_path: Path):
        pq_path = tmp_path / "base.parquet"
        pq.write_table(pa.table({"id": [1, 2, 3], "label": ["a", "b", "a"]}), pq_path)
        contract = tmp_path / "c.json"
        assert main(["infer", "--input", str(pq_path), "--out", str(contract)]) == EXIT_SUCCESS
        good = tmp_path / "good.csv"
        good.write_text("id,label\n4,b\n", encoding="utf-8")
        assert main(["check", "--input", str(good), "--contract", str(contract)]) == EXIT_SUCCESS
        bad = tmp_path / "bad.csv"
        bad.write_text("id,label\n4,7\n", encoding="utf-8")
        assert main(["check", "--input", str(bad), "--contract", str(contract)]) == (
            EXIT_CHECK_FAILED
        )

    def test_forced_format_and_bad_file(self, tmp_path: Path):
        data = tmp_path / "data.txt"
        data.write_text("a,b\n1,2\n", encoding="utf-8")
        contract = tmp_path / "c.json"
        args = ["infer", "--input", str(data), "--out", str(contract), "--input-format", "csv"]
        assert main(args) == EXIT_SUCCESS
        assert set(json.loads(contract.read_text())["schema"]["properties"]) == {"a", "b"}
        broken = tmp_path / "broken.parquet"
        broken.write_bytes(b"not parquet")
        assert main(["check", "--input", str(broken), "--contract", str(contract)]) == (
            EXIT_CLI_ERROR
        )
