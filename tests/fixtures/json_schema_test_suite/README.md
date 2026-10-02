# JSON Schema Test Suite (vendored subset)

Files under `draft2020-12/` are copied unchanged from the official
[JSON-Schema-Test-Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite)
at commit `5b0ee1613e45fcc2bddac00e07c19cd49b00d8a8` (`tests/draft2020-12/`).
They are MIT-licensed; see `LICENSE` in this folder.

Only files for keywords this project implements are vendored.
`tests/test_json_schema_suite.py` runs every case and keeps an explicit list of
the cases the validator rejects as unsupported (remote refs, `$id`/`$anchor`
based refs, `unevaluated*`, `$dynamicRef`).
