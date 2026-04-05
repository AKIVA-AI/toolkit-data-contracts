# Toolkit Data Contracts — Full System Audit

**Date:** 2026-04-04
**Auditor:** Claude (Akiva Build Standard v2.14)
**Archetype:** 9 — Developer Tool / CLI Utility
**Previous Audit:** 2026-03-09 (52/100, recalculated 58/100)
**Declared Agentic Engineering Level:** N/A (CLI tool)
**Declared Agent Runtime Tier:** none
**Standards Baseline:** v2.14 Build Standard, Archetypes v2.0, Repository Controls v1.3, Sprint Protocol v3.4

---

## Standards Evaluated

### Core Standards
- [x] Build Standard v2.14 — all 24 dimensions scored
- [x] Archetypes v2.0 — Archetype 9 weights and minimums applied
- [x] Sprint Execution Protocol v3.4 — gate evidence checked
- [x] Repository Controls v1.3 — SECURITY.md, CONTRIBUTING.md, CI patterns, Dependabot, SBOM
- [x] Pre-Push Verification v1.2 — lint, type-check, test commands verified

### AI Standards
- [x] AI Service Standard v1.5 — N/A (no AI service integration; tool validates data schemas, not AI services)
- [x] AI Agent Runtime Standard v1.8 — Partial: control_plane/contracts.py implements ToolSpec, AuthorityBoundary, PermissionScope; no runtime execution
- [x] AI Resilience Standard v1.3 — N/A (no AI-driven behavior)
- [x] Knowledge Representation Standard v1.0 — N/A (contract schemas are domain-specific, not formal ontology)
- [x] BENCHMARK Standard v1.5 — N/A (no self-improvement or benchmark capabilities)

### Domain-Specific Standards
- [x] Integration and Webhook Standard v1.1 — N/A (no integrations or webhooks)
- [x] Data Isolation Standard v1.1 — N/A (no multi-tenancy)
- [x] Application Composition Standard v1.4 — Partial: control_plane config hierarchy follows platform pattern
- [x] User Trust Standard v1.4 — N/A (CLI tool, no user-facing trust surfaces)
- [x] Compliance Framework Standard — Minimal: no SBOM, no signed releases
- [x] SBOM & Supply Chain Standard — Not met: no CycloneDX/SBOM generation
- [x] AI Governance & Ethics Standard — N/A
- [x] Change Management Standard — Partial: CHANGELOG exists, no formal CAB process

---

## Audit Metadata

| Metric | Value |
|--------|-------|
| Source LOC | 1,692 (12 Python files in src/) |
| Test LOC | 2,906 (12 test files) |
| Test count | 221 (all passing) |
| Coverage | 89.44% (branch) |
| Coverage threshold | 80% (enforced) |
| Runtime deps | 0 |
| Dev deps | pytest, pytest-cov, ruff, pyright |
| CI jobs | 7 (test, security, lint, sbom, build, docker, all-checks) + publish |
| Python versions tested | 3.10, 3.11, 3.12 |
| Lint status | Clean (ruff, all checks passed) |
| CODEBASE_MAP.md | Present (created 2026-04-04) |

---

## Composite Score: 70/100

