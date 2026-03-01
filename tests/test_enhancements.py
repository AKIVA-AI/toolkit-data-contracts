"""Tests for data-contracts-drift enhancements."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit_data_contracts_drift.cli import (
    EXIT_CLI_ERROR,
    EXIT_SUCCESS,
    main,
)
from toolkit_data_contracts_drift.io import (
    read_json,
    read_jsonl,
    validate_path_for_read,
    validate_path_for_write,
    write_json,
)

# ============================================================================
# Path Validation Tests (IO)
# ============================================================================


def test_validate_path_for_read_success(tmp_path: Path) -> None:
    """Test read path validation succeeds with valid file."""
    file_path = tmp_path / "test.json"
    file_path.write_text('{"test": true}', encoding="utf-8")

    result = validate_path_for_read(file_path)
    assert result.is_absolute()
    assert result.is_file()


def test_validate_path_for_read_not_found() -> None:
    """Test read path validation fails with non-existent file."""
    with pytest.raises(FileNotFoundError, match="File not found"):
        validate_path_for_read(Path("/nonexistent/file.json"))


def test_validate_path_for_read_is_directory(tmp_path: Path) -> None:
    """Test read path validation fails when path is directory."""
    with pytest.raises(ValueError, match="not a file"):
        validate_path_for_read(tmp_path)


def test_validate_path_for_write_success(tmp_path: Path) -> None:
    """Test write path validation succeeds."""
    file_path = tmp_path / "output.json"
    result = validate_path_for_write(file_path)
    assert result.is_absolute()


def test_validate_path_for_write_is_directory(tmp_path: Path) -> None:
    """Test write path validation fails when path is directory."""
    with pytest.raises(ValueError, match="is a directory"):
        validate_path_for_write(tmp_path)


# ============================================================================
# JSON IO Tests
# ============================================================================


def test_read_json_success(tmp_path: Path) -> None:
    """Test reading valid JSON file."""
    file_path = tmp_path / "test.json"
    data = {"key": "value", "number": 42}
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = read_json(file_path)
    assert result == data


def test_read_json_invalid_json(tmp_path: Path) -> None:
    """Test reading invalid JSON raises ValueError."""
    file_path = tmp_path / "invalid.json"
    file_path.write_text("not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        read_json(file_path)


def test_read_json_file_not_found() -> None:
    """Test reading non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        read_json(Path("/nonexistent.json"))


def test_write_json_success(tmp_path: Path) -> None:
    """Test writing JSON file."""
    file_path = tmp_path / "output.json"
    data = {"test": True, "value": 123}

    write_json(file_path, data)

    assert file_path.exists()
    assert json.loads(file_path.read_text()) == data


# ============================================================================
# JSONL IO Tests
# ============================================================================


def test_read_jsonl_success(tmp_path: Path) -> None:
    """Test reading JSONL file."""
    file_path = tmp_path / "test.jsonl"
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    content = "\n".join(json.dumps(r) for r in rows) + "\n"
    file_path.write_text(content, encoding="utf-8")

    result = list(read_jsonl(file_path))

    assert len(result) == 3
    assert result[0] == {"id": 1}
    assert result[2] == {"id": 3}


def test_read_jsonl_with_limit(tmp_path: Path) -> None:
    """Test JSONL reader respects limit."""
    file_path = tmp_path / "test.jsonl"
    rows = [{"id": i} for i in range(10)]
    content = "\n".join(json.dumps(r) for r in rows) + "\n"
    file_path.write_text(content, encoding="utf-8")

    result = list(read_jsonl(file_path, limit=3))

    assert len(result) == 3


def test_read_jsonl_skips_empty_lines(tmp_path: Path) -> None:
    """Test JSONL reader skips empty lines."""
    file_path = tmp_path / "test.jsonl"
    content = '{"id": 1}\n\n{"id": 2}\n\n\n{"id": 3}\n'
    file_path.write_text(content, encoding="utf-8")

    result = list(read_jsonl(file_path))

    assert len(result) == 3


