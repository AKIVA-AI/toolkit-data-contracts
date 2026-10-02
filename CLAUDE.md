# toolkit-data-contracts: notes for coding agents

Stdlib-only Python CLI (`toolkit-contracts`) that infers JSONL schema contracts,
validates batches, and checks drift against a baseline profile.

## Commands

| Task | Command |
|------|---------|
| Install for development | `pip install -e ".[dev]"` |
| Tests | `pytest` |
| Lint | `ruff check src/ tests/` and `ruff format --check src/ tests/` |
| Type-check | `pyright` (basic mode, `src/` only); CI also runs `mypy src/ --ignore-missing-imports` |

## Layout

- `src/toolkit_data_contracts_drift/contract.py`: contract loading (v1 -> v2), streaming inference, validation, profiling, drift.
- `src/toolkit_data_contracts_drift/schema.py`: JSON Schema subset validator. Run the official suite (`tests/test_json_schema_suite.py`) after any change; keep its UNSUPPORTED list exact.
- `src/toolkit_data_contracts_drift/odcs.py`: ODCS v3 import/export. Exports must validate against the pinned official ODCS schema in `tests/fixtures/odcs/`.
- `src/toolkit_data_contracts_drift/presets.py`: LLM preset schemas and record checks. Preset tests cross-check every schema verdict with the `jsonschema` reference validator.
- `src/toolkit_data_contracts_drift/diff.py`: contract diff. Every direction claim in `tests/test_diff.py` has a witness record checked with `jsonschema`; keep adding one per new rule.
- `src/toolkit_data_contracts_drift/types.py`: contract TypedDicts, `ValidationIssue`, `json_type`.
- `src/toolkit_data_contracts_drift/io.py`: strict JSON/JSONL reading and path checks.
- `src/toolkit_data_contracts_drift/cli.py`: argparse CLI and exit codes.
- `src/toolkit_data_contracts_drift/monitoring.py`: `ContractMetrics` for `check --metrics-out`.
- `src/toolkit_data_contracts_drift/report.py`: report envelope v1; spec in `docs/report-envelope.md`, schema in `schemas/` (keep both identical to the other toolkits).
- `docs/CODEBASE_MAP.md`: fuller map and data flow.

## Conventions

- No runtime dependencies. Anything else goes in an optional extra (`odcs` = PyYAML), imported lazily.
- Write a failing test before changing behavior; tests exercise real behavior
  (CLI runs, real profiles), not just construction.
- Exit codes are a public contract: 0 pass, 2 CLI/input error, 3 unexpected, 4 check failed.
- Contract and profile JSON formats must stay readable by older files: add
  optional keys, and skip a check when a baseline lacks the data it needs.
- Keep the README status table in sync with what the code actually does.