| Dim | Dimension | Weight | Score | Prior | Delta | Weighted | Min | Status |
|-----|-----------|--------|-------|-------|-------|----------|-----|--------|
| 1 | Architecture Integrity | 8% | 7 | 7 | 0 | 0.56 | -- | OK |
| 2 | Auth & Identity | 2% | 3 | 2 | +1 | 0.06 | -- | OK |
| 3 | RLS / Multi-Tenancy | 0% | 0 | 0 | 0 | 0.00 | -- | N/A |
| 4 | API Surface Quality | 12% | 8 | 7 | +1 | 0.96 | 7 | MET |
| 5 | Data Layer | 2% | 5 | 4 | +1 | 0.10 | -- | OK |
| 6 | Frontend Quality | 0% | 0 | 0 | 0 | 0.00 | -- | N/A |
| 7 | Testing & QA | 15% | 8 | 6 | +2 | 1.20 | 7 | MET |
| 8 | Security Posture | 10% | 8 | 6 | +2 | 0.80 | 6 | MET |
| 9 | Observability | 5% | 7 | 4 | +3 | 0.35 | -- | OK |
| 10 | CI/CD | 10% | 8 | 6 | +2 | 0.80 | 6 | MET |
| 11 | Documentation | 10% | 7 | 6 | +1 | 0.70 | 6 | MET |
| 12 | Domain Capability | 8% | 7 | -- | -- | 0.56 | 6 | MET |
| 13 | AI/ML Capability | 5% | 4 | -- | -- | 0.20 | -- | OK |
| 14 | Connectivity | 2% | 3 | -- | -- | 0.06 | -- | OK |
| 15 | Agentic UI/UX | 0% | 0 | 0 | 0 | 0.00 | -- | N/A |
| 16 | UX Quality | 0% | 0 | 0 | 0 | 0.00 | -- | N/A |
| 17 | User Journey | 0% | 0 | 0 | 0 | 0.00 | -- | N/A |
| 18 | Zero Trust / Dep Mgmt | 2% | 7 | 8 | -1 | 0.14 | -- | OK |
| 19 | Enterprise Security | 5% | 7 | 7 | 0 | 0.35 | -- | OK |
| 20 | Operational Readiness | 2% | 6 | 5 | +1 | 0.12 | -- | OK |
| 21 | Agentic Workspace | 2% | 4 | 1 | +3 | 0.08 | -- | OK |
| | **TOTAL** | **100%** | | | | **7.04** | | |

**Composite: 70.4 -> 70/100** (prior: 58/100, delta: +12)

### Post-Remediation Changes (same session)

| Dim | Pre-Fix | Post-Fix | Change | Reason |
|-----|---------|----------|--------|--------|
| D8 | 7 | 8 | +1 | SECURITY.md expanded to full Repo Controls template; SBOM generation added to CI |
| D9 | 6 | 7 | +1 | OperationMetrics + OperationTimer + correlation IDs wired into all CLI commands |
| D10 | 7 | 8 | +1 | Aggregator job added; SBOM job added; bandit artifact upload |
| D11 | 6 | 7 | +1 | CODEBASE_MAP.md created; CONTRIBUTING.md expanded; Issue/PR templates added; README exit codes complete |
| D18 | 6 | 7 | +1 | SBOM generation (CycloneDX via Syft/Grype) added to CI pipeline |

### Archetype 9 Minimum Check

| Dimension | Required | Actual | Status |
|-----------|----------|--------|--------|
| D7 (Testing) | 7 | 8 | MET |
| D4 (API Surface) | 7 | 8 | MET |
| D8 (Security) | 6 | 8 | MET |
| D10 (CI/CD) | 6 | 8 | MET |
| D11 (Documentation) | 6 | 7 | MET |
| D12 (Domain Capability) | 6 | 7 | MET |
| Composite | 60 | 70 | MET |

**All minimums met.** Prior audit had D7 and D10 below minimum — both now resolved.

---

## Dimension Details

### Dim 1: Architecture Integrity — Score: 7/10

**Evidence:**
- Clean module structure: types.py (43 LOC), contract.py (237), io.py (172), cli.py (389), config.py (74), monitoring.py (158), observability.py (248)
- New control_plane/ package (3 files, 331 LOC) with proper optional import pattern (`try/except ImportError` + `_HAS_EXECUTION_CONTRACTS` flag)
- `py.typed` PEP 561 marker present
- TypedDict contracts (Contract, FieldContract), frozen dataclasses (Profile, ValidationIssue)
- Zero runtime dependencies — only stdlib
- `src/` layout with setuptools, entry point via `[project.scripts]`
- ContextVar for correlation IDs in observability.py

**Gaps:**
- Duplication between monitoring.py (ContractMetrics + HealthCheck) and observability.py (OperationMetrics + health_probe) — two parallel metrics systems
- config.py uses class-level env var parsing at import time — not injectable
- No plugin/extension architecture
- No CODEBASE_MAP.md (Phase 0.5 requirement)

