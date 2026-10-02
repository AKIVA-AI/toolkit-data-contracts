# Codebase map: toolkit-data-contracts

## Directory structure

```text
toolkit-data-contracts/
├── src/toolkit_data_contracts_drift/
│   ├── __init__.py        # __version__
│   ├── __main__.py        # python -m entry point
│   ├── cli.py             # argparse CLI: infer, profile, check; exit codes
│   ├── contract.py        # v1->v2 loading, streaming inference/validation/profiling, drift, PSI
│   ├── schema.py          # stdlib JSON Schema (2020-12 subset) validator
│   ├── odcs.py            # ODCS v3 import/export (PyYAML optional)
│   ├── diff.py            # contract diff: tightens / loosens / both / annotation
│   ├── text.py            # tokenizers, language detection, length bins, centroid distances
│   ├── presets.py         # LLM presets: schemas + record checks (tool args, pairs, chunks)
│   ├── readers.py         # JSONL / Parquet / CSV record streams (pyarrow optional)
│   ├── io.py              # strict JSON/JSONL readers, write_json, path checks
│   ├── monitoring.py      # ContractMetrics (check --metrics-out)
│   ├── report.py          # report envelope v1 (in-toto Statement), canonical JSON
│   ├── types.py           # Contract / FieldContract TypedDicts, ValidationIssue, json_type
│   └── py.typed
├── tests/                 # pytest suite; fixtures: official JSON-Schema-Test-Suite subset, ODCS schemas + examples
├── schemas/report-envelope.v1.json, docs/report-envelope.md  # shared report format
├── examples/               # ml_pipeline_example.py, data/ (UltraChat sample)
├── action.yml             # composite GitHub Action running `diff` on pull requests
├── .github/               # CI, release workflow (v* tag: GitHub Release; PyPI upload when PUBLISH_TO_PYPI is true), Dependabot, issue/PR templates
├── Dockerfile, docker-compose.yml
└── README.md, QUICKSTART.md, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md
```

## Data flow

```text
JSONL file (streamed, strict JSON: rejects NaN/Infinity)
   │
   ├─► SchemaInferrer.add()  → contract.json  {"version": 2, "schema": JSON Schema}
   │
   ├─► RecordValidator.add() → issues per (kind, path, message), counted
   │        uses schema.Validator (JSON Schema subset; unsupported keywords raise SchemaError)
   │
   └─► Profiler.add()        → profile.json (per declared path: missing rate vs parent,
                                type counts, numeric stats, categorical counts)
            │
            ▼
       drift_check(baseline, current) → drift issues per path
            │
            ▼
       report envelope v1 (JSON) or table/markdown, exit code 0 / 4 (2 = error)
```

Paths: `field`, `parent.child`, `array[]`, `array[].key`; `$` is the record.

## Key types

| Type | Module | Purpose |
|------|--------|---------|
| `Validator`, `SchemaError` | schema.py | JSON Schema validation, schema checking |
| `SchemaInferrer`, `RecordValidator`, `Profiler` | contract.py | streaming infer / validate / profile |
| `Profile` | contract.py | per-path stats; `to_json` / `from_json` (v1 and v2) |
| `ValidationIssue` | types.py | `kind`, `field` (path), `message`, `count` |
| `ContractMetrics` | monitoring.py | pass/fail counters for `--metrics-out` |

## Issue kinds

| Kind | Source |
|------|--------|
| `missing_required`, `type_mismatch`, `unexpected_field`, `enum_mismatch`, `const_mismatch`, `range_violation`, `length_violation`, `pattern_mismatch`, `unique_violation`, `contains_violation`, `unexpected_item`, `invalid_property_name`, `combinator_mismatch`, `false_schema` | `schema.Validator` via `validate_records` |
| `unknown_tool`, `tool_args_*`, `orphan_tool_result`, `preference_identical`, `preference_type_mismatch`, `duplicate_id`, `embedding_dimension_mismatch`, `offset_order` | `presets.RecordChecks` via `RecordValidator(checks=...)` |
| `drift_missing_rate`, `drift_null_rate`, `drift_mean_shift`, `drift_categorical`, `drift_text_length`, `drift_token_count`, `drift_language`, `drift_embedding_centroid` | `drift_check` |

## Known limits

- The mean-shift check is a heuristic, not a statistical test.
- Keys the contract does not declare are not profiled.
- Unsupported JSON Schema keywords: `unevaluated*`, `$dynamicRef`, `$anchor`,
  remote refs, `$id` in subschemas.
