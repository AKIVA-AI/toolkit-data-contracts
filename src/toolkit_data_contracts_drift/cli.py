from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .contract import (
    Profile,
    drift_check,
    infer_contract,
    profile_records,
    validate_records,
)
from .io import read_json, read_jsonl, write_json

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_CLI_ERROR = 2
EXIT_UNEXPECTED_ERROR = 3
EXIT_CHECK_FAILED = 4


def _cmd_infer(args: argparse.Namespace) -> int:
    """Infer contract from JSONL records."""
    input_path = Path(args.input).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit)

    logger.info(f"Inferring contract from: {input_path} (limit={limit})")

    try:
        records = list(read_jsonl(input_path, limit=limit))
        logger.info(f"Read {len(records)} records")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_CLI_ERROR

    try:
        c = infer_contract(records, allow_extra_fields=not bool(args.disallow_extra))
        logger.info("Contract inferred successfully")
    except Exception as e:
        logger.error(f"Failed to infer contract: {e}")
        return EXIT_CLI_ERROR

    try:
        write_json(out_path, c)
        logger.info(f"Wrote contract to: {out_path}")
        return EXIT_SUCCESS
    except (OSError, PermissionError, ValueError) as e:
        logger.error(f"Failed to write output: {e}")
        return EXIT_CLI_ERROR


def _cmd_profile(args: argparse.Namespace) -> int:
    """Compute baseline profile for drift checks."""
    input_path = Path(args.input).resolve()
    contract_path = Path(args.contract).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit)

    logger.info(f"Loading contract from: {contract_path}")

    try:
        contract = read_json(contract_path)
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read contract: {e}")
        return EXIT_CLI_ERROR

    logger.info(f"Reading records from: {input_path} (limit={limit})")

    try:
        records = list(read_jsonl(input_path, limit=limit))
        logger.info(f"Read {len(records)} records")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_CLI_ERROR

    logger.info("Computing profile...")

    try:
        prof = profile_records(contract=contract, records=records)
    except Exception as e:
        logger.error(f"Failed to profile records: {e}")
        return EXIT_CLI_ERROR

    try:
        write_json(out_path, prof.to_json())
        logger.info(f"Wrote profile to: {out_path}")
        return EXIT_SUCCESS
    except (OSError, PermissionError, ValueError) as e:
        logger.error(f"Failed to write output: {e}")
        return EXIT_CLI_ERROR


def _report_json(obj: Any, out: str) -> None:
    """Output JSON report to file or stdout."""
    text = json.dumps(obj, indent=2, sort_keys=True)
    if out:
        try:
            out_path = Path(out)
            out_path.write_text(text, encoding="utf-8")
            logger.info(f"Wrote report to: {out_path}")
        except (OSError, PermissionError) as e:
            logger.error(f"Failed to write report: {e}")
            raise
    else:
        print(text)


def _cmd_check(args: argparse.Namespace) -> int:
    """Validate records and optionally check for drift."""
    input_path = Path(args.input).resolve()
    contract_path = Path(args.contract).resolve()

    logger.info(f"Loading contract from: {contract_path}")

    try:
        contract = read_json(contract_path)
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read contract: {e}")
        return EXIT_CLI_ERROR

    logger.info(f"Reading records from: {input_path}")

    try:
        records = list(read_jsonl(input_path))
        logger.info(f"Read {len(records)} records")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_CLI_ERROR

    logger.info("Validating records...")

    try:
        validation = validate_records(contract=contract, records=records)
        failed = bool(validation)

        if validation:
            logger.warning(f"Found {len(validation)} validation issues")
        else:
            logger.info("Validation passed")

    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        return EXIT_CLI_ERROR

    baseline_issues = []
    if args.baseline:
        baseline_path = Path(args.baseline).resolve()
        logger.info(f"Loading baseline from: {baseline_path}")

        try:
            baseline = Profile.from_json(read_json(baseline_path))
            current = profile_records(contract=contract, records=records)

            logger.info("Checking for drift...")
            baseline_issues = drift_check(
                baseline=baseline,
                current=current,
                max_missing_rate=float(args.max_missing),
                max_mean_shift_sigma=float(args.max_mean_shift_sigma),
            )
            failed = failed or bool(baseline_issues)

            if baseline_issues:
                logger.warning(f"Found {len(baseline_issues)} drift issues")
            else:
                logger.info("No drift detected")

        except (ValueError, FileNotFoundError) as e:
            logger.error(f"Failed to process baseline: {e}")
            return EXIT_CLI_ERROR
        except Exception as e:
            logger.error(f"Drift check failed: {e}")
            return EXIT_CLI_ERROR

    report = {
        "ok": not failed,
        "validation_issues": [v.__dict__ for v in validation],
        "drift_issues": [v.__dict__ for v in baseline_issues],
    }

    try:
        _report_json(report, str(args.out or ""))
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to write report: {e}")
        return EXIT_CLI_ERROR

    if failed:
        logger.error("Check failed")
        return EXIT_CHECK_FAILED
    else:
        logger.info("Check passed")
        return EXIT_SUCCESS


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="toolkit-contracts",
        description="Toolkit Data Contracts Drift - Validate and monitor data contracts",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    infer = sub.add_parser("infer", help="Infer a contract from JSONL records.")
    infer.add_argument("--input", required=True, help="Input JSONL file path")
    infer.add_argument("--out", required=True, help="Output contract JSON file path")
    infer.add_argument(
        "--limit", default="5000", help="Max records to process (default: 5000)"
    )
    infer.add_argument(
        "--disallow-extra", action="store_true", help="Disallow extra fields"
    )
    infer.set_defaults(func=_cmd_infer)

    prof = sub.add_parser(
        "profile", help="Compute a baseline profile for drift checks."
    )
    prof.add_argument("--input", required=True, help="Input JSONL file path")
    prof.add_argument("--contract", required=True, help="Contract JSON file path")
    prof.add_argument("--out", required=True, help="Output profile JSON file path")
    prof.add_argument(
        "--limit", default="50000", help="Max records to process (default: 50000)"
    )
    prof.set_defaults(func=_cmd_profile)

    check = sub.add_parser(
        "check", help="Validate records and optionally drift-check vs baseline."
    )
    check.add_argument("--input", required=True, help="Input JSONL file path")
    check.add_argument("--contract", required=True, help="Contract JSON file path")
    check.add_argument("--baseline", default="", help="Baseline profile JSON file path")
    check.add_argument(
        "--max-missing", default="0.01", help="Max missing rate (default: 0.01)"
    )
    check.add_argument(
        "--max-mean-shift-sigma",
        default="3.0",
        help="Max mean shift sigma (default: 3.0)",
    )
    check.add_argument(
        "--out", default="", help="Output report file path (default: stdout)"
    )
    check.set_defaults(func=_cmd_check)

    return p


def main(argv: list[str] | None = None) -> int:
    """Main entry point for CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    try:
        return int(args.func(args))
    except (ValueError, FileNotFoundError, PermissionError) as e:
        logger.error(f"{type(e).__name__}: {e}")
        return EXIT_CLI_ERROR
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return EXIT_UNEXPECTED_ERROR
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(
            "\nAn unexpected error occurred. Please report this issue.",
            file=sys.stderr,
        )
        return EXIT_UNEXPECTED_ERROR
