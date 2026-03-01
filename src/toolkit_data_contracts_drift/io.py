from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def validate_path_for_read(path: Path) -> Path:
    """Validate path exists and is readable file.

    Args:
        path: Path to validate

    Returns:
        Resolved absolute path

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If path is not a file
        PermissionError: If file is not readable
    """
    resolved = path.resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    if not resolved.is_file():
        raise ValueError(f"Path is not a file: {resolved}")

    try:
        with resolved.open("r"):
            pass
    except PermissionError as e:
        raise PermissionError(f"File not readable: {resolved}") from e

    return resolved


def validate_path_for_write(path: Path) -> Path:
    """Validate path can be written to.

    Args:
        path: Path to validate

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is a directory
    """
    resolved = path.resolve()

    if resolved.is_dir():
        raise ValueError(f"Path is a directory, not a file: {resolved}")

    parent = resolved.parent
    if parent.exists() and not parent.is_dir():
        raise ValueError(f"Parent path is not a directory: {parent}")

    return resolved


def read_jsonl(path: Path, *, limit: int | None = None) -> Iterable[dict[str, Any]]:
    """Read JSONL file and yield dicts.

    Args:
        path: Path to JSONL file
        limit: Maximum number of records to read (None = all)

    Yields:
        Dictionary for each valid line

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file contains invalid JSON or non-dict objects
        PermissionError: If file is not readable
    """
    validated_path = validate_path_for_read(path)
    logger.debug(
        f"Reading JSONL from: {validated_path}" + (f" (limit={limit})" if limit else "")
    )

    n = 0
    try:
        with validated_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON at line {line_num}: {e}")
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}") from e

                if not isinstance(obj, dict):
                    logger.error(f"Line {line_num} is not a dict")
                    raise ValueError(f"Line {line_num} contains non-dict object")

                yield obj
                n += 1

                if limit is not None and n >= limit:
                    logger.debug(f"Reached limit of {limit} records")
                    break

        logger.info(f"Read {n} records from JSONL: {validated_path}")

    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"Failed to read {validated_path}: {e}")
        raise


def write_json(path: Path, obj: Any) -> None:
    """Write object to JSON file.

    Args:
        path: Path to JSON file
        obj: Object to serialize to JSON

    Raises:
        ValueError: If object is not JSON serializable
        PermissionError: If path is not writable
        OSError: If file write fails
    """
    validated_path = validate_path_for_write(path)
    logger.debug(f"Writing JSON to: {validated_path}")

    try:
        content = json.dumps(obj, indent=2, sort_keys=True)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize object to JSON: {e}")
        raise ValueError(f"Object is not JSON serializable: {e}") from e

    try:
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        validated_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote JSON to: {validated_path}")
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to write {validated_path}: {e}")
        raise


def read_json(path: Path) -> Any:
    """Read and parse JSON file.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not valid JSON
        PermissionError: If file is not readable
    """
    validated_path = validate_path_for_read(path)
    logger.debug(f"Reading JSON from: {validated_path}")

    try:
        content = validated_path.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {validated_path}: {e}")
        raise ValueError(f"Invalid JSON in {validated_path}: {e}") from e
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"Failed to read {validated_path}: {e}")
        raise