**Cap condition:** 7 is fair — clean but not exemplary. Would need to resolve monitoring/observability duplication and add CODEBASE_MAP for 8.

---

### Dim 2: Auth & Identity — Score: 3/10

**Evidence:**
- CLI tool processes local files — no network auth needed
- File path validation (validate_path_for_read, validate_path_for_write) in io.py
- Dockerfile creates non-root user (`USER contracts`)
- control_plane/contracts.py defines PermissionScope, ApprovalPolicy, AuthorityBoundary

**Gaps:**
- No signed contract verification
- No file permission enforcement beyond existence checks

**Note:** Weight is 2%. For a CLI tool, minimal auth is expected. Score reflects control-plane types exist but aren't enforced at runtime.

---

### Dim 3: RLS / Multi-Tenancy — Score: 0/10

N/A for Archetype 9. Weight: 0%.

---

### Dim 4: API Surface Quality — Score: 8/10

**Evidence (improvements since prior):**
- `--version` flag added (cli.py:288-292)
- `--format` flag with `json` and `table` options (cli.py:337-344)
- `--metrics-out` flag for exporting validation/drift metrics (cli.py:332-336)
- `--log-format` flag with `text` and `json` options (cli.py:299-304)
- `--disallow-extra` flag on infer command (cli.py:311)
- `_format_table()` function for human-readable output (cli.py:116-153)
- control_plane/tool_specs.py maps CLI commands to ToolSpec contracts with JSON Schema input definitions
- 3 well-defined subcommands: infer, profile, check
- Distinct exit codes: 0 (success), 2 (CLI error), 3 (unexpected), 4 (check failed)
- Programmatic API: infer_contract(), validate_records(), profile_records(), drift_check()

**Gaps:**
- No stdin/stdout streaming/pipe support
- No shell completions
- Config class settings (DEFAULT_SAMPLE_SIZE, etc.) not wired to CLI behavior
- CLI --help text is minimal

**Cap condition:** 8 is appropriate. Would need streaming support and shell completions for 9.

---

### Dim 5: Data Layer — Score: 5/10

**Evidence:**
- JSONL reading with validation, line-level error reporting (io.py:67-114)
- JSON reading/writing with UTF-8 encoding (io.py:117-172)
- Path validation (io.py:12-64)
- Lazy JSONL via generator (`yield` in read_jsonl)
- Parent directory auto-creation on write (io.py:139)

**Gaps:**
- No schema versioning/migration strategy
- No contract registry or catalog
- No CSV/Parquet/other format support
- No atomic file writes (no temp file + rename)
- No caching or data sampling strategies beyond `--limit`

**Cap condition:** File-based only. CLI tool scope limits this dimension. Weight is 2%.

---

### Dim 6: Frontend Quality — Score: 0/10

N/A for Archetype 9. Weight: 0%.

---

### Dim 7: Testing & QA — Score: 8/10

**Evidence:**
- **221 tests**, all passing (up from 23 at prior audit)
- **89.44% branch coverage** (up from 64.48%)
- Coverage threshold enforced at **80%** in pyproject.toml (up from 60%)
- Per-module coverage:
  - cli.py: 86%
  - control_plane/config.py: 95%
  - io.py: 90%
  - monitoring.py: 92%
  - observability.py: 98%
  - config.py, types.py, contract.py, __init__.py, __main__.py: 100%
- 12 test files with organized test classes covering:
  - Config validation edge cases (test_config.py)
  - Monitoring/health checks (test_monitoring.py)
  - Observability: correlation IDs, structured logging, timers, metrics (test_observability.py)
  - Drift edge cases: zero std, missing fields, empty profiles (test_drift_edge_cases.py)
  - json_type() all branches including dict, list, fallback (test_drift_edge_cases.py)
  - Profile CLI end-to-end (test_profile_cli.py)
  - Schema validation boundaries (test_schema_validation_edge_cases.py)
  - CLI flags: --version, --format (test_sprint1_cli_flags.py)
  - CLI metrics + logging (test_cli_metrics_logging.py)
  - Control-plane adapter (test_control_plane.py)
  - IO and CLI error paths (test_enhancements.py)
