from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .contract import (
    Profile,
    drift_check,
    infer_contract,
    profile_records,
    validate_records,
)
from .io import read_json, read_jsonl, write_json
from .monitoring import ContractMetrics
from .observability import OperationTimer, get_operation_metrics, new_correlation_id

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_CLI_ERROR = 2
EXIT_UNEXPECTED_ERROR = 3
EXIT_CHECK_FAILED = 4


class _JsonLogFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


def _cmd_infer(args: argparse.Namespace) -> int:
    """Infer contract from JSONL records."""
    input_path = Path(args.input).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit)
    op_metrics = get_operation_metrics()

    logger.info(f"Inferring contract from: {input_path} (limit={limit})")

    try:
        records = list(read_jsonl(input_path, limit=limit))
        logger.info(f"Read {len(records)} records")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_CLI_ERROR

    try:
        with OperationTimer("infer") as timer:
            c = infer_contract(records, allow_extra_fields=not bool(args.disallow_extra))
        op_metrics.record_infer(record_count=len(records))
        op_metrics.record_timing("infer", timer.duration_ms)
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
    op_metrics = get_operation_metrics()

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
        with OperationTimer("profile") as timer:
            prof = profile_records(contract=contract, records=records)
        op_metrics.record_profile(record_count=len(records))
        op_metrics.record_timing("profile", timer.duration_ms)
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


def _format_table(report: dict[str, Any]) -> str:
    """Format check report as a human-readable table."""
    lines: list[str] = []
    ok = report.get("ok", False)
    lines.append(f"Status: {'PASS' if ok else 'FAIL'}")
    lines.append("")

    validation_issues = report.get("validation_issues", [])
    if validation_issues:
        lines.append("Validation Issues:")
        lines.append(f"  {'Kind':<25} {'Field':<20} {'Count':>6}  Message")
        lines.append(f"  {'-' * 25} {'-' * 20} {'-' * 6}  {'-' * 30}")
        for v in validation_issues:
            kind = v.get("kind", "")
            field = v.get("field", "")
            count = v.get("count", 0)
            msg = v.get("message", "")
            lines.append(f"  {kind:<25} {field:<20} {count:>6}  {msg}")
    else:
        lines.append("Validation: OK (no issues)")

    lines.append("")

    drift_issues = report.get("drift_issues", [])
    if drift_issues:
        lines.append("Drift Issues:")
        lines.append(f"  {'Kind':<25} {'Field':<20} {'Count':>6}  Message")
        lines.append(f"  {'-' * 25} {'-' * 20} {'-' * 6}  {'-' * 30}")
        for d in drift_issues:
            kind = d.get("kind", "")
            field = d.get("field", "")
            count = d.get("count", 0)
            msg = d.get("message", "")
            lines.append(f"  {kind:<25} {field:<20} {count:>6}  {msg}")
    else:
        lines.append("Drift: OK (no issues)")

    return "\n".join(lines)


def _report_output(report: dict[str, Any], out: str, fmt: str) -> None:
    """Output report to file or stdout in the requested format."""
    if fmt == "table":
        text = _format_table(report)
    else:
        text = json.dumps(report, indent=2, sort_keys=True)

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
    op_metrics = get_operation_metrics()

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

    metrics = ContractMetrics()

    logger.info("Validating records...")

    try:
        with OperationTimer("validate") as val_timer:
            validation = validate_records(contract=contract, records=records)
        failed = bool(validation)
        metrics.record_validation(passed=not bool(validation))
        op_metrics.record_schema_check(passed=not bool(validation), record_count=len(records))
        op_metrics.record_timing("validate", val_timer.duration_ms)

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
            with OperationTimer("drift_check") as drift_timer:
                baseline_issues = drift_check(
                    baseline=baseline,
                    current=current,
                    max_missing_rate=float(args.max_missing),
                    max_mean_shift_sigma=float(args.max_mean_shift_sigma),
                )
            failed = failed or bool(baseline_issues)
            metrics.record_drift_check(drift_detected=bool(baseline_issues))
            op_metrics.record_drift_check(drift_detected=bool(baseline_issues))
            op_metrics.record_timing("drift_check", drift_timer.duration_ms)

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

    output_format = getattr(args, "output_format", "json")
    try:
        _report_output(report, str(args.out or ""), output_format)
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to write report: {e}")
        return EXIT_CLI_ERROR

    # Export metrics if --metrics-out is specified
    metrics_out = getattr(args, "metrics_out", None)
    if metrics_out:
        try:
            metrics_path = Path(metrics_out).resolve()
            write_json(metrics_path, metrics.get_metrics())
            logger.info(f"Wrote metrics to: {metrics_path}")
        except (OSError, PermissionError, ValueError) as e:
            logger.error(f"Failed to write metrics: {e}")

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
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    p.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log output format: text (default) or json",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    infer = sub.add_parser("infer", help="Infer a contract from JSONL records.")
    infer.add_argument("--input", required=True, help="Input JSONL file path")
    infer.add_argument("--out", required=True, help="Output contract JSON file path")
    infer.add_argument("--limit", default="5000", help="Max records to process (default: 5000)")
    infer.add_argument("--disallow-extra", action="store_true", help="Disallow extra fields")
    infer.set_defaults(func=_cmd_infer)

    prof = sub.add_parser("profile", help="Compute a baseline profile for drift checks.")
    prof.add_argument("--input", required=True, help="Input JSONL file path")
    prof.add_argument("--contract", required=True, help="Contract JSON file path")
    prof.add_argument("--out", required=True, help="Output profile JSON file path")
    prof.add_argument("--limit", default="50000", help="Max records to process (default: 50000)")
    prof.set_defaults(func=_cmd_profile)

    check = sub.add_parser("check", help="Validate records and optionally drift-check vs baseline.")
    check.add_argument("--input", required=True, help="Input JSONL file path")
    check.add_argument("--contract", required=True, help="Contract JSON file path")
    check.add_argument("--baseline", default="", help="Baseline profile JSON file path")
    check.add_argument("--max-missing", default="0.01", help="Max missing rate (default: 0.01)")
    check.add_argument(
        "--max-mean-shift-sigma",
        default="3.0",
        help="Max mean shift sigma (default: 3.0)",
    )
    check.add_argument("--out", default="", help="Output report file path (default: stdout)")
    check.add_argument(
        "--metrics-out",
        default="",
        help="Output metrics JSON file path (default: none)",
    )
    check.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        dest="output_format",
        help="Output format: json (default) or table",
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
    new_correlation_id()

    log_level = logging.DEBUG if args.verbose else logging.WARNING

    if getattr(args, "log_format", "text") == "json":
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonLogFormatter())
        logging.basicConfig(level=log_level, handlers=[handler])
    else:
        logging.basicConfig(
            level=log_level,
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
