# Quick start

## Install

```bash
git clone https://github.com/AKIVA-AI/toolkit-data-contracts.git
cd toolkit-data-contracts
pip install .
toolkit-contracts --help
```

## 1. Sample data

`samples.jsonl`:

```json
{"user_id": 1, "age": 25, "country": "US", "approved": true, "meta": {"source": "web"}}
{"user_id": 2, "age": 35, "country": "CA", "approved": true, "meta": {"source": "app"}}
{"user_id": 3, "age": 45, "country": "US", "approved": false, "meta": {"source": "web"}}
```

## 2. Infer a contract

```bash
toolkit-contracts infer --input samples.jsonl --out contract.json
```

`contract.json` holds a JSON Schema (keys are sorted in the real file):

```json
{
  "version": 2,
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "user_id": {"type": "integer"},
      "age": {"type": "integer"},
      "country": {"type": "string"},
      "approved": {"type": "boolean"},
      "meta": {
        "type": "object",
        "properties": {"source": {"type": "string"}},
        "required": ["source"],
        "additionalProperties": true
      }
    },
    "required": ["age", "approved", "country", "meta", "user_id"],
    "additionalProperties": true
  }
}
```

You can tighten it by hand, for example `"age": {"type": "integer", "minimum": 18}`
or `"country": {"enum": ["US", "CA"]}`.

Use `--disallow-extra` to reject keys the contract does not list, at every level,
and `--enum-max N` to give low-cardinality string fields an `enum`.

## 3. Profile a baseline

```bash
toolkit-contracts profile --input samples.jsonl --contract contract.json --out baseline.profile.json
```

## 4. Check a new batch

```bash
toolkit-contracts check --input new_batch.jsonl --contract contract.json \
  --baseline baseline.profile.json --format table
```

For a batch of three rows shaped like the samples but with `"country": "CN"`
in every row (the baseline only had US and CA), the output is:

```text
Status: FAIL

Validation: OK (no issues)

Drift Issues:
  Kind                      Field                 Count  Message
  ------------------------- -------------------- ------  ------------------------------
  drift_categorical         country                   1  psi=17.782 exceeds 0.250
```

Exit code is `0` on pass, `4` on validation or drift failure, and `2` on bad
input, so `check` can gate a CI job directly.

## Run the example

```bash
pip install -e ".[dev]"
python examples/ml_pipeline_example.py
```

See [README.md](README.md) for what each check does and its known limits.
