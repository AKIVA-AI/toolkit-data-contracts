from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .contract import (
    Profile,
    Profiler,
    RecordValidator,
    SchemaInferrer,
    drift_check,
    load_contract,
)
from .diff import MODES, diff_contracts, summarize
from .io import (
    read_json,
    validate_path_for_read,
    validate_path_for_write,
    write_json,
)
from .monitoring import ContractMetrics
from .odcs import dump_yaml, from_odcs, parse_document, to_odcs
from .presets import PRESETS, Preset, get_preset, parse_tools
from .readers import FORMATS, read_records
from .report import build_envelope, canonical_json, resource_ref

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


def _preset_of(args: argparse.Namespace) -> Preset | None:
    name = getattr(args, "preset", "") or ""
    return get_preset(name) if name else None


def _load_contract_arg(args: argparse.Namespace) -> dict[str, Any]:
    """The contract from ``--contract`` or ``--preset`` (exactly one)."""
    preset = _preset_of(args)
    if preset is not None and args.contract:
        raise ValueError("use either --contract or --preset, not both")
    if preset is not None:
        return preset.contract()
    if not args.contract:
        raise ValueError("--contract or --preset is required")
    return load_contract(read_json(Path(args.contract)))


def _contract_ref(args: argparse.Namespace) -> dict[str, Any] | None:
    preset = _preset_of(args)
    if preset is not None:
        digest = hashlib.sha256(canonical_json(preset.contract()).encode("utf-8")).hexdigest()
        return {"name": f"preset:{preset.name}", "digest": {"sha256": digest}}
    if args.contract and Path(args.contract).is_file():
        return resource_ref(str(args.contract), Path(args.contract))
    return None


def _cmd_infer(args: argparse.Namespace) -> int:
    """Infer a contract (JSON Schema) from JSONL records, streaming."""
    input_path = Path(args.input).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit) or None

    logger.info(f"Inferring contract from: {input_path} (limit={limit or 'all'})")

    inferrer = SchemaInferrer(
        allow_extra_fields=not bool(args.disallow_extra),
        enum_max=int(getattr(args, "enum_max", 0) or 0),
    )
    try:
        for rec in read_records(input_path, fmt=args.input_format, limit=limit):
            inferrer.add(rec)
        logger.info(f"Read {inferrer.records} records")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_CLI_ERROR

    try:
        write_json(out_path, inferrer.contract())
        logger.info(f"Wrote contract to: {out_path}")
        return EXIT_SUCCESS
    except (OSError, PermissionError, ValueError) as e:
        logger.error(f"Failed to write output: {e}")
        return EXIT_CLI_ERROR


def _cmd_profile(args: argparse.Namespace) -> int:
    """Compute a baseline profile for drift checks, streaming."""
    input_path = Path(args.input).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit) or None

    try:
        profiler = Profiler(
            _load_contract_arg(args),
            tokenizer=args.tokenizer,
            language_paths=args.language or [],
            embedding_paths=args.embedding or [],
        )
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read contract: {e}")
        return EXIT_CLI_ERROR

    logger.info(f"Profiling records from: {input_path} (limit={limit or 'all'})")

    try:
        for rec in read_records(input_path, fmt=args.input_format, limit=limit):
            profiler.add(rec)
        logger.info(f"Read {profiler.records} records")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_CLI_ERROR

    try:
        write_json(out_path, profiler.profile().to_json())
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