- Integration tests exercise full infer -> profile -> check workflow
- tmp_path fixtures for test isolation

**Gaps:**
- control_plane/contracts.py at 25% coverage — the fallback inline definitions when `akiva_execution_contracts` is not installed are tested, but the framework-present path (lines 22-28) is not exercisable without installing the framework
- No property-based / fuzz testing
- No performance benchmarks

**Cap condition:** 8 is appropriate. 25% on contracts.py is a known limitation (optional dep path). Would need fuzz testing and benchmark suite for 9.

---

### Dim 8: Security Posture — Score: 8/10

**Evidence:**
- Zero runtime dependencies — minimal attack surface
- No eval(), exec(), subprocess, os.system, or shell=True anywhere in codebase
- No hardcoded secrets or credentials
- .env in .gitignore, .env.example contains only config knobs
- **SECURITY.md complete** — supported versions table, reporting instructions, 48h acknowledge timeline, 90-day coordinated disclosure, scope definition (in/out), security properties
- Dockerfile uses non-root user (`USER contracts`)
- Bandit security scan in CI — **blocking** (no continue-on-error), report uploaded as artifact
- Safety dependency check in CI — **blocking**
- **SBOM generation** — CycloneDX via Syft in CI, vulnerability scanning via Grype (fail-on critical), SBOM published as artifact
- Dependabot configured (.github/dependabot.yml) for pip + github-actions
- Pre-commit hooks configured (.pre-commit-config.yaml) with ruff + pyright
- Path validation prevents directory traversal (io.py resolves to absolute)
- Input validation on JSON/JSONL parsing with specific error types

**Gaps:**
- No file size limits on input (could OOM on huge files)
- No signed commits or artifact signing (recommended for Arch 9 per §10) — **HUMAN REQUIRED**

**Cap condition:** 8 is appropriate. Would need signed commits (human) and input size limits for 9.

---

### Dim 9: Observability — Score: 7/10

**Evidence:**
- **observability.py** (248 LOC) with StructuredJsonFormatter, correlation IDs (ContextVar), OperationTimer, OperationMetrics with snapshot/timing summaries, health_probe()
- **OperationMetrics wired into all CLI commands:**
  - `_cmd_infer`: record_infer + record_timing("infer")
  - `_cmd_profile`: record_profile + record_timing("profile")
  - `_cmd_check`: record_schema_check + record_timing("validate"), record_drift_check + record_timing("drift_check")
- **OperationTimer** wraps core operations in all 3 commands
- **Correlation IDs** generated per CLI invocation via new_correlation_id() in main()
- ContractMetrics (monitoring.py) also wired into check command for --metrics-out export
- `--log-format json` CLI flag for structured JSON logging
- `--metrics-out` for exporting metrics to JSON file
- `--verbose` flag for DEBUG level
- Logs to stderr (stdout reserved for output)

**Gaps:**
- Two metrics systems remain (ContractMetrics for --metrics-out export, OperationMetrics for internal tracking) — functional overlap but both wired
- No OpenTelemetry or distributed tracing
- No metrics export to external systems (Prometheus, StatsD)
- No log rotation configuration

**Cap condition:** 7 is appropriate. Would need OTel integration or external metrics export for 8.

---

### Dim 10: CI/CD — Score: 8/10

**Evidence:**
- GitHub Actions CI with **7 jobs:** test, security, lint, sbom, build, docker, all-checks (ci.yml)
- **publish.yml** — PyPI publishing via OIDC trusted publisher (pypa/gh-action-pypi-publish)
- Multi-Python matrix testing: 3.10, 3.11, 3.12 with `fail-fast` default
- Ruff linting + mypy type checking in CI
- Bandit + Safety security scanning — **blocking**, bandit report uploaded as artifact
- **SBOM generation** — CycloneDX via Syft, vulnerability scanning via Grype (fail-on critical), SBOM published as artifact
- **Aggregator job** (`all-checks`) depends on all 6 other jobs, fails if any fail or cancel — suitable for branch protection
- Package build + twine check
- Docker image build with buildx and GHA cache
- Coverage upload to Codecov
- Dependabot for pip + github-actions dependencies
- Pre-commit config with ruff + pyright
- Build job depends on [test, security, lint] — proper ordering

