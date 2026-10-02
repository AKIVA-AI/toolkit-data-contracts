"""Record readers for JSONL (built in), Parquet and CSV (optional ``pyarrow``).

Every reader streams: Parquet row groups and CSV blocks are converted to
records batch by batch. Arrow values are converted to plain JSON values
(dates and times to ISO 8601 strings, decimals to numbers, binary to base64
strings) so the same contracts apply to every format. Like the JSONL reader,
the Parquet and CSV readers reject NaN and infinite floats.
"""

from __future__ import annotations

import base64
import datetime as _dt
import decimal
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .io import read_jsonl, validate_path_for_read

FORMATS = ("auto", "jsonl", "parquet", "csv")
_SUFFIXES = {".jsonl": "jsonl", ".ndjson": "jsonl", ".parquet": "parquet", ".csv": "csv"}


def detect_format(path: Path, fmt: str = "auto") -> str:
    if fmt != "auto":
        if fmt not in FORMATS:
            raise ValueError(f"unknown input format {fmt!r}; choose from {FORMATS}")
        return fmt
    return _SUFFIXES.get(Path(path).suffix.lower(), "jsonl")


def _jsonable(v: Any, where: str) -> Any:
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError(f"{where}: non-finite number {v} is not valid JSON")
        return v
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _jsonable(x, where) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        # Arrow maps come back as lists of (key, value) tuples.
        if v and all(isinstance(x, tuple) and len(x) == 2 for x in v):
            return {str(k): _jsonable(x, where) for k, x in v}
        return [_jsonable(x, where) for x in v]
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
        return v.isoformat()
    if isinstance(v, _dt.timedelta):
        return v.total_seconds()
    if isinstance(v, decimal.Decimal):
        f = float(v)
        return int(v) if v == v.to_integral_value() and abs(v) < 2**63 else f
    if isinstance(v, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(v)).decode("ascii")
    return str(v)


def _pyarrow() -> Any:
    try:
        import pyarrow  # pyright: ignore[reportMissingImports]
    except ImportError as e:
        raise ValueError(
            "Parquet and CSV input need pyarrow: "
            "pip install 'toolkit-data-contracts[parquet]'"
        ) from e
    return pyarrow


def _batches_to_records(batches: Any, limit: int | None) -> Iterator[dict[str, Any]]:
    n = 0
    for batch in batches:
        for row in batch.to_pylist():
            n += 1
            yield _jsonable(row, f"row {n}")
            if limit is not None and n >= limit:
                return


def read_parquet(path: Path, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    _pyarrow()
    import pyarrow.parquet as pq  # pyright: ignore[reportMissingImports]

    resolved = validate_path_for_read(Path(path))
    try:
        pf = pq.ParquetFile(resolved)
    except Exception as e:  # pyarrow raises its own error types
        raise ValueError(f"invalid Parquet file {resolved}: {e}") from e
    yield from _batches_to_records(pf.iter_batches(batch_size=1024), limit)


def read_csv(path: Path, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    _pyarrow()
    import pyarrow.csv as pacsv  # pyright: ignore[reportMissingImports]

    resolved = validate_path_for_read(Path(path))
    try:
        reader = pacsv.open_csv(resolved)
    except Exception as e:
        raise ValueError(f"invalid CSV file {resolved}: {e}") from e

    def batches() -> Iterator[Any]:
        while True:
            try:
                yield reader.read_next_batch()
            except StopIteration:
                return
            except Exception as e:
                raise ValueError(f"invalid CSV file {resolved}: {e}") from e

    yield from _batches_to_records(batches(), limit)


def read_records(
    path: Path, *, fmt: str = "auto", limit: int | None = None
) -> Iterator[dict[str, Any]]:
    """Stream records from a JSONL, Parquet or CSV file."""
    kind = detect_format(path, fmt)
    if kind == "parquet":
        return read_parquet(path, limit=limit)
    if kind == "csv":
        return read_csv(path, limit=limit)
    return iter(read_jsonl(path, limit=limit))
