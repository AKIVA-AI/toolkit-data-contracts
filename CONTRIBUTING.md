# Contributing to toolkit-data-contracts

## Development Environment Setup

```bash
# Clone the repository
git clone https://github.com/AKIVA-AI/toolkit-data-contracts.git
cd toolkit-data-contracts

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

## Running Tests

```bash
# Run all tests
pytest -xvs

# Run with coverage
pytest --cov=src/toolkit_data_contracts_drift --cov-report=term-missing

# Run a specific test file
pytest tests/test_contracts.py -xvs
```

**Coverage threshold:** 80% (enforced in CI). Do not submit changes that reduce coverage.

## Code Style and Linting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting, and [Pyright](https://github.com/microsoft/pyright) for type checking.

```bash
# Lint
ruff check src/ tests/

# Auto-fix lint issues
ruff check src/ tests/ --fix

# Type check
pyright
```

**Rules enforced:** E (pycodestyle errors), F (pyflakes), I (isort), B (bugbear), UP (pyupgrade).
**Line length:** 100 characters.

All code must use `from __future__ import annotations` for modern type annotation syntax.

## Pull Request Process

1. **Branch:** Create a feature branch from `main` (e.g., `feature/add-csv-support`)
2. **Tests:** Write tests first. All new behavior must have tests.
3. **Lint:** Ensure `ruff check src/ tests/` passes with zero errors
4. **Type-check:** Ensure `pyright` passes
5. **Coverage:** Ensure coverage does not decrease
6. **Commit:** Use clear, descriptive commit messages
7. **PR:** Open a pull request against `main` with:
   - Description of what changed and why
   - Link to any related issues
   - Confirmation that tests pass locally

## Core Principles

- **Zero runtime dependencies.** The core package must only use Python stdlib. If you need an external library, add it as an optional dependency.
- **Deterministic output.** CLI output must be suitable for CI gating. JSON output must be stable and parseable.
- **Tests first.** Write a failing test before implementing new behavior.
- **Security first.** No eval, exec, subprocess, or shell=True. No hardcoded secrets.

## Issue Reporting

- **Bugs:** Use the bug report template in `.github/ISSUE_TEMPLATE/bug_report.md`
- **Features:** Use the feature request template in `.github/ISSUE_TEMPLATE/feature_request.md`
- **Security:** See [SECURITY.md](SECURITY.md) for vulnerability reporting