**Gaps:**
- Branch protection not yet configured on GitHub — **HUMAN REQUIRED**
- No release automation — version 0.1.0 hardcoded in pyproject.toml and __init__.py
- Docker image not published to any registry
- No artifact signing

**Cap condition:** 8 is appropriate. Would need release automation and branch protection (human) for 9.

---

### Dim 11: Documentation — Score: 7/10

**Evidence:**
- README.md: proper GitHub URLs, installation, usage, CLI commands, **complete exit codes table** (0, 2, 3, 4)
- QUICKSTART.md: step-by-step workflow with examples
- DEPLOYMENT.md: Docker + local install + CI/CD integration + troubleshooting
- **CONTRIBUTING.md expanded** — dev environment setup, how to run tests, code style/linting requirements, PR process with checklist, core principles, issue reporting guidance
- **SECURITY.md expanded** — supported versions table, reporting instructions, 48h acknowledge timeline, 90-day coordinated disclosure, scope (in/out), security properties
- **CODEBASE_MAP.md created** — directory structure, data flow diagram, key types table, CLI commands, dependencies, known tech debt
- **Issue/PR templates added** — .github/ISSUE_TEMPLATE/bug_report.md, feature_request.md, PULL_REQUEST_TEMPLATE.md
- CHANGELOG.md with 0.1.0 entry following Keep a Changelog format
- examples/ml_pipeline_example.py: working end-to-end example
- Docstrings on all public functions in contract.py and io.py
- Type annotations throughout codebase
- py.typed PEP 561 marker

**Gaps:**
- No API reference documentation (auto-generated)
- No architecture diagram (data flow in CODEBASE_MAP serves partially)
- No man page or shell completions
- Doc build validation not in CI — per Repository Controls v1.3 §4, Dim 11 capped at 7

**Cap condition:** Capped at 7 without doc build validation in CI. Would need auto-generated API docs and doc validation for 8.

---

### Dim 12: Domain Capability — Score: 7/10

**Evidence:**
- Contract inference from JSONL samples — working, 10+ tests (test_schema_validation_edge_cases.py: TestInferContractEdgeCases)
- Schema validation: type checking, required fields, extra fields enforcement — working, 8+ tests (TestValidateRecordsEdgeCases)
- Drift detection: missing rate and mean shift detection with configurable thresholds — working, 12+ tests (test_drift_edge_cases.py)
- Statistical profiling: mean, std, min, max, missing rate, type distribution — working, tested
- Multiple output formats: JSON and human-readable table — working
- CI integration via exit codes (0, 2, 3, 4) — working
- Full workflow: infer -> profile -> check — integration tested

**Gaps:**
- Limited drift metrics: only missing rate + mean shift sigma. No distribution divergence (KS test, chi-squared), no categorical drift, no feature importance
- Config settings (DEFAULT_SAMPLE_SIZE, DEFAULT_DRIFT_THRESHOLD, etc.) exist but are not wired to CLI or core logic
- No contract versioning or evolution tracking
- No multi-contract management or registry
- No streaming support for large datasets

**Cap condition:** 7 reflects correct, tested core logic covering stated purpose. Would need advanced statistical tests (KS, chi-squared) and contract versioning for 8.

---

### Dim 13: AI/ML Capability — Score: 4/10

**Evidence:**
- Tool is ML-adjacent: validates ML pipeline inputs before they reach models
- Statistical profiling computes mean/std/min/max per field (contract.py:127-176)
- Drift detection with configurable sigma thresholds (contract.py:179-237)
- Configurable missing rate thresholds

