# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-09-26

Contracts for LLM-shaped data. Highlights: JSON Schema contracts with nested
validation and drift, LLM presets with tool-call argument checks, ODCS v3
import/export, text/token/language/embedding drift, a breaking-change `diff`
with a GitHub Action, the shared report envelope, and Parquet/CSV input.

### Release and project files

- The PyPI distribution name is now `toolkit-data-contracts`, matching the repository (was `toolkit-data-contracts-drift`, never published). Import paths and CLI commands are unchanged.
- Release workflow: a `v*` tag runs the tests, builds the sdist and wheel,
  checks them with `twine check --strict` (twine 6.1 or newer, which reads the
  Metadata 2.4 that setuptools 77+ writes), installs the wheel and checks its
  version against the tag, and attaches both files to a GitHub Release. The
  PyPI upload (Trusted Publishing) runs only when the repository variable
  `PUBLISH_TO_PYPI` is `true`. See `RELEASING.md`.
- CI builds and checks the package the same way on every pull request.
- Package metadata: SPDX license expression `Apache-2.0` with `LICENSE` and
  `NOTICE` in the distributions, author AKIVA AI, LLC, and links to the
  documentation, issues and changelog.
- Added `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), issue and pull request
  templates and `RELEASING.md`. `SECURITY.md` lists the supported versions and
  the private reporting channel.
- CI runs pyright as well as mypy, and `pip-audit` with every optional extra
  installed (it audited only the core, which has no dependencies).

### Added

- Parquet and CSV input (`--input-format`, optional extra `parquet` =
  pyarrow), streamed batch by batch; Arrow dates, decimals and binary values
  become JSON values; NaN and infinity are rejected as in JSONL.
- A five-minute README example on a 40-row sample of the public UltraChat
  200k dataset (`examples/data/`), run in CI by `tests/test_readme_walkthrough.py`.
- `diff` command: classifies contract changes as tightening, loosening,
  both or annotation, and as breaking under `--mode backward|forward|full`;
  outputs the report envelope (`data.diff`), a table, Markdown, or GitHub
  workflow annotations. A composite GitHub Action (`action.yml`) runs it on
  pull requests; CI self-tests the action.
- Text drift for LLM data: every string path gets character and token-count
  histograms (power-of-two bins) compared with PSI (`drift_text_length`,
  `drift_token_count`, `check --max-length-psi`). Tokens are whitespace-split
  or counted with tiktoken (`profile --tokenizer tiktoken:<encoding>`, extra
  `tiktoken`). Opt-in language distribution drift (`profile --language PATH`,
  extra `lang`) and embedding-centroid drift (`profile --embedding PATH`,
  `check --max-centroid-distance`, `--centroid-metric`). Profiles store these
  settings under `config` and `check` reuses them.
- LLM presets (`check --preset`, `profile --preset`, `presets list|show`):
  `openai-chat`, `anthropic-messages`, `tool-calls`, `sft`, `dpo` and
  `rag-chunks`, each a JSON Schema plus record checks JSON Schema cannot
  express. Tool-call arguments are validated against the tool's own JSON
  Schema (`--tools`, or the row's `tools`), with unknown tools and orphan tool
  results reported; preference rows flag identical pairs; RAG chunks flag
  duplicate ids, inconsistent embedding sizes and inverted offsets.
- `odcs export` / `odcs import`: convert contracts to and from the Open Data
  Contract Standard. Export writes ODCS v3.1.0 and is validated in tests
  against the official ODCS JSON Schema; import reads v3.0 to v3.2 (including
  `enum`, `map` and `vector`). Lossy exports embed the exact JSON Schema as
  the `jsonSchema` custom property. New optional extra `odcs` (PyYAML).
- **Contract v2 = JSON Schema.** Contracts are `{"version": 2, "schema": ...}`
  with a draft 2020-12 JSON Schema. A new stdlib-only validator (`schema.py`)
  implements the common subset (nested objects, arrays with item schemas,
  enums, const, numeric ranges, string lengths and patterns, combinators,
  same-document `$ref`) and is tested against the official
  JSON-Schema-Test-Suite. Unsupported keywords are rejected (exit 2) rather
  than ignored. Bare JSON Schema files and v1 contracts are accepted.
- `infer` describes nested objects and arrays at every level, with
  nullability, and `--enum-max N` adds enums for low-cardinality strings.
- Profiles and drift cover every declared path, including nested keys
  (`meta.source`) and array items (`messages[].role`).
- `infer`, `profile` and `check` stream JSONL in a single pass (constant
  memory); `check` validates and profiles in the same pass.
- The report `summary` gains `invalid_records`.
- `check` writes the shared **report envelope v1** by default: an in-toto
  Statement v1 in canonical JSON with SHA-256 digests of the batch, contract
  and baseline, a `pass`/`fail`/`error` verdict that matches the exit code,
  a `summary` block for CI gates and per-issue `details`. Bad input that can
  still be hashed produces an `error` report (exit 2). The spec and JSON Schema
  are committed as `docs/report-envelope.md` and `schemas/report-envelope.v1.json`.
  `SOURCE_DATE_EPOCH` pins `created_at` for reproducible reports.
- `check --format markdown` for PR comments.
- Categorical-distribution drift (`drift_categorical`): Population Stability
  Index on string/boolean value counts, `check --max-psi` (default 0.25).
  Profiles now store value counts for fields with up to 50 distinct values.
- Null-rate drift (`drift_null_rate`): rise in the share of null values,
  `check --max-null-increase` (default 0.10).
- `check --strict-integer` to reject fractional values on integer-only fields.

### Changed

- **Breaking:** `infer` writes version 2 contracts and `profile` writes
  version 2 profiles (paths as keys, plus a `records` count). Version 1
  contracts and profiles are still read. A v1 field with no `types` still
  accepts no value.
- Relicensed from MIT to Apache-2.0. Releases before this change remain
  available under MIT. Added a `NOTICE` file.
- **Breaking:** the default `check` JSON output is now the report envelope.
  The old `{ok, validation_issues, drift_issues}` object is still available
  with `--format json-legacy` (deprecated; removed in the next minor version).
- Integer and number are now one JSON numeric type during validation by
  default, so a field inferred from whole numbers accepts `10.5`.
- `infer` and `profile` read the whole input by default (`--limit 0`).
  `infer` previously stopped at 5,000 rows.
- `check --out` applies the same output-path checks as the other commands.
- README, QUICKSTART and SECURITY rewritten to describe what the tool does
  today, with a Working / Partial / Planned status table.
- Dependabot opens one grouped weekly PR per ecosystem.
- CI dependency audit uses `pip-audit .` on the declared dependencies instead
  of the deprecated `safety check`, which scanned the CI runner's own packages.

### Fixed

- `NaN`, `Infinity` and overflowing numbers are rejected as invalid JSON.
  A NaN mean used to make the mean-shift check pass silently.

### Removed

- Unused modules: `config.py` (env-var settings that changed nothing),
  `observability.py`, the health-check helpers in `monitoring.py`, and the
  `control_plane` package. None were reachable from the CLI.
- `.env.example` and `DEPLOYMENT.md`.

## [0.1.0] - 2026-03-09

### Added

- Contract inference from JSONL records (`infer` command)
- Baseline profiling for drift detection (`profile` command)
- Record validation and drift checking (`check` command)
- `--version` flag for CLI version display
- `--format` flag (`json`, `table`) for check command output
- `--metrics-out` flag for exporting validation/drift metrics
- `--log-format json` for structured JSON logging
- `--verbose` flag for DEBUG-level logging
- Dependabot configuration for pip and GitHub Actions
- Pre-commit configuration with ruff and pyright
- Bandit and Safety security scans (blocking in CI)
- PyPI publish workflow via GitHub Actions
- Comprehensive test suite (100+ tests, 80%+ coverage)
- Zero runtime dependencies (stdlib only)
- Docker and Docker Compose support
- Full documentation: README, QUICKSTART, DEPLOYMENT, CONTRIBUTING, SECURITY

### Fixed

- Removed dead BATCH_SIZE/MAX_WORKERS config (never wired to behavior)
- Fixed placeholder URLs in README.md and DEPLOYMENT.md
- Fixed `datetime.utcnow()` deprecation (uses `datetime.now(UTC)`)
