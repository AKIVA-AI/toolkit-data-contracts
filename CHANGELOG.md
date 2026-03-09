# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