**Gaps:**
- No actual ML model usage
- No distribution divergence tests (KS, chi-squared, Jensen-Shannon)
- No advanced statistical tests (despite ENABLE_STATISTICAL_TESTS config existing)
- No embedding drift detection
- No feature importance or correlation tracking
- No integration with ML frameworks

**Cap condition:** 4 reflects basic statistical analysis without ML capability. Weight is 5%.

---

### Dim 14: Connectivity — Score: 3/10

**Evidence:**
- Pure CLI tool — file-based I/O only
- No network connectivity needed or implemented
- No API server mode

**Gaps:**
- No HTTP client for remote data sources
- No webhook integration
- No S3/GCS/cloud storage support

**Cap condition:** 3 is fair for a local-only CLI tool. Weight is 2%.

---

### Dims 15-17: Agentic UI/UX, UX Quality, User Journey — Score: 0/10 each

N/A for Archetype 9. Weight: 0% each.

---

### Dim 18: Zero Trust / Dependency Management — Score: 7/10

**Evidence:**
- Zero runtime dependencies — only Python stdlib
- Dev dependencies cleanly separated in [project.optional-dependencies]
- Dependabot configured for pip + github-actions (weekly)
- CI tests across 3.10, 3.11, 3.12
- pyproject.toml is single source of truth
- Pre-commit hooks configured
- **SBOM generation** — CycloneDX via Syft in CI, vulnerability scanning via Grype (fail-on critical)
- Safety dependency check in CI (blocking)

**Gaps:**
- No lock file for dev dependencies (no poetry.lock, Pipfile.lock, or requirements.txt with pinned versions)
- No license compliance checks in CI — per Repository Controls v1.3 §5.4

**Prior was 8:** Reassessed under v2.14 with stricter supply chain requirements. Now 7 with SBOM added.

**Cap condition:** 7 is appropriate. Would need lock file and license compliance for 8.

---

### Dim 19: Enterprise Security — Score: 7/10

**Evidence:**
- Ruff configured with E, F, I, B, UP rules (pyproject.toml)
- Pyright configured (basic mode) with pyrightconfig.json
- mypy in CI (--ignore-missing-imports)
- py.typed PEP 561 marker
- Consistent code style: `from __future__ import annotations`, sorted imports
- TypedDict and frozen dataclass usage for structured data
- Line length: 100 chars
- Clean module separation
- Pre-commit hooks (ruff + pyright)

**Gaps:**
- Pyright in "basic" mode — strict would catch more
- mypy uses --ignore-missing-imports (weakens type checking)
- No SBOM or signed releases
- No container image scanning

**Cap condition:** 7 is appropriate. Would need strict type checking and SBOM for 8.

---

### Dim 20: Operational Readiness — Score: 6/10

**Evidence:**
- Dockerfile with non-root user, HEALTHCHECK, labels
- Docker Compose with service profiles
- pip install -e . editable install supported
- Package builds via python -m build
- pyproject.toml fully configured for distribution
- PyPI publish workflow (publish.yml) via OIDC

**Gaps:**
- Docker image not published to any registry
- No multi-arch Docker build
- No Helm chart / K8s manifests
- No binary distribution (pyinstaller)
- Version 0.1.0 hardcoded in two places (pyproject.toml + __init__.py)

**Cap condition:** 6 reflects deployment infrastructure exists but not yet operationalized. Weight is 2%.

---

### Dim 21: Agentic Workspace — Score: 4/10

**Evidence (improvement from 1):**
- **New control_plane/ package** (331 LOC, 3 files):
  - contracts.py: PermissionScope, ApprovalPolicy, AuthorityBoundary, ToolSpec with optional import from akiva_execution_contracts
  - config.py: ToolkitConfigContract dataclass with 3-tier config hierarchy (platform -> toolkit -> CLI)
  - tool_specs.py: TOOLKIT_TOOL_SPECS mapping all 3 CLI commands to ToolSpec contracts with JSON Schema input definitions
- Authority boundaries: all commands are READ_ONLY + AUTO approval
- Input schemas defined for each command (infer, profile, check)
- Proper try/except ImportError pattern for optional framework dependency

