# Data Contracts — Schema contracts and drift detection for ML/LLM data pipelines

**Archetype:** 9 — Developer Tool / CLI Utility
**Standards:** Akiva Build Standard v2.14
**Ontology ID:** TK-05

## Stack
- Language: Python 3.10+
- Test: `pytest -xvs`
- Lint: `ruff check src/ tests/`
- Type-check: `pyright` (basic mode), `mypy src/ --ignore-missing-imports`
- Build: `pip install -e .`

## Verification Commands
| Command | Purpose |
|---------|---------|
| `pytest -xvs` | Run tests |
| `ruff check src/ tests/` | Lint |
| `pyright` | Type-check |

## Current State
- Audit Score: 70/100 (2026-04-04, full v2.14 audit + remediation)
- Prior Audit: 52/100 (2026-03-09, v1.2 audit)
- Tests: 221
- Coverage: 89.73% (branch, threshold 80%)
- All archetype minimums met (D4=8, D7=8, D8=8, D10=8, D11=7, D12=7)
- Path to 75: agent needs KS/chi-squared tests (D13), release automation (D10); human needs branch protection + signed commits

## Key Rules
- Archetype 9: single-purpose CLI tool, zero or minimal dependencies in core
- Tests first, security fixes before features
- One task at a time, verified before moving to next
