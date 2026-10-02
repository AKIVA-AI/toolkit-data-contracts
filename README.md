# toolkit-data-contracts

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Contracts for LLM-shaped data.** A small, dependency-free Python CLI that
checks chat transcripts, tool-call arguments, SFT and preference (DPO) rows
and RAG chunk records against a JSON Schema contract, and flags drift at every
nested path. Contracts interoperate with the
[Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/)
(ODCS). It is meant as a cheap CI gate in front of training, evaluation or
retrieval data.

```bash
toolkit-contracts check --input train.jsonl --preset openai-chat --tools tools.json
```

It reads JSONL (and, with the `parquet` extra, Parquet or CSV) in one
streaming pass. If you need warehouse connectors or a full suite of statistical drift tests, look at larger projects such as
[datacontract-cli](https://github.com/datacontract/datacontract-cli) or
[Evidently](https://github.com/evidentlyai/evidently).

## Status

| Capability | Status | Notes |
|---|---|---|
| Contract format | Working | `{"version": 2, "schema": <JSON Schema>}`. A bare JSON Schema file and version 1 contracts (`fields`/`types`/`required`) are also accepted. See [Contracts](#contracts). |
| JSON Schema validation | Working | Draft 2020-12 subset: `type`, `enum`, `const`, numeric ranges and `multipleOf`, string lengths and `pattern`, `items`/`prefixItems`/`contains`, array sizes and `uniqueItems`, `properties`/`required`/`additionalProperties`/`patternProperties`/`propertyNames`, `dependentRequired`/`dependentSchemas`, `allOf`/`anyOf`/`oneOf`/`not`/`if`-`then`-`else`, same-document `$ref`. Checked against the official JSON-Schema-Test-Suite. Unsupported keywords make `check` fail with exit 2 instead of passing. |
| Contract inference (`infer`) | Working | Nested objects (`properties`, `required`), arrays (`items`, merged over all elements), nullability (`null` in `type`), optional `enum` for low-cardinality strings (`--enum-max N`). |
| Validation (`check`) | Working | Issues are counted per kind and path (`meta.source`, `messages[].role`). Integer and number are one JSON numeric type unless `--strict-integer` is set. |
| Baseline profile (`profile`) | Working | Per declared path, including nested keys and array items: missing rate (relative to the parent object), JSON type counts, numeric mean/std/min/max, and value counts for string/boolean values with up to 50 distinct values. |
| Drift: missing rate | Working | Flags a path whose missing rate is above `--max-missing` (default 0.01) and higher than the baseline's. |
| Drift: null rate | Working | Flags a rise of more than `--max-null-increase` (default 0.10, absolute) in the share of present values that are null. |
| Drift: categorical distribution | Working | Population Stability Index (PSI) on string/boolean value counts, threshold `--max-psi` (default 0.25). Paths with more than 50 distinct baseline values are skipped as high-cardinality. |
| Drift: text length and token count | Working | Every string path: character and token counts in power-of-two bins (0, 1, 2-3, 4-7, ...), compared with PSI (`--max-length-psi`, default 0.25). Tokens are whitespace-split by default or counted with `profile --tokenizer tiktoken:<encoding>` (extra `tiktoken`). |
| Drift: language distribution | Working (opt-in) | `profile --language PATH` detects each text's language with `langdetect` (extra `lang`; texts under 20 non-space characters count as `und`); PSI against `--max-psi`. |
| Drift: embedding centroid | Working (opt-in) | `profile --embedding PATH` stores the mean vector of that path; `check` flags a Euclidean (or `--centroid-metric cosine`) distance above `--max-centroid-distance` (default 0.2) or a dimension change. Pure Python; tune the threshold for your embedding model. |
| Drift: numeric mean | Partial | Flags `abs(mean - baseline_mean) / baseline_std > --max-mean-shift-sigma` (default 3.0). This is a heuristic, not a statistical test: it ignores batch size and distribution shape. |
| Drift on nested keys and array items | Working | Every path the contract declares is profiled and drift-checked. |
| Drift on keys the contract does not declare | Planned | Undeclared keys are not profiled. Set `additionalProperties: false` (`infer --disallow-extra`) to reject them in validation. |
| Statistical tests (KS, chi-squared) | Planned | Not implemented. |
| Large files / streaming | Working | `infer`, `profile` and `check` read the input once, in constant memory apart from the schema, the profile and at most 51 category counts per path (the `rag-chunks` duplicate-id check keeps the ids). |
| Parquet / CSV input | Working | `--input-format` `auto` (by file extension), `jsonl`, `parquet` or `csv`; needs the `parquet` extra (pyarrow). Rows are read batch by batch; dates become ISO 8601 strings, decimals numbers, binary base64. |
| Contract diff / compatibility (`diff`) | Working | Classifies each change as tightening, loosening, both or annotation, and as breaking under `--mode backward` (default), `forward` or `full`. Changes inside `anyOf`/`oneOf`/`not`/`if` are reported as "not analysed" (both directions). GitHub Action included. See [Reviewing contract changes](#reviewing-contract-changes). |
| LLM presets | Working | `openai-chat`, `anthropic-messages`, `tool-calls`, `sft`, `dpo`, `rag-chunks`. Tool-call arguments are validated against each tool's JSON Schema. See [LLM presets](#llm-presets). |
| ODCS v3 import / export | Working | `odcs export` writes ODCS v3.1.0 (validated against the official ODCS JSON Schema in tests); `odcs import` reads ODCS v3.0-v3.2 including v3.2 `enum`, `map` and `vector`. See [ODCS](#odcs-open-data-contract-standard). |
| Report envelope v1 (`check` and `diff` JSON output) | Working | in-toto Statement v1, canonical JSON, input digests; see [Report format](#report-format). |
| PyPI package | Planned | Not published yet; install from source. The release workflow is ready and waits on the one-time PyPI setup in [RELEASING.md](RELEASING.md). |

## Install

Requires Python 3.10+. The core has no runtime dependencies. Optional extras:
`odcs` (PyYAML, for ODCS YAML files), `tiktoken` (tiktoken token counts),
`lang` (langdetect, for language drift), `parquet` (pyarrow, for Parquet and CSV input).

```bash
git clone https://github.com/AKIVA-AI/toolkit-data-contracts.git
cd toolkit-data-contracts
pip install .            # or ".[odcs,tiktoken,lang,parquet]"; pip install -e ".[dev]" for development
toolkit-contracts --help
```

## Five-minute example

`examples/data/ultrachat_200k_test_sft_40.jsonl` holds 40 chat rows from the
public [UltraChat 200k](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k)
dataset (MIT license; see `examples/data/README.md`). From the repository root:

```bash
# 1. Does the file have the shape trainers expect for SFT?
toolkit-contracts check --input examples/data/ultrachat_200k_test_sft_40.jsonl --preset sft --format table
```

```text
Status: PASS

Validation: OK (no issues)

Drift: OK (no issues)
```

```bash
# 2. Freeze its shape as a contract (roles become an enum) and profile it as the baseline
toolkit-contracts infer --input examples/data/ultrachat_200k_test_sft_40.jsonl \
  --out chat.contract.json --enum-max 3
toolkit-contracts profile --input examples/data/ultrachat_200k_test_sft_40.jsonl \
  --contract chat.contract.json --out baseline.profile.json

# 3. Make a bad batch: assistant answers cut to 20 characters, a system turn added
python - <<'EOF'
import json
with open("examples/data/ultrachat_200k_test_sft_40.jsonl", encoding="utf-8") as src, \
        open("bad.jsonl", "w", encoding="utf-8") as out:
    for line in src:
        row = json.loads(line)
        for m in row["messages"]:
            if m["role"] == "assistant":
                m["content"] = m["content"][:20]
        row["messages"].insert(0, {"role": "system", "content": "You are terse."})
        out.write(json.dumps(row) + "\n")
EOF

# 4. Gate it (exit code 4)
toolkit-contracts check --input bad.jsonl --contract chat.contract.json \
  --baseline baseline.profile.json --format table
```

```text
Status: FAIL

Validation Issues:
  Kind                      Field                 Count  Message
  ------------------------- -------------------- ------  ------------------------------
  enum_mismatch             messages[].role          40  enum

Drift Issues:
  Kind                      Field                 Count  Message
  ------------------------- -------------------- ------  ------------------------------
  drift_text_length         messages[].content        1  psi=5.707 exceeds 0.250 (mean 902.6 -> 154.5)
  drift_token_count         messages[].content        1  psi=5.642 exceeds 0.250 (mean 144.3 -> 25.4)
  drift_categorical         messages[].role           1  psi=0.941 exceeds 0.250
```

```bash
# 5. Share the contract as an Open Data Contract Standard document (needs the odcs extra)
toolkit-contracts odcs export --contract chat.contract.json --out chat.odcs.yaml --name ultrachat_sft
```

`tests/test_readme_walkthrough.py` runs these steps in CI.

## Usage

```bash
# 1. Infer a contract from known-good records (reads the whole file; --limit N to cap)
toolkit-contracts infer --input samples.jsonl --out contract.json

# 2. Profile known-good records as the drift baseline
toolkit-contracts profile --input baseline.jsonl --contract contract.json --out baseline.profile.json

# 3. Validate a new batch, and drift-check it against the baseline
toolkit-contracts check --input new_batch.jsonl --contract contract.json \
  --baseline baseline.profile.json
```

`check` prints a JSON report, or writes it with `--out FILE`. Other formats:
`--format table` and `--format markdown` (for a PR comment) are for people;
`--format json-legacy` prints the pre-1.0 `{ok, validation_issues, drift_issues}`
object and will be removed in the next minor version.

### Report format

The JSON report is the shared toolkit **report envelope v1**: an
[in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
in canonical JSON (sorted keys, no extra whitespace, trailing newline), so its
SHA-256 is stable and it can be signed. See [docs/report-envelope.md](docs/report-envelope.md)
and the JSON Schema [schemas/report-envelope.v1.json](schemas/report-envelope.v1.json).

- `subject`: the checked batch file, with its SHA-256.
- `predicate.kind`: `data.check`.
- `predicate.inputs`: the contract (or `preset:NAME`), baseline profile and `--tools` files, with their SHA-256.
- `predicate.verdict` / `exit_code`: `pass`/0, `fail`/4, or `error`/2 (the
  input was readable but could not be judged, for example a malformed line).
  If the input file itself cannot be read, no report is written.
- `predicate.summary` (what a CI gate reads):

  | Key | Meaning |
  |---|---|
  | `ok` | `true` only when there are no validation or drift issues |
  | `records` | records read from the batch |
  | `validation_issues` | distinct (kind, field, message) validation issues |
  | `invalid_occurrences` | total occurrences across those issues |
  | `drift_checked` | whether `--baseline` was given |
  | `drift_issues` | number of drift issues |
  | `invalid_records` | records with at least one validation issue |
  | `tool_calls_checked`, `tool_calls_unchecked` | with the `openai-chat`, `anthropic-messages` and `tool-calls` presets |

  `diff` reports use `kind: data.diff` with summary keys `mode`, `changes`,
  `breaking`, `non_breaking` and `ok`, and a `details.changes` list.

- `predicate.details`: `validation_issues` and `drift_issues` lists (`kind`,
  `field`, `message`, `count`), the drift `thresholds` used, and the `preset` name.

Set `SOURCE_DATE_EPOCH` to fix `created_at` and make a report byte-for-byte
reproducible. Signing is optional and not built in; for example, with
[toolkit-ml-provenance](https://github.com/AKIVA-AI/toolkit-ml-provenance) installed:

```bash
toolkit-mlsbom sign-file report.json    # and later: toolkit-mlsbom verify-file report.json
```

Useful `check` options:

| Option | Default | Meaning |
|---|---|---|
| `--strict-integer` | off | Reject fractional values on integer-only fields. |
| `--max-missing` | 0.01 | Missing-rate ceiling. |
| `--max-null-increase` | 0.10 | Allowed absolute rise in null rate. |
| `--max-psi` | 0.25 | Allowed categorical PSI (below 0.1 is usually read as stable, above 0.25 as a significant shift). |
| `--max-mean-shift-sigma` | 3.0 | Allowed mean shift in baseline standard deviations. |
| `--max-length-psi` | 0.25 | Allowed PSI of text length and token-count histograms. |
| `--max-centroid-distance` | 0.2 | Allowed distance between embedding centroids (`--centroid-metric euclidean` or `cosine`). |
| `--metrics-out FILE` | none | Write pass/fail counters as JSON. |

Global options: `--verbose`, `--log-format json`, `--version`.

### Text and embedding drift

`profile` records text statistics for every string path automatically. The
tokenizer, the paths with language detection and the embedding paths are
stored in the profile's `config`, and `check` profiles the new batch the same
way, so they are chosen once:

```bash
toolkit-contracts profile --input base.jsonl --preset rag-chunks --out base.profile.json   --tokenizer tiktoken:cl100k_base --language text --embedding embedding
toolkit-contracts check --input new.jsonl --preset rag-chunks --baseline base.profile.json
```

Comparing profiles made with different tokenizers is an error (exit 2).

### LLM presets

Built-in contracts for common LLM data shapes. Use `--preset NAME` instead of
`--contract` with `check` and `profile`; `toolkit-contracts presets list` lists
them and `presets show NAME` prints the JSON Schema so you can copy and tighten it.

| Preset | Row shape | Extra record checks |
|---|---|---|
| `openai-chat` | `{"messages": [...], "tools"?: [...]}`; roles `system`/`developer`/`user`/`assistant`/`tool`, text or content-part arrays, assistant `tool_calls`, `weight` | tool-call arguments (a JSON string) parsed and validated against the tool's `parameters`; unknown tools; `tool` messages whose `tool_call_id` answers no earlier call |
| `anthropic-messages` | `{"system"?, "messages": [...], "tools"?}`; first message from `user`; `text`, `image`, `document`, `tool_use`, `tool_result`, `thinking`, `redacted_thinking` blocks (other block types pass with a `type`) | `tool_use.input` validated against the tool's `input_schema`; unknown tools; `tool_result` blocks with no matching `tool_use` |
| `tool-calls` | one call per row: `{"name", "arguments"}`, `{"type": "function", "function": {...}}` or a `tool_use` block | arguments validated against `--tools` (required) |
| `sft` | `messages` with at least one assistant turn, `prompt` + non-empty `completion`, or non-empty `text` | |
| `dpo` | `prompt`? + `chosen` + `rejected` (strings or message lists), or OpenAI `input` + `preferred_output` + `non_preferred_output` | identical chosen/rejected; chosen and rejected of different types |
| `rag-chunks` | `id`, non-empty `text`, optional `doc_id`, `source`, `title`, `chunk_index`, `start_char`/`end_char`, `metadata`, `embedding` | duplicate ids; embeddings of different lengths; `start_char > end_char` |

`--tools FILE` takes OpenAI tools (`[{"type": "function", "function": {"name", "parameters"}}]`),
legacy OpenAI functions or Anthropic tools (`[{"name", "input_schema"}]`), as a
list or as `{"tools": [...]}`. Tools inside a row take precedence. Without any
tool definitions, tool calls are counted as `tool_calls_unchecked` in the report
summary instead of failing. Tool arguments use strict JSON Schema integer rules
(`2.0` is an integer, `2.5` is not). Issue paths look like
`tool[get_weather].location`. The duplicate-id check keeps every chunk id in
memory.

### Contracts

`infer --enum-max 2` on a chat file writes a contract like this (the real file
has its keys sorted):

```json
{
  "version": 2,
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "id": {"type": "string"},
      "messages": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "role": {"type": "string", "enum": ["assistant", "user"]},
            "content": {"type": ["null", "string"]}
          },
          "required": ["content", "role"],
          "additionalProperties": true
        }
      }
    },
    "required": ["id", "messages"],
    "additionalProperties": true
  }
}
```

Edit it by hand to tighten it (`pattern`, `minimum`/`maximum`, `maxLength`,
`minItems`, `additionalProperties: false`, and so on), or pass any JSON Schema
file that stays within the supported subset as `--contract`. Issue kinds:
`missing_required`, `type_mismatch`, `unexpected_field`, `enum_mismatch`,
`const_mismatch`, `range_violation`, `length_violation`, `pattern_mismatch`,
`unique_violation`, `contains_violation`, `unexpected_item`,
`invalid_property_name`, `combinator_mismatch`, `false_schema`. When no branch
of an `anyOf`/`oneOf` matches, the issues of the closest branch are reported.
`pattern` uses Python regular expressions, which differ from ECMA-262 in rare
cases (for example `\p{...}` is rejected).

Input must be strict JSON: `NaN`, `Infinity` and numbers that overflow are
rejected with exit code 2. Profiles written by older versions still work;
regenerate the baseline to get nested paths and categorical counts.

### ODCS (Open Data Contract Standard)

[ODCS](https://bitol-io.github.io/open-data-contract-standard/) is the Bitol
(Linux Foundation) standard for data contracts, also used by tools such as
datacontract-cli. Convert in either direction:

```bash
pip install ".[odcs]"    # PyYAML; .json output and input work without it
toolkit-contracts odcs export --contract contract.json --out contract.odcs.yaml --name chat_sft
toolkit-contracts odcs import --input contract.odcs.yaml --out contract.json [--object NAME]
```

How the mapping works:

| JSON Schema | ODCS property |
|---|---|
| one non-null `type` | `logicalType` (`date`/`timestamp`/`time` import as strings with a `format`) |
| type without `null` | `required: true` (ODCS `required` means "not null") |
| nested key in `required` | parent's `logicalTypeOptions.required` |
| length, range, pattern, item-count keywords | `logicalTypeOptions` |
| `items`, nested `properties` | `items`, `properties` |
| `enum` / `const` | quality rule `metric: invalidValues`, `arguments.validValues`, `mustBe: 0` (and v3.2 `enum` on import) |
| (import) `map`, `vector` | `additionalProperties: <value schema>`; array of numbers with `minItems = maxItems = dimensions` |

ODCS has no presence flag for top-level columns, so a top-level key exports
as `required: true` only when it is both required and non-null. Constructs
ODCS cannot express (`anyOf`, `additionalProperties: false`, `$ref`, a
required-but-nullable top-level key, and so on) are listed as a warning, and
the exact JSON Schema is embedded in the schema object as the custom property
`jsonSchema`. `odcs import` uses that exact schema only while the ODCS fields
still describe it; if someone edited the fields, it uses the fields and warns.
Quality rules other than a strict valid-values list are reported, not enforced.

### Library use

```python
from toolkit_data_contracts_drift.contract import (
    drift_check, infer_contract, profile_records, validate_records,
)

contract = infer_contract(training_rows)
issues = validate_records(contract=contract, records=new_rows)
drift = drift_check(
    baseline=profile_records(contract=contract, records=training_rows),
    current=profile_records(contract=contract, records=new_rows),
)
```

See `examples/ml_pipeline_example.py` for a runnable walkthrough.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success: validation passed, no drift detected |
| `2`  | CLI error: invalid arguments, missing files, bad input |
| `3`  | Unexpected error, or interrupted |
| `4`  | Check failed: validation issues or drift detected |

## Reviewing contract changes

`diff` compares two contracts and classifies every change:

| Direction | Meaning | Examples |
|---|---|---|
| `tightens` | the new contract rejects data the old one accepted: existing data and producers may start failing | new required field, narrower type, removed enum value, lower `maxLength`, `additionalProperties: false` |
| `loosens` | the new contract accepts data the old one rejected: consumers may see values they do not expect | nullable field, new enum value, wider range, field no longer required |
| `both` | either can happen | changed `pattern`, changes inside `anyOf`/`oneOf`/`not`/`if` (not analysed further) |
| `annotation` | no effect on validity | `description`, `title`, `examples`, `format` |

`--mode backward` (default, as in schema registries) treats `tightens` and
`both` as breaking; `forward` treats `loosens` and `both` as breaking; `full`
treats all three as breaking. The exit code is 4 when anything is breaking.

```bash
toolkit-contracts diff --old main-contract.json --new contract.json --format table
```

Formats: `json` (report envelope, `kind: data.diff`), `table`, `markdown`
(for a PR comment) and `github` (workflow annotations).

### GitHub Action

```yaml
on: pull_request
jobs:
  contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # the action reads the base version with git show
      - uses: AKIVA-AI/toolkit-data-contracts@main   # pin a release tag once one exists
        with:
          contract: contracts/chat.contract.json
          mode: backward
```

The action writes a Markdown summary to the job page, annotates breaking
changes on the PR, fails the step when a change is breaking, and exposes the
JSON report path as the `report` output. Pass `old` and `new` instead of
`contract` to compare two files directly.

## CI example

```yaml
- name: Data contract gate
  run: |
    pip install git+https://github.com/AKIVA-AI/toolkit-data-contracts.git
    toolkit-contracts check --input data/batch.jsonl \
      --contract contracts/contract.json --baseline profiles/baseline.profile.json
```

## Docker

```bash
docker build -t toolkit-data-contracts .
docker run --rm -v "$PWD/data:/app/data" toolkit-data-contracts \
  toolkit-contracts check --input /app/data/batch.jsonl --contract /app/data/contract.json
```

`docker-compose.yml` has example `infer` and `check` services under the `tools` profile.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: `pytest`, `ruff check src/ tests/`, `pyright`.

## Contributing and security

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Please report security problems
privately, as described in [SECURITY.md](SECURITY.md).

## Releasing

Releases are cut by pushing a `vX.Y.Z` tag. CI runs the tests, builds the
sdist and wheel, checks them, attaches them to a GitHub Release and publishes
them to PyPI with Trusted Publishing. [RELEASING.md](RELEASING.md) describes
the process and how to verify a release.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
Releases before the relicensing remain available under the MIT License.