**Gaps:**
- No MCP server or tool definitions
- control_plane adapter defines specs but is not wired into CLI execution path
- No agent runtime integration (specs only, no runtime)
- No LLM hooks or callbacks

**Cap condition:** 4 reflects structural preparation for agent integration but no runtime wiring. Weight is 2%.

---

## Cross-Standard Findings

### Repository Controls v1.3 Compliance

| Control | Status | Impact |
|---------|--------|--------|
| SECURITY.md | Complete (versions, timeline, disclosure, scope) | OK |
| CONTRIBUTING.md | Complete (dev setup, tests, style, PR process, issue reporting) | OK |
| Issue/PR templates | Present (bug_report, feature_request, PR template) | OK |
| CI matrix testing | Present (3.10, 3.11, 3.12) | OK |
| Coverage publishing | Present (Codecov) | OK |
| Branch protection | Not configured on GitHub — **HUMAN REQUIRED** | D10 cap at 9 |
| Dependabot | Configured (pip + github-actions) | OK |
| Doc build validation | Not in CI | D11 capped at 7 |
| SBOM generation | Present (CycloneDX via Syft, Grype scan, artifact published) | OK |
| Aggregator job | Present (`all-checks` depends on all 6 jobs) | OK |

### AI Agent Runtime Standard v1.8

- control_plane/contracts.py: ToolSpec and AuthorityBoundary types implemented with fallback pattern
- control_plane/tool_specs.py: All CLI commands mapped to ToolSpec contracts
- control_plane/config.py: 3-tier config hierarchy matches platform pattern
- **Not wired to CLI execution** — adapter layer only

### Application Composition Standard v1.4

- Config hierarchy follows platform pattern (Level 0 platform, Level 1 toolkit, Level 2 CLI)
- control_plane/ package structure matches other toolkit adapters

---

## Gap Summary (Post-Remediation)

### Resolved This Session

| ID | Dim | Gap | Resolution |
|----|-----|-----|------------|
| G1 | 11 | No CODEBASE_MAP.md | Created docs/CODEBASE_MAP.md |
| G2 | 8 | SECURITY.md incomplete | Expanded with full Repo Controls template |
| G3 | 11 | CONTRIBUTING.md minimal | Expanded with dev setup, tests, style, PR process |
| G4 | 8/18 | No SBOM generation | Added CycloneDX (Syft) + Grype vulnerability scanning to CI |
| G5 | 9 | OperationMetrics not wired to CLI | Wired into all 3 commands with OperationTimer |
| G6 | 9 | No correlation IDs in CLI | new_correlation_id() called per invocation |
| G7 | 10 | No aggregator job | Added `all-checks` job depending on all 6 other jobs |
| G8 | 11 | No Issue/PR templates | Added bug_report.md, feature_request.md, PULL_REQUEST_TEMPLATE.md |
| G10 | 12 | Dead config settings | Documented as programmatic API config; CLI flags take precedence |
| G11 | 11 | README exit codes incomplete | Expanded to full table (0, 2, 3, 4) |

### Remaining Gaps (Agent-Fixable)

| ID | Dim | Gap | Current | Target | Priority |
|----|-----|-----|---------|--------|----------|
| G9 | 10 | No release automation (version hardcoded in 2 places) | 8 | 9 | P2 |
| G12 | 13 | No advanced statistical tests (KS, chi-squared) | 4 | 6 | P2 |
| G13 | 4 | No stdin/stdout streaming support | 8 | 9 | P2 |
| G14 | 7 | control_plane/contracts.py at 25% coverage | 8 | 9 | P2 |
| G15 | 19 | Pyright basic mode, mypy --ignore-missing-imports | 7 | 8 | P2 |
| G16 | 1 | monitoring.py / observability.py partial duplication | 7 | 8 | P2 |

### Remaining Gaps (HUMAN REQUIRED)

