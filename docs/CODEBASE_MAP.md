# Codebase Map — toolkit-data-contracts

**System:** toolkit-data-contracts (TK-05)
**Archetype:** 9 — Developer Tool / CLI Utility
**Last Updated:** 2026-04-04

---

## Directory Structure

```
toolkit-data-contracts/
├── src/toolkit_data_contracts_drift/     # Main package
│   ├── __init__.py                       # Package version (__version__ = "0.1.0")
│   ├── __main__.py                       # python -m entry point
│   ├── cli.py                            # CLI entry point (argparse, 3 subcommands)
│   ├── config.py                         # Env-var-based Config class (import-time validation)
│   ├── contract.py                       # Core domain: infer, validate, profile, drift_check
│   ├── io.py                             # JSONL/JSON file I/O with path validation
│   ├── monitoring.py                     # ContractMetrics + HealthCheck (wired to CLI)
│   ├── observability.py                  # OperationMetrics, OperationTimer, StructuredJsonFormatter, correlation IDs
│   ├── types.py                          # TypedDict contracts, ValidationIssue, json_type()
│   ├── py.typed                          # PEP 561 marker
│   └── control_plane/                    # Control-plane adapter (Agent Runtime Standard)
│       ├── __init__.py                   # Re-exports
│       ├── config.py                     # ToolkitConfigContract, 3-tier config hierarchy
│       ├── contracts.py                  # ToolSpec, AuthorityBoundary, PermissionScope (optional framework import)
│       └── tool_specs.py                 # CLI command -> ToolSpec mapping (infer, profile, check)
├── tests/                                # 221 tests, 89% branch coverage
│   ├── conftest.py                       # sys.path setup
│   ├── test_cli_metrics_logging.py       # CLI metrics wiring + --metrics-out + --log-format
│   ├── test_config.py                    # Config.validate, get_config_dict, env var parsing
│   ├── test_contracts.py                 # Integration: infer -> profile -> check workflow
│   ├── test_control_plane.py             # Control-plane adapter: contracts, config, tool_specs
│   ├── test_drift_edge_cases.py          # drift_check: zero std, missing fields, empty profiles, json_type branches
│   ├── test_enhancements.py              # IO + CLI error paths, path validation, lazy JSONL
│   ├── test_monitoring.py                # HealthCheck, ContractMetrics, get_health_status
│   ├── test_observability.py             # StructuredJsonFormatter, correlation IDs, OperationTimer, OperationMetrics
│   ├── test_profile_cli.py              # profile CLI subcommand end-to-end
│   ├── test_schema_validation_edge_cases.py  # Inference, validation, Profile serialization, CLI error paths
│   └── test_sprint1_cli_flags.py         # --version, --format flags
├── .github/
│   ├── dependabot.yml                    # Dependabot for pip + github-actions (weekly)
│   └── workflows/
│       ├── ci.yml                        # CI: test (3.10-3.12), security, lint, build, docker
│       └── publish.yml                   # PyPI publishing via OIDC trusted publisher
├── docs/
│   ├── CODEBASE_MAP.md                   # This file
│   └── audits/                           # Audit reports
├── examples/
│   └── ml_pipeline_example.py            # End-to-end usage example
├── pyproject.toml                        # Package config, deps, tool config
├── pyrightconfig.json                    # Pyright type-check config
├── .pre-commit-config.yaml               # Ruff + pyright pre-commit hooks
├── Dockerfile                            # Python 3.11-slim, non-root user, healthcheck
├── docker-compose.yml                    # Local dev with service profiles
├── CLAUDE.md                             # Build agent instructions
├── README.md                             # Usage, installation, CLI reference
├── QUICKSTART.md                         # Step-by-step getting started
├── DEPLOYMENT.md                         # Docker, local, CI/CD deployment
├── CONTRIBUTING.md                       # Contribution guidelines
├── SECURITY.md                           # Security policy
├── CHANGELOG.md                          # Version history (Keep a Changelog)
└── LICENSE                               # MIT
```

## Data Flow

```
JSONL records (file)
       │
       ▼
   read_jsonl()          ← io.py: validates path, lazy generator, line-level errors
       │
       ├──→ infer_contract()    ← contract.py: scans all records, infers field types + required
       │         │
       │         ▼
       │    Contract (TypedDict)  → write_json() → contract.json
       │
       ├──→ validate_records()   ← contract.py: checks types, required, extra fields
       │         │
       │         ▼
       │    list[ValidationIssue]
       │
       ├──→ profile_records()    ← contract.py: computes per-field stats (mean, std, missing rate)
       │         │
       │         ▼
       │    Profile (dataclass)   → write_json() → baseline.profile.json
       │
       └──→ drift_check()        ← contract.py: compares current vs baseline profiles
                 │
                 ▼
           list[ValidationIssue]  → JSON/table report → exit code 0 or 4
```

## Key Types

| Type | Module | Kind | Purpose |
|------|--------|------|---------|
| `Contract` | types.py | TypedDict | Schema: version, allow_extra_fields, fields |
| `FieldContract` | types.py | TypedDict | Per-field: types[], required |
| `ValidationIssue` | types.py | frozen dataclass | Issue: kind, field, message, count |
| `Profile` | contract.py | frozen dataclass | Per-field stats: missing_rate, type_counts, numeric |
| `ContractMetrics` | monitoring.py | class | Validation/drift counters (wired to CLI) |
| `OperationMetrics` | observability.py | dataclass | Timing + count accumulator (not yet wired to CLI) |
| `ToolkitConfigContract` | control_plane/config.py | dataclass | Resolved 3-tier config |
| `ToolkitCommandSpec` | control_plane/tool_specs.py | dataclass | CLI command -> ToolSpec + AuthorityBoundary |

## CLI Commands

| Command | Entry | Description | Exit Codes |
|---------|-------|-------------|------------|
| `toolkit-contracts infer` | cli.py:_cmd_infer | Infer contract from JSONL | 0, 2, 3 |
| `toolkit-contracts profile` | cli.py:_cmd_profile | Compute baseline profile | 0, 2, 3 |
| `toolkit-contracts check` | cli.py:_cmd_check | Validate + drift check | 0, 2, 3, 4 |

## Dependencies

- **Runtime:** None (stdlib only)
- **Dev:** pytest, pytest-cov, ruff, pyright
- **Optional:** akiva_execution_contracts, akiva_policy_runtime (control-plane; graceful fallback)

## Known Technical Debt

1. Dual metrics systems: monitoring.py (ContractMetrics) vs observability.py (OperationMetrics) — need consolidation
2. config.py env-var parsing at import time — not injectable/testable cleanly
3. control_plane adapter defines specs but is not wired into CLI execution path
