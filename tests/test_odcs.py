"""ODCS v3 import/export.

Exported documents are validated against the official ODCS JSON Schemas
(bitol-io/open-data-contract-standard, tag v3.2.0, commit f0bdad9; files
schema/odcs-json-schema-v3.1.0.json and -v3.2.0.json, vendored under
tests/fixtures/odcs) with the reference `jsonschema` Draft 2019-09 validator.
Import is exercised on official ODCS example documents from the same commit.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft201909Validator

from toolkit_data_contracts_drift.cli import EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.contract import infer_contract, validate_records
from toolkit_data_contracts_drift.odcs import (
    EMBEDDED_SCHEMA_PROPERTY,
    OdcsError,
    dump_yaml,
    from_odcs,
    normalize_schema,
    to_odcs,
)

FIX = Path(__file__).parent / "fixtures" / "odcs"


def _odcs_validator(version: str) -> Draft201909Validator:
    schema = json.loads((FIX / f"odcs-json-schema-{version}.json").read_text(encoding="utf-8"))
    Draft201909Validator.check_schema(schema)
    return Draft201909Validator(schema)


V31 = _odcs_validator("v3.1.0")
V32 = _odcs_validator("v3.2.0")


def _assert_official(doc: dict) -> None:
    errors = [e.message for e in V31.iter_errors(doc)]
    assert errors == [], errors
    assert [e.message for e in V32.iter_errors(doc)] == []


def _example(name: str) -> dict:
    return yaml.safe_load((FIX / "examples" / name).read_text(encoding="utf-8"))


CHAT = [
    {
        "id": "a1",
        "messages": [
            {"role": "user", "content": "hi", "score": 1},
            {"role": "assistant", "content": None},
        ],
        "meta": {"source": "web", "n": 2.5, "tags": ["x"]},
    },
    {
        "id": "a2",
        "messages": [{"role": "user", "content": "yo"}],
        "meta": {"source": "app", "n": 1},
    },
]


class TestExport:
    def test_inferred_contract_exports_valid_lossless_odcs(self):
        contract = infer_contract(CHAT, enum_max=2)
        doc, lossy = to_odcs(contract, name="chat")
        assert lossy == []
        # Through YAML, as a user would write it.
        doc = yaml.safe_load(dump_yaml(doc))
        _assert_official(doc)
        assert doc["apiVersion"] == "v3.1.0" and doc["kind"] == "DataContract"
        obj = doc["schema"][0]
        assert "customProperties" not in obj
        msgs = next(p for p in obj["properties"] if p["name"] == "messages")
        assert msgs["logicalType"] == "array"
        assert msgs["items"]["logicalTypeOptions"] == {"required": ["content", "role"]}
        role = next(p for p in msgs["items"]["properties"] if p["name"] == "role")
        assert role["quality"][0]["arguments"]["validValues"] == ["assistant", "user"]
        content = next(p for p in msgs["items"]["properties"] if p["name"] == "content")
        assert content["required"] is False  # nullable
        back, warnings = from_odcs(doc)
        assert warnings == []
        assert normalize_schema(back["schema"]) == normalize_schema(contract["schema"])

    def test_constraints_map_to_logical_type_options(self):
        schema = {
            "type": "object",
            "required": ["age", "name", "tags"],
            "properties": {
                "age": {"type": "integer", "minimum": 0, "maximum": 130, "multipleOf": 1},
                "name": {"type": "string", "minLength": 1, "maxLength": 50, "pattern": "^[A-Z]"},
                "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "score": {"type": ["null", "number"], "exclusiveMaximum": 1},
            },
        }
        doc, lossy = to_odcs({"schema": schema})
        _assert_official(doc)
        assert lossy == []
        props = {p["name"]: p for p in doc["schema"][0]["properties"]}
        assert props["age"]["logicalTypeOptions"] == {"minimum": 0, "maximum": 130, "multipleOf": 1}
        assert props["name"]["logicalTypeOptions"]["pattern"] == "^[A-Z]"
        assert props["tags"]["logicalTypeOptions"] == {"maxItems": 5}
        back, _ = from_odcs(doc)
        assert normalize_schema(back["schema"]) == normalize_schema(schema)

    def test_lossy_contract_embeds_exact_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "x": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                "m": {"type": "object", "properties": {"k": {"type": "string"}}},
            },
            "additionalProperties": False,
        }
        doc, lossy = to_odcs({"schema": schema})
        _assert_official(doc)
        assert "$: additionalProperties" in lossy and "x: anyOf" in lossy
        custom = doc["schema"][0]["customProperties"]
        assert custom[0]["property"] == EMBEDDED_SCHEMA_PROPERTY
        back, warnings = from_odcs(doc)
        assert warnings == []
        assert back["schema"] == schema

    def test_edited_fields_win_over_stale_embedded_schema(self):
        schema = {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": "string"}},
            "additionalProperties": False,
        }
        doc, _ = to_odcs({"schema": schema})
        edited = copy.deepcopy(doc)
        edited["schema"][0]["properties"][0]["logicalType"] = "integer"
        back, warnings = from_odcs(edited)
        assert any("no longer matches" in w for w in warnings)
        assert back["schema"]["properties"]["a"]["type"] == "integer"

    def test_top_level_presence_and_nullability_share_one_flag(self):
        schema = {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": ["null", "string"]}},
        }
        doc, lossy = to_odcs({"schema": schema})
        assert lossy == ["a: presence differs from nullability"]
        assert doc["schema"][0]["properties"][0]["required"] is False
        assert from_odcs(doc)[0]["schema"] == {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": ["null", "string"]}},
        }

    def test_official_validator_is_not_vacuous(self):
        doc, _ = to_odcs(infer_contract(CHAT))
        broken = copy.deepcopy(doc)
        del broken["id"]
        assert list(V31.iter_errors(broken))
        broken = copy.deepcopy(doc)
        broken["schema"][0]["properties"][0]["logicalType"] = "decimal"
        assert list(V31.iter_errors(broken))


class TestImportOfficialExamples:
    def test_enum_example_v3_2(self):
        contract, warnings = from_odcs(_example("enum.odcs.yaml"))
        assert warnings == []
        props = contract["schema"]["properties"]
        assert props["status"]["enum"] == ["pending", "processing", "shipped", "cancelled"]
        assert props["priority"] == {
            "type": ["null", "integer"],
            "description": "Numeric priority bucket (1 highest, 3 lowest).",
            "enum": [1, 2, 3, None],
        }
        assert contract["schema"]["required"] == ["country_code", "order_id", "status"]
        good = {"order_id": "o1", "status": "pending", "country_code": "US", "priority": None}
        bad = {"order_id": "o1", "status": "lost", "country_code": "US"}
        assert validate_records(contract=contract, records=[good]) == []
        issues = validate_records(contract=contract, records=[bad])
        assert [(i.kind, i.field) for i in issues] == [("enum_mismatch", "status")]

    def test_vector_example(self):
        contract, _ = from_odcs(_example("vector.odcs.yaml"))
        emb = contract["schema"]["properties"]["body_embedding"]
        assert emb == {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 1536,
            "maxItems": 1536,
        }

    def test_map_example(self):
        contract, _ = from_odcs(_example("map.odcs.yaml"))
        counts = contract["schema"]["properties"]["daily_counts"]
        assert counts["additionalProperties"]["minimum"] == 0
        assert validate_records(
            contract=contract, records=[{"product_id": "p", "daily_counts": {"a": -1}}]
        )

    def test_several_objects_need_a_choice(self):
        doc = _example("all-schema-types.odcs.yaml")
        with pytest.raises(OdcsError, match="several schema objects"):
            from_odcs(doc)
        contract, _ = from_odcs(doc, object_name="AnotherObject")
        x = contract["schema"]["properties"]["x"]
        assert x["items"]["properties"]["zip"]["type"] == ["null", "string"]

    def test_tolerant_quality_rule_is_reported_not_enforced(self):
        contract, warnings = from_odcs(_example("column-validity.odcs.yaml"))
        assert "enum" not in contract["schema"]["properties"]["air_quality_status"]
        assert warnings == ["air_quality_status: quality rule 'invalidValues' is not enforced"]

    def test_yaml_dates_become_strings(self):
        contract, _ = from_odcs(_example("all-schema-types.odcs.yaml"), object_name="tbl")
        assert contract["schema"]["properties"]["txn_ref_dt"]["examples"] == [
            "2022-10-03",
            "2020-01-28",
        ]
        assert contract["schema"]["properties"]["txn_ref_dt"]["format"] == "date"

    @pytest.mark.parametrize(
        "doc",
        [
            {"apiVersion": "v2.2.2", "kind": "DataContract", "schema": []},
            {"apiVersion": "v3.1.0", "kind": "Other", "schema": []},
            {"apiVersion": "v3.1.0", "kind": "DataContract", "schema": []},
        ],
    )
    def test_rejects_non_v3_documents(self, doc):
        with pytest.raises(OdcsError):
            from_odcs(doc)


class TestCli:
    def test_export_yaml_and_json_then_import(self, tmp_path: Path):
        data = tmp_path / "d.jsonl"
        data.write_text("\n".join(json.dumps(r) for r in CHAT) + "\n", encoding="utf-8")
        contract = tmp_path / "c.json"
        assert main(["infer", "--input", str(data), "--out", str(contract)]) == EXIT_SUCCESS
        for suffix in ("odcs.yaml", "odcs.json"):
            out = tmp_path / f"c.{suffix}"
            code = main(
                ["odcs", "export", "--contract", str(contract), "--out", str(out), "--name", "chat"]
            )
            assert code == EXIT_SUCCESS
            doc = yaml.safe_load(out.read_text(encoding="utf-8"))
            _assert_official(doc)
            back = tmp_path / f"back-{suffix}.json"
            assert main(["odcs", "import", "--input", str(out), "--out", str(back)]) == 0
            original = json.loads(contract.read_text(encoding="utf-8"))["schema"]
            imported = json.loads(back.read_text(encoding="utf-8"))
            assert imported["name"] == "chat"
            assert normalize_schema(imported["schema"]) == normalize_schema(original)
            code = main(["check", "--input", str(data), "--contract", str(back)])
            assert code == EXIT_SUCCESS

    def test_import_errors_exit_2(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("apiVersion: v2.2.0\nkind: DataContract\n", encoding="utf-8")
        out = tmp_path / "c.json"
        assert main(["odcs", "import", "--input", str(bad), "--out", str(out)]) == EXIT_CLI_ERROR
        assert not out.exists()

    def test_export_of_non_object_schema_exits_2(self, tmp_path: Path):
        contract = tmp_path / "c.json"
        contract.write_text(json.dumps({"schema": {"type": "string"}}), encoding="utf-8")
        out = tmp_path / "o.yaml"
        assert (
            main(["odcs", "export", "--contract", str(contract), "--out", str(out)])
            == EXIT_CLI_ERROR
        )