| ID | Dim | Gap | Action Required |
|----|-----|-----|-----------------|
| H1 | 10 | Branch protection not configured on GitHub | Admin: enable required status checks on `main`, require `all-checks` to pass |
| H2 | 8 | No signed commits | Developer: configure GPG/SSH key for commit signing |
| H3 | 20 | PyPI trusted publisher not configured | Admin: configure OIDC on PyPI for `toolkit-data-contracts-drift` |
| H4 | 20 | Docker image not published to registry | Admin: choose registry (GHCR/DockerHub), add push credentials |
| H5 | 8 | No artifact signing | Admin: set up organization signing key for releases |

---

## Path to 75/100

Current score: **70/100**. To reach 75, the highest-impact agent-fixable gaps:

| Action | Dims Affected | Expected Lift |
|--------|---------------|---------------|
| Advanced statistical tests (KS, chi-squared, categorical drift) | D13: 4->6 | +1.0 (5% weight) |
| Release automation (version bumping, tag-based workflow) | D10: 8->9 | +1.0 (10% weight) |
| Consolidate monitoring.py into observability.py | D1: 7->8 | +0.8 (8% weight) |
| Pyright strict mode + mypy strict | D19: 7->8 | +0.5 (5% weight) |
| Lock file for dev dependencies + license compliance | D18: 7->8 | +0.2 (2% weight) |

**Projected composite after remaining agent work:** ~73-74/100

**To reach 75+ requires human actions:**
- Branch protection on GitHub (H1) — enables D10: 9
- Signed commits (H2) — enables D8: 9

**Projected composite with human + agent:** ~76/100

---

## Human-Only Blockers

| Item | Why Human |
|------|-----------|
| Branch protection rules on GitHub | Requires admin access to repo settings |
| PyPI trusted publisher configuration | Requires PyPI account setup |
| Container registry access | Requires registry credentials |
| Signed commits (GPG/SSH) | Requires developer key setup |
| Production deployment | Requires infrastructure decisions |

---

## Accepted Exceptions

| Item | Reason |
|------|--------|
| D3 (Multi-Tenancy) = 0 | N/A for CLI tool, weight = 0% |
| D6 (Frontend Quality) = 0 | N/A for CLI tool, weight = 0% |
| D15 (Agentic UI/UX) = 0 | N/A for CLI tool, weight = 0% |
| D16 (UX Quality) = 0 | N/A for CLI tool, weight = 0% |
| D17 (User Journey) = 0 | N/A for CLI tool, weight = 0% |
| D2 (Auth) = 3 | Local CLI tool, no network auth needed, weight = 2% |
| D14 (Connectivity) = 3 | File-only tool, no network needed, weight = 2% |

---

## Coverage Tracker

| Dimension | Last Audited | Score |
|-----------|-------------|-------|
| D1 Architecture | 2026-04-04 | 7 |
| D2 Auth | 2026-04-04 | 3 |
| D3 Multi-Tenancy | 2026-04-04 | N/A |
| D4 API Surface | 2026-04-04 | 8 |
| D5 Data Layer | 2026-04-04 | 5 |
| D6 Frontend | 2026-04-04 | N/A |
| D7 Testing | 2026-04-04 | 8 |
| D8 Security | 2026-04-04 | 8 |
| D9 Observability | 2026-04-04 | 7 |
| D10 CI/CD | 2026-04-04 | 8 |
| D11 Documentation | 2026-04-04 | 7 |
| D12 Domain Capability | 2026-04-04 | 7 |
| D13 AI/ML | 2026-04-04 | 4 |
| D14 Connectivity | 2026-04-04 | 3 |
| D15-17 UI/UX | 2026-04-04 | N/A |
| D18 Zero Trust | 2026-04-04 | 7 |
| D19 Enterprise Security | 2026-04-04 | 7 |
| D20 Operational Readiness | 2026-04-04 | 6 |
| D21 Agentic Workspace | 2026-04-04 | 4 |

---

_Audit conducted under Akiva Build Standard v2.14, Archetypes v2.0, Repository Controls v1.3._
_All scores evidence-backed from source code, test execution, and CI configuration._