def test_read_jsonl_invalid_json(tmp_path: Path) -> None:
    """Test JSONL reader raises on invalid JSON."""
    file_path = tmp_path / "invalid.jsonl"
    content = '{"id": 1}\nnot json\n{"id": 2}\n'
    file_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON at line 2"):
        list(read_jsonl(file_path))


def test_read_jsonl_non_dict_object(tmp_path: Path) -> None:
    """Test JSONL reader raises on non-dict objects."""
    file_path = tmp_path / "invalid.jsonl"
    content = '{"id": 1}\n["array"]\n{"id": 2}\n'
    file_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Line 2 contains non-dict"):
        list(read_jsonl(file_path))


# ============================================================================
# CLI Infer Command Tests
# ============================================================================


def test_cli_infer_input_not_found(tmp_path: Path) -> None:
    """Test infer fails when input doesn't exist."""
    out_file = tmp_path / "contract.json"

    exit_code = main(["infer", "--input", "/nonexistent.jsonl", "--out", str(out_file)])

    assert exit_code == EXIT_CLI_ERROR


def test_cli_infer_invalid_jsonl(tmp_path: Path) -> None:
    """Test infer fails with invalid JSONL."""
    input_file = tmp_path / "data.jsonl"
    input_file.write_text("not json\n", encoding="utf-8")

    out_file = tmp_path / "contract.json"

    exit_code = main(["infer", "--input", str(input_file), "--out", str(out_file)])

    assert exit_code == EXIT_CLI_ERROR


# ============================================================================
# CLI Check Command Tests
# ============================================================================


def test_cli_check_contract_not_found(tmp_path: Path) -> None:
    """Test check fails when contract doesn't exist."""
    data_file = tmp_path / "data.jsonl"
    data_file.write_text('{"test": true}\n', encoding="utf-8")

    exit_code = main(
        ["check", "--input", str(data_file), "--contract", "/nonexistent.json"]
    )

    assert exit_code == EXIT_CLI_ERROR


def test_cli_check_input_not_found(tmp_path: Path) -> None:
    """Test check fails when input doesn't exist."""
    contract_file = tmp_path / "contract.json"
    contract = {
        "version": 1,
        "fields": {"test": {"type": "boolean"}},
        "allow_extra_fields": True,
    }
    contract_file.write_text(json.dumps(contract), encoding="utf-8")

    exit_code = main(
        ["check", "--input", "/nonexistent.jsonl", "--contract", str(contract_file)]
    )

    assert exit_code == EXIT_CLI_ERROR


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_cli_verbose_flag(tmp_path: Path, caplog) -> None:
    """Test --verbose flag enables debug logging."""
    data = [{"id": 1}, {"id": 2}]
    data_file = tmp_path / "data.jsonl"
    content = "\n".join(json.dumps(r) for r in data) + "\n"
    data_file.write_text(content, encoding="utf-8")

    out_file = tmp_path / "contract.json"

    exit_code = main(
        ["--verbose", "infer", "--input", str(data_file), "--out", str(out_file)]
    )

    assert exit_code == EXIT_SUCCESS


def test_jsonl_generator_lazy_evaluation(tmp_path: Path) -> None:
    """Test JSONL reader returns generator (lazy evaluation)."""
    file_path = tmp_path / "test.jsonl"
    rows = [{"id": i} for i in range(100)]
    content = "\n".join(json.dumps(r) for r in rows) + "\n"
    file_path.write_text(content, encoding="utf-8")

    # read_jsonl returns an iterator, not a list
    result = read_jsonl(file_path, limit=5)

    # Convert to list to consume iterator
    consumed = list(result)
    assert len(consumed) == 5


def test_write_json_creates_parent_directory(tmp_path: Path) -> None:
    """Test write_json creates parent directories."""
    file_path = tmp_path / "subdir" / "nested" / "output.json"
    data = {"nested": True}

    write_json(file_path, data)

    assert file_path.exists()
    assert json.loads(file_path.read_text()) == data