def _format_markdown(report: dict[str, Any]) -> str:
    """Format check report as GitHub-flavored Markdown (e.g. for a PR comment)."""
    ok = report.get("ok", False)
    lines = [f"### Data contract check: {'PASS' if ok else 'FAIL'}", ""]
    sections = (("Validation issues", "validation_issues"), ("Drift issues", "drift_issues"))
    for title, key in sections:
        items = report.get(key, [])
        if not items:
            lines.append(f"{title}: none")
            lines.append("")
            continue
        lines.append(f"{title}:")
        lines.append("")
        lines.append("| Kind | Field | Count | Message |")
        lines.append("|---|---|---:|---|")
        for v in items:
            msg = str(v.get("message", "")).replace("|", "\\|")
            field = v.get("field", "")
            lines.append(f"| {v.get('kind', '')} | `{field}` | {v.get('count', 0)} | {msg} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_text(text: str, out: str) -> None:
    """Write text to ``out`` (after path checks), or print it to stdout."""
    if out:
        out_path = validate_path_for_write(Path(out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        logger.info(f"Wrote report to: {out_path}")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _render_check(legacy: dict[str, Any], envelope: dict[str, Any] | None, fmt: str) -> str:
    if fmt == "table":
        return _format_table(legacy) + "\n"
    if fmt == "markdown":
        return _format_markdown(legacy)
    if fmt == "json-legacy" or envelope is None:
        return json.dumps(legacy, indent=2, sort_keys=True) + "\n"
    return canonical_json(envelope)


CHECK_KIND = "data.check"


def _check_inputs(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Digests of the contract (or preset), baseline and tools files that exist."""
    refs: list[dict[str, Any]] = []
    contract_ref = _contract_ref(args)
    if contract_ref is not None:
        refs.append(contract_ref)
    for arg in (args.baseline, getattr(args, "tools", "")):
        if arg and Path(arg).is_file():
            refs.append(resource_ref(str(arg), Path(arg)))
    return refs


def _emit_check_error(args: argparse.Namespace, message: str, exit_code: int) -> int:
    """Write an ``error`` envelope when the input file can at least be hashed.

    If the input itself cannot be read there is no subject to report on, so
    only the log message and the exit code signal the failure.
    """
    fmt = getattr(args, "output_format", "json")
    input_path = Path(args.input)
    if fmt == "json" and input_path.is_file():
        try:
            envelope = build_envelope(
                kind=CHECK_KIND,
                subject=[resource_ref(str(args.input), input_path)],
                inputs=_check_inputs(args),
                verdict="error",
                exit_code=exit_code,
                summary={"ok": False},
                details={"error": message},
            )
            _write_text(canonical_json(envelope), str(args.out or ""))
        except (OSError, ValueError) as e:
            logger.error(f"Failed to write error report: {e}")
    return exit_code


def _cmd_check(args: argparse.Namespace) -> int:
    """Validate records and optionally check for drift."""
    input_path = Path(args.input).resolve()
    output_format = getattr(args, "output_format", "json")

    if args.out:
        try:
            validate_path_for_write(Path(args.out))
        except ValueError as e:
            logger.error(f"Invalid --out path: {e}")
            return EXIT_CLI_ERROR

    preset: Preset | None = None
    try:
        preset = _preset_of(args)
        contract = _load_contract_arg(args)
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read contract: {e}")
        return _emit_check_error(args, f"contract: {e}", EXIT_CLI_ERROR)

    tools = None
    tools_arg = getattr(args, "tools", "") or ""
    try:
        if tools_arg:
            if preset is None or preset.name not in TOOL_PRESETS:
                raise ValueError(f"--tools needs --preset {' or '.join(TOOL_PRESETS)}")
            tools = parse_tools(read_json(Path(tools_arg)))
        elif preset is not None and preset.needs_tools:
            raise ValueError(f"--preset {preset.name} needs --tools")
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to load tools: {e}")
        return _emit_check_error(args, f"tools: {e}", EXIT_CLI_ERROR)

    preset_checks = preset.checks(tools) if preset is not None else None
    validator = RecordValidator(
        contract,
        strict_integer=bool(getattr(args, "strict_integer", False)),
        checks=[preset_checks] if preset_checks is not None else [],
    )

    thresholds: dict[str, Any] = {
        "max_missing_rate": float(args.max_missing),
        "max_mean_shift_sigma": float(args.max_mean_shift_sigma),
        "max_null_rate_increase": float(getattr(args, "max_null_increase", 0.10)),
        "max_psi": float(getattr(args, "max_psi", 0.25)),
        "max_length_psi": float(getattr(args, "max_length_psi", 0.25)),
        "max_centroid_distance": float(getattr(args, "max_centroid_distance", 0.2)),
        "centroid_metric": str(getattr(args, "centroid_metric", "euclidean")),
    }
    baseline: Profile | None = None
    profiler: Profiler | None = None
    if args.baseline:
        baseline_path = Path(args.baseline).resolve()
        logger.info(f"Loading baseline from: {baseline_path}")
        try:
            baseline = Profile.from_json(read_json(baseline_path))
            profiler = Profiler.like(contract, baseline)
        except (ValueError, FileNotFoundError) as e:
            logger.error(f"Failed to process baseline: {e}")
            return _emit_check_error(args, f"baseline: {e}", EXIT_CLI_ERROR)

    logger.info(f"Validating records from: {input_path}")
    metrics = ContractMetrics()

    # One streaming pass: validate every record and, with a baseline, profile it.
    try:
        for rec in read_records(input_path, fmt=args.input_format):
            validator.add(rec)
            if profiler is not None:
                profiler.add(rec)
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to read input: {e}")
        return _emit_check_error(args, f"input: {e}", EXIT_CLI_ERROR)

    record_count = validator.records
    logger.info(f"Read {record_count} records")
    validation = validator.issues()
    failed = bool(validation)
    metrics.record_validation(passed=not failed)
    if validation:
        logger.warning(f"Found {len(validation)} validation issues")

    baseline_issues = []
    if baseline is not None and profiler is not None:
        logger.info("Checking for drift...")
        try:
            baseline_issues = drift_check(
                baseline=baseline, current=profiler.profile(), **thresholds
            )
        except ValueError as e:
            logger.error(f"Drift check failed: {e}")
            return _emit_check_error(args, f"drift: {e}", EXIT_CLI_ERROR)
        failed = failed or bool(baseline_issues)
        metrics.record_drift_check(drift_detected=bool(baseline_issues))
        if baseline_issues:
            logger.warning(f"Found {len(baseline_issues)} drift issues")

    exit_code = EXIT_CHECK_FAILED if failed else EXIT_SUCCESS
    validation_rows = [dict(v.__dict__) for v in validation]
    drift_rows = [dict(v.__dict__) for v in baseline_issues]
    legacy = {
        "ok": not failed,
        "validation_issues": validation_rows,
        "drift_issues": drift_rows,
    }

    try:
        envelope = None
        if output_format == "json":
            envelope = build_envelope(
                kind=CHECK_KIND,
                subject=[resource_ref(str(args.input), input_path)],
                inputs=_check_inputs(args),
                verdict="fail" if failed else "pass",
                exit_code=exit_code,
                summary={
                    "ok": not failed,
                    "records": record_count,
                    "validation_issues": len(validation_rows),
                    "invalid_records": validator.invalid_records,
                    "invalid_occurrences": sum(int(v["count"]) for v in validation_rows),
                    "drift_checked": bool(args.baseline),
                    "drift_issues": len(drift_rows),
                    **(preset_checks.summary() if preset_checks is not None else {}),
                },
                details={
                    "preset": preset.name if preset is not None else None,
                    "validation_issues": validation_rows,
                    "drift_issues": drift_rows,
                    "thresholds": thresholds if args.baseline else {},
                },
            )
        _write_text(_render_check(legacy, envelope, output_format), str(args.out or ""))
    except (OSError, PermissionError, ValueError) as e:
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
    else:
        logger.info("Check passed")
    return exit_code


def _cmd_odcs_export(args: argparse.Namespace) -> int:
    """Export a contract as an ODCS v3 document (YAML, or JSON for a .json path)."""
    try:
        contract = read_json(Path(args.contract))
        doc, lossy = to_odcs(
            contract,
            contract_id=args.id or None,
            name=args.name or None,
            version=args.contract_version,
            status=args.status,
            object_name=args.object_name,
        )
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Failed to export ODCS: {e}")
        return EXIT_CLI_ERROR
    if lossy:
        logger.warning(
            "ODCS cannot express part of this contract; the exact JSON Schema is embedded "
            "as the 'jsonSchema' custom property: " + "; ".join(lossy)
        )
    try:
        text = (
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
            if str(args.out).lower().endswith(".json")
            else dump_yaml(doc)
        )
        _write_text(text, str(args.out))
    except (OSError, ValueError) as e:
        logger.error(f"Failed to write ODCS: {e}")
        return EXIT_CLI_ERROR
    return EXIT_SUCCESS


def _cmd_odcs_import(args: argparse.Namespace) -> int:
    """Import one schema object of an ODCS v3 document as a contract."""
    try:
        path = validate_path_for_read(Path(args.input))
        doc = parse_document(path.read_text(encoding="utf-8"))
        contract, warnings = from_odcs(doc, object_name=args.object or None)
    except (ValueError, FileNotFoundError, OSError) as e:
        logger.error(f"Failed to import ODCS: {e}")
        return EXIT_CLI_ERROR
    for w in warnings:
        logger.warning(w)
    try:
        write_json(Path(args.out), contract)
    except (OSError, ValueError) as e:
        logger.error(f"Failed to write contract: {e}")
        return EXIT_CLI_ERROR
    return EXIT_SUCCESS


DIFF_KIND = "data.diff"


def _short(v: Any) -> str:
    text = json.dumps(v, sort_keys=True, ensure_ascii=False) if v is not None else "-"
    return text if len(text) <= 60 else text[:57] + "..."


def _render_diff(rows: list[dict[str, Any]], summary: dict[str, Any], fmt: str, new: str) -> str:
    if fmt == "github":
        lines = []
        for r in rows:
            level = "error" if r["breaking"] else "notice"
            title = "Breaking contract change" if r["breaking"] else "Contract change"
            msg = f"{r['path']}: {r['change']} ({r['direction']})"
            lines.append(f"::{level} file={new},title={title}::{msg}")
        lines.append(
            f"{summary['breaking']} breaking / {summary['changes']} changes "
            f"(mode {summary['mode']})"
        )
        return "\n".join(lines) + "\n"
    if fmt == "markdown":
        head = "BREAKING" if summary["breaking"] else "no breaking changes"
        lines = [
            f"### Contract diff ({summary['mode']}): {head}",
            "",
            f"{summary['breaking']} breaking, {summary['non_breaking']} non-breaking.",
            "",
        ]
        if rows:
            lines += ["| | Path | Change | Direction | Old | New |", "|---|---|---|---|---|---|"]
            for r in rows:
                mark = "breaking" if r["breaking"] else ""
                old = _short(r["old"]).replace("|", "\\|")
                new_v = _short(r["new"]).replace("|", "\\|")
                lines.append(
                    f"| {mark} | `{r['path']}` | {r['change']} | {r['direction']} | "
                    f"`{old}` | `{new_v}` |"
                )
        return "\n".join(lines) + "\n"
    lines = [
        f"Mode: {summary['mode']}  Breaking: {summary['breaking']}  Changes: {summary['changes']}"
    ]
    for r in rows:
        mark = "BREAKING" if r["breaking"] else "ok"
        lines.append(
            f"  {mark:<9} {r['direction']:<10} {r['path']:<30} {r['change']}: "
            f"{_short(r['old'])} -> {_short(r['new'])}"
        )
    return "\n".join(lines) + "\n"


def _cmd_diff(args: argparse.Namespace) -> int:
    """Classify the changes between two contracts as breaking or not."""
    fmt = args.output_format

    def error(message: str) -> int:
        logger.error(message)
        new_path = Path(args.new)
        if fmt == "json" and new_path.is_file():
            inputs = (
                [resource_ref(str(args.old), Path(args.old))] if Path(args.old).is_file() else []
            )
            env = build_envelope(
                kind=DIFF_KIND,
                subject=[resource_ref(str(args.new), new_path)],
                inputs=inputs,
                verdict="error",
                exit_code=EXIT_CLI_ERROR,
                summary={"ok": False},
                details={"error": message},
            )
            try:
                _write_text(canonical_json(env), str(args.out or ""))
            except (OSError, ValueError) as e:
                logger.error(f"Failed to write report: {e}")
        return EXIT_CLI_ERROR

    try:
        old = read_json(Path(args.old))
        new = read_json(Path(args.new))
        changes = diff_contracts(old, new)
        summary = summarize(changes, args.mode)
    except (ValueError, FileNotFoundError) as e:
        return error(f"diff: {e}")
    rows = [c.to_json(args.mode) for c in changes]
    exit_code = EXIT_SUCCESS if summary["ok"] else EXIT_CHECK_FAILED
    try:
        if fmt == "json":
            env = build_envelope(
                kind=DIFF_KIND,
                subject=[resource_ref(str(args.new), Path(args.new))],
                inputs=[resource_ref(str(args.old), Path(args.old))],
                verdict="pass" if summary["ok"] else "fail",
                exit_code=exit_code,
                summary=summary,
                details={"changes": rows},
            )
            text = canonical_json(env)
        else:
            text = _render_diff(rows, summary, fmt, str(args.new))
        _write_text(text, str(args.out or ""))
    except (OSError, ValueError) as e:
        logger.error(f"Failed to write report: {e}")
        return EXIT_CLI_ERROR
    return exit_code


TOOL_PRESETS = ("openai-chat", "anthropic-messages", "tool-calls")


def _cmd_presets(args: argparse.Namespace) -> int:
    """List built-in presets, or print one preset's contract."""
    if args.presets_cmd == "list":
        width = max(len(n) for n in PRESETS)
        for name, p in PRESETS.items():
            sys.stdout.write(f"{name:<{width}}  {p.description}\n")
        return EXIT_SUCCESS
    try:
        contract = get_preset(args.name).contract()
    except ValueError as e:
        logger.error(str(e))
        return EXIT_CLI_ERROR
    text = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    try:
        _write_text(text, str(args.out or ""))
    except (OSError, ValueError) as e:
        logger.error(f"Failed to write contract: {e}")
        return EXIT_CLI_ERROR
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
    infer.add_argument("--input", required=True, help="Input file (JSONL, Parquet or CSV)")
    infer.add_argument(
        "--input-format",
        choices=list(FORMATS),
        default="auto",
        help="auto (by extension, default), jsonl, parquet or csv (parquet/csv need the "
        "parquet extra)",
    )
    infer.add_argument("--out", required=True, help="Output contract JSON file path")
    infer.add_argument(
        "--limit", default="0", help="Max records to read (default: 0 = the whole file)"
    )
    infer.add_argument(
        "--disallow-extra",
        action="store_true",
        help="Set additionalProperties: false on every object (reject undeclared keys)",
    )
    infer.add_argument(
        "--enum-max",
        type=int,
        default=0,
        help="Give string fields with at most N distinct values an enum (default: 0 = off)",
    )
    infer.set_defaults(func=_cmd_infer)

    prof = sub.add_parser("profile", help="Compute a baseline profile for drift checks.")
    prof.add_argument("--input", required=True, help="Input file (JSONL, Parquet or CSV)")
    prof.add_argument(
        "--input-format",
        choices=list(FORMATS),
        default="auto",
        help="auto (by extension, default), jsonl, parquet or csv (parquet/csv need the "
        "parquet extra)",
    )
    prof.add_argument("--contract", default="", help="Contract JSON file path")
    prof.add_argument(
        "--preset", default="", choices=["", *PRESETS], help="Use a built-in contract instead"
    )
    prof.add_argument("--out", required=True, help="Output profile JSON file path")
    prof.add_argument(
        "--limit", default="0", help="Max records to read (default: 0 = the whole file)"
    )
    prof.add_argument(
        "--tokenizer",
        default="whitespace",
        help="Token counter for text stats: whitespace (default) or tiktoken:<encoding> "
        "(needs the tiktoken extra)",
    )
    prof.add_argument(
        "--language",
        action="append",
        metavar="PATH",
        help="Also profile the detected language of this string path (repeatable; needs the "
        "lang extra)",
    )
    prof.add_argument(
        "--embedding",
        action="append",
        metavar="PATH",
        help="Profile the centroid of the numeric vectors at this path (repeatable)",
    )
    prof.set_defaults(func=_cmd_profile)

    check = sub.add_parser("check", help="Validate records and optionally drift-check vs baseline.")
    check.add_argument("--input", required=True, help="Input file (JSONL, Parquet or CSV)")
    check.add_argument(
        "--input-format",
        choices=list(FORMATS),
        default="auto",
        help="auto (by extension, default), jsonl, parquet or csv (parquet/csv need the "
        "parquet extra)",
    )
    check.add_argument("--contract", default="", help="Contract JSON file path")
    check.add_argument(
        "--preset",
        default="",
        choices=["", *PRESETS],
        help="Use a built-in contract for LLM data instead of --contract",
    )
    check.add_argument(
        "--tools",
        default="",
        help="Tool definitions JSON (OpenAI or Anthropic format) for checking tool-call "
        "arguments with the openai-chat, anthropic-messages and tool-calls presets",
    )
    check.add_argument("--baseline", default="", help="Baseline profile JSON file path")
    check.add_argument("--max-missing", default="0.01", help="Max missing rate (default: 0.01)")
    check.add_argument(
        "--max-mean-shift-sigma",
        default="3.0",
        help="Max mean shift sigma (default: 3.0)",
    )
    check.add_argument(
        "--max-null-increase",
        default="0.10",
        help="Max absolute rise in a field's null rate vs baseline (default: 0.10)",
    )
    check.add_argument(
        "--max-psi",
        default="0.25",
        help="Max Population Stability Index for string/boolean fields (default: 0.25)",
    )
    check.add_argument(
        "--max-length-psi",
        default="0.25",
        help="Max PSI of text length and token-count histograms (default: 0.25)",
    )
    check.add_argument(
        "--max-centroid-distance",
        default="0.2",
        help="Max distance between baseline and current embedding centroids (default: 0.2)",
    )
    check.add_argument(
        "--centroid-metric",
        choices=["euclidean", "cosine"],
        default="euclidean",
        help="Distance for embedding centroid drift (default: euclidean)",
    )
    check.add_argument(
        "--strict-integer",
        action="store_true",
        help="Reject fractional values on integer-only fields "
        "(default: integer and number are one JSON numeric type)",
    )
    check.add_argument("--out", default="", help="Output report file path (default: stdout)")
    check.add_argument(
        "--metrics-out",
        default="",
        help="Output metrics JSON file path (default: none)",
    )
    check.add_argument(
        "--format",
        choices=["json", "table", "markdown", "json-legacy"],
        default="json",
        dest="output_format",
        help="Output format: json (default; report envelope v1, an in-toto Statement in "
        "canonical JSON), table, markdown, or json-legacy (the pre-1.0 report, deprecated "
        "and removed in the next minor version)",
    )
    check.set_defaults(func=_cmd_check)

    diff = sub.add_parser(
        "diff", help="Classify changes between two contracts as breaking or non-breaking."
    )
    diff.add_argument("--old", required=True, help="Old (base) contract JSON")
    diff.add_argument("--new", required=True, help="New (proposed) contract JSON")
    diff.add_argument(
        "--mode",
        choices=list(MODES),
        default="backward",
        help="backward (default): tightening is breaking; forward: loosening is breaking; "
        "full: both",
    )
    diff.add_argument(
        "--format",
        choices=["json", "table", "markdown", "github"],
        default="json",
        dest="output_format",
        help="json (report envelope, default), table, markdown, or github (workflow annotations)",
    )
    diff.add_argument("--out", default="", help="Output file (default: stdout)")
    diff.set_defaults(func=_cmd_diff)

    presets = sub.add_parser("presets", help="List or show built-in contracts for LLM data.")
    psub = presets.add_subparsers(dest="presets_cmd", required=True)
    psub.add_parser("list", help="List presets.").set_defaults(func=_cmd_presets)
    show = psub.add_parser("show", help="Print a preset's contract (JSON Schema).")
    show.add_argument("name", help="Preset name")
    show.add_argument("--out", default="", help="Write to a file instead of stdout")
    show.set_defaults(func=_cmd_presets)

    odcs = sub.add_parser(
        "odcs", help="Import or export Open Data Contract Standard (ODCS) v3 documents."
    )
    osub = odcs.add_subparsers(dest="odcs_cmd", required=True)
    exp = osub.add_parser("export", help="Write a contract as an ODCS v3.1.0 document.")
    exp.add_argument("--contract", required=True, help="Contract JSON file path")
    exp.add_argument(
        "--out", required=True, help="Output path (.yaml/.yml needs the odcs extra; .json always)"
    )
    exp.add_argument("--id", default="", help="ODCS id (default: a UUID derived from the schema)")
    exp.add_argument("--name", default="", help="ODCS name (default: the contract name)")
    exp.add_argument(
        "--contract-version", default="1.0.0", help="ODCS version field (default: 1.0.0)"
    )
    exp.add_argument("--status", default="draft", help="ODCS status (default: draft)")
    exp.add_argument(
        "--object-name", default="records", help="Name of the ODCS schema object (default: records)"
    )
    exp.set_defaults(func=_cmd_odcs_export)
    imp = osub.add_parser("import", help="Read one ODCS v3 schema object as a contract.")
    imp.add_argument("--input", required=True, help="ODCS YAML or JSON file")
    imp.add_argument("--out", required=True, help="Output contract JSON file path")
    imp.add_argument(
        "--object", default="", help="Schema object name (needed when there are several)"
    )
    imp.set_defaults(func=_cmd_odcs_import)

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
