"""Open Data Contract Standard (ODCS) v3 import and export.

ODCS (https://bitol-io.github.io/open-data-contract-standard/, Bitol / Linux
Foundation) describes a dataset as a list of schema objects, each with a list
of properties. This module maps between that and our JSON Schema contracts.

Export writes ``apiVersion: v3.1.0``. Import reads ODCS v3.0.x to v3.2.0,
including the v3.2.0 ``enum``, ``map`` and ``vector`` property forms.

Mapping (JSON Schema -> ODCS property):

- ``type`` -> ``logicalType`` (one non-null type). ODCS ``required: true``
  means "may not be null", so a type without ``null`` exports as
  ``required: true``.
- Key presence inside a nested object -> the object's
  ``logicalTypeOptions.required``. ODCS has no presence flag for the columns
  of a top-level object, so a top-level key exports as ``required: true``
  only when it is both required and non-null.
- ``minLength``/``maxLength``/``pattern``/``format``, ``minimum``/``maximum``/
  ``exclusiveMinimum``/``exclusiveMaximum``/``multipleOf``,
  ``minItems``/``maxItems``/``uniqueItems``, ``minProperties``/
  ``maxProperties`` -> ``logicalTypeOptions``; ``items`` -> ``items``;
  nested ``properties`` -> ``properties``.
- ``enum``/``const`` -> a library quality rule ``metric: invalidValues`` with
  ``arguments.validValues`` and ``mustBe: 0``.

Anything else (``anyOf``, ``additionalProperties: false``, ``$ref`` and so on)
has no ODCS equivalent. When the mapping loses information, export also stores
the exact JSON Schema on the schema object as the custom property
``jsonSchema``. Import uses that exact schema only if the ODCS fields still
describe it (they were not edited since export); otherwise it maps the ODCS
fields and warns.
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid
from typing import Any

from .contract import CONTRACT_VERSION, JSON_SCHEMA_DIALECT, load_contract
from .schema import JSON_TYPES, SchemaError, check_schema, resolve_ref

ODCS_API_VERSION = "v3.1.0"
EMBEDDED_SCHEMA_PROPERTY = "jsonSchema"

_ANNOTATIONS = {
    "$schema",
    "$id",
    "$comment",
    "$defs",
    "definitions",
    "title",
    "description",
    "default",
    "examples",
    "deprecated",
    "readOnly",
    "writeOnly",
    "contentMediaType",
    "contentEncoding",
}
_STRING_OPTS = ("minLength", "maxLength", "pattern", "format")
_NUMBER_OPTS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf")
_ARRAY_OPTS = ("minItems", "maxItems", "uniqueItems")
_OBJECT_OPTS = ("minProperties", "maxProperties")
_HANDLED = (
    {"type", "enum", "const", "properties", "required", "items"}
    | set(_STRING_OPTS)
    | set(_NUMBER_OPTS)
    | set(_ARRAY_OPTS)
    | set(_OBJECT_OPTS)
)
_MAX_REF_DEPTH = 16


class OdcsError(ValueError):
    """The ODCS document cannot be converted."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _type_list(s: dict[str, Any]) -> list[str]:
    t = s.get("type")
    if t is None:
        return []
    names = [t] if isinstance(t, str) else list(t)
    return [n for n in JSON_TYPES if n in names]


def _type_value(types: list[str]) -> str | list[str]:
    ordered = [n for n in JSON_TYPES if n in types]
    return ordered[0] if len(ordered) == 1 else ordered


def _canon_value(v: Any) -> str:
    return json.dumps(v, sort_keys=True)


def normalize_schema(s: Any) -> Any:
    """A comparison form of a schema: sorted lists, ``additionalProperties: true``
    and ``$schema`` dropped. Used to decide whether a conversion was lossless."""
    if isinstance(s, list):
        return [normalize_schema(x) for x in s]
    if not isinstance(s, dict):
        return s
    out: dict[str, Any] = {}
    for k, v in s.items():
        if k == "$schema" or (k == "additionalProperties" and v is True):
            continue
        if k == "type":
            out[k] = sorted([v] if isinstance(v, str) else v)
        elif k == "required" and isinstance(v, list):
            if v:
                out[k] = sorted(v)
        elif k == "enum" and isinstance(v, list):
            out[k] = sorted(v, key=_canon_value)
        elif k == "const":
            out["enum"] = [v]
        elif k == "properties" and isinstance(v, dict):
            out[k] = {pk: normalize_schema(pv) for pk, pv in v.items()}
        else:
            out[k] = normalize_schema(v)
    return out


def _deref(node: Any, root: Any, lossy: list[str], depth: int = 0) -> Any:
    """Inline a same-document ``$ref`` (for the ODCS view only)."""
    while isinstance(node, dict) and "$ref" in node:
        if depth > _MAX_REF_DEPTH:
            lossy.append("recursive $ref")
            return {}
        lossy.append("$ref")
        target = resolve_ref(root, node["$ref"])
        extra = {k: v for k, v in node.items() if k != "$ref"}
        node = {**target, **extra} if isinstance(target, dict) else target
        depth += 1
    return node


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def _enum_quality(values: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "library",
            "metric": "invalidValues",
            "arguments": {"validValues": values},
            "mustBe": 0,
            "description": "Values must be one of validValues.",
        }
    ]


def _odcs_property(
    name: str | None,
    s: Any,
    *,
    root: Any,
    present: bool | None,
    lossy: list[str],
    where: str,
) -> dict[str, Any]:
    p: dict[str, Any] = {} if name is None else {"name": name}
    s = _deref(s, root, lossy)
    if not isinstance(s, dict):
        lossy.append(f"{where}: boolean schema")
        return p
    for k in s:
        if k not in _HANDLED and k not in _ANNOTATIONS and k != "additionalProperties":
            lossy.append(f"{where}: {k}")
    if s.get("additionalProperties", True) is not True:
        lossy.append(f"{where}: additionalProperties")

    types = _type_list(s)
    nullable = "null" in types
    base = [t for t in types if t != "null"]
    lt = base[0] if len(base) == 1 else None
    if len(base) > 1:
        lossy.append(f"{where}: multiple types {base}")
    if lt is not None:
        p["logicalType"] = lt
    if types:
        non_null = not nullable
        if present is None:
            p["required"] = non_null
        else:  # top-level column: presence and non-null share one flag
            p["required"] = non_null and present
            if non_null != present:
                lossy.append(f"{where}: presence differs from nullability")
    if isinstance(s.get("description"), str):
        p["description"] = s["description"]
    if isinstance(s.get("examples"), list):
        p["examples"] = s["examples"]

    opts: dict[str, Any] = {}
    kinds = {
        "string": _STRING_OPTS,
        "integer": _NUMBER_OPTS,
        "number": _NUMBER_OPTS,
        "array": _ARRAY_OPTS,
        "object": _OBJECT_OPTS,
    }
    for kw in set(_STRING_OPTS) | set(_NUMBER_OPTS) | set(_ARRAY_OPTS) | set(_OBJECT_OPTS):
        if kw in s:
            if lt is not None and kw in kinds.get(lt, ()):
                opts[kw] = s[kw]
            else:
                lossy.append(f"{where}: {kw} without a matching single type")

    if "items" in s:
        if lt == "array":
            p["items"] = _odcs_property(
                None, s["items"], root=root, present=None, lossy=lossy, where=f"{where}[]"
            )
        else:
            lossy.append(f"{where}: items without type array")
    if "properties" in s:
        if lt == "object":
            req = set(s.get("required") or [])
            p["properties"] = [
                _odcs_property(
                    k, v, root=root, present=None, lossy=lossy, where=f"{where}.{k}".lstrip(".")
                )
                for k, v in s["properties"].items()
            ]
            if req:
                opts["required"] = sorted(req)
        else:
            lossy.append(f"{where}: properties without type object")
    elif s.get("required"):
        if lt == "object":
            opts["required"] = sorted(set(s["required"]))
        else:
            lossy.append(f"{where}: required without type object")
    if opts:
        p["logicalTypeOptions"] = opts

    values = list(s["enum"]) if "enum" in s else ([s["const"]] if "const" in s else None)
    if values is not None:
        p["quality"] = _enum_quality([v for v in values if v is not None])
        if None in values and not nullable:
            lossy.append(f"{where}: enum allows null but type does not")
    return p


def _odcs_object(
    schema: Any, *, object_name: str, lossy: list[str], root: Any = None
) -> dict[str, Any]:
    root = schema if root is None else root
    s = _deref(schema, root, lossy)
    if not isinstance(s, dict) or _type_list(s) not in ([], ["object"]):
        raise OdcsError("the contract schema must describe a JSON object")
    for k in s:
        if k not in _ANNOTATIONS and k not in {
            "type",
            "properties",
            "required",
            "additionalProperties",
        }:
            lossy.append(f"$: {k}")
    if s.get("additionalProperties", True) is not True:
        lossy.append("$: additionalProperties")
    req = set(s.get("required") or [])
    obj: dict[str, Any] = {"name": object_name, "logicalType": "object"}
    if isinstance(s.get("description"), str):
        obj["description"] = s["description"]
    props = s.get("properties") or {}
    for k in req - set(props):
        lossy.append(f"$: required key {k!r} has no property")
    obj["properties"] = [
        _odcs_property(k, v, root=root, present=k in req, lossy=lossy, where=k)
        for k, v in props.items()
    ]
    return obj


def to_odcs(
    contract: Any,
    *,
    contract_id: str | None = None,
    name: str | None = None,
    version: str = "1.0.0",
    status: str = "draft",
    object_name: str = "records",
) -> tuple[dict[str, Any], list[str]]:
    """Export a contract as an ODCS v3.1.0 document.

    Returns:
        (document, lossy): ``lossy`` lists what the ODCS fields cannot express;
        when it is non-empty the exact JSON Schema is embedded as the
        ``jsonSchema`` custom property of the schema object.
    """
    c = load_contract(contract)
    schema = c["schema"]
    lossy: list[str] = []
    obj = _odcs_object(schema, object_name=object_name, lossy=lossy)
    if not lossy:
        back = _schema_from_object(obj, warnings=[])
        if normalize_schema(back) != normalize_schema(schema):
            lossy.append("round trip differs")
    if lossy:
        obj["customProperties"] = [
            {
                "property": EMBEDDED_SCHEMA_PROPERTY,
                "value": schema,
                "description": (
                    "Exact JSON Schema from toolkit-data-contracts; the ODCS fields are a "
                    "lossy view of it."
                ),
            }
        ]
    title = name or c.get("name") or schema.get("title") or object_name
    cid = contract_id or str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, "toolkit-data-contracts:" + json.dumps(schema, sort_keys=True)
        )
    )
    doc: dict[str, Any] = {
        "apiVersion": ODCS_API_VERSION,
        "kind": "DataContract",
        "id": cid,
        "name": str(title),
        "version": str(version),
        "status": str(status),
        "schema": [obj],
    }
    desc = c.get("description") or schema.get("description")
    if isinstance(desc, str):
        doc["description"] = {"purpose": desc}
    return doc, sorted(set(lossy))


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #

_LOGICAL = {
    "string": "string",
    "date": "string",
    "timestamp": "string",
    "time": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
    "map": "object",
    "vector": "array",
}
_DATE_FORMATS = {"date": "date", "timestamp": "date-time", "time": "time"}


def _enum_from_quality(q: Any, where: str, warnings: list[str]) -> list[Any] | None:
    if not isinstance(q, dict):
        return None
    metric = q.get("metric") or q.get("rule")
    args = _as_dict(q.get("arguments"))
    valid = args.get("validValues")
    strict = (
        q.get("mustBe") == 0 or q.get("mustBeLessOrEqualTo") == 0 or q.get("mustBeLessThan") == 1
    ) and q.get("unit") in (None, "rows")
    if metric == "invalidValues" and isinstance(valid, list) and strict:
        return list(valid)
    warnings.append(f"{where}: quality rule {metric or q.get('type')!r} is not enforced")
    return None


def _schema_from_prop(p: Any, where: str, warnings: list[str]) -> dict[str, Any]:
    if not isinstance(p, dict):
        raise OdcsError(f"{where}: property must be an object")
    s: dict[str, Any] = {}
    lt = p.get("logicalType")
    opts = _as_dict(p.get("logicalTypeOptions"))
    nullable = p.get("required") is not True
    base = _LOGICAL.get(lt) if isinstance(lt, str) else None
    if isinstance(lt, str) and base is None:
        warnings.append(f"{where}: unknown logicalType {lt!r}; accepting any value")
    if base is not None:
        s["type"] = _type_value([base, "null"] if nullable else [base])
    if isinstance(p.get("description"), str):
        s["description"] = p["description"]
    if isinstance(p.get("examples"), list):
        s["examples"] = p["examples"]

    if lt in _DATE_FORMATS:
        s["format"] = _DATE_FORMATS[lt]
    elif base == "string":
        for kw in _STRING_OPTS:
            if kw in opts:
                s[kw] = opts[kw]
    elif base in ("integer", "number"):
        for kw in _NUMBER_OPTS:
            if kw in opts:
                s[kw] = opts[kw]

    if lt == "vector":
        dims = opts.get("dimensions")
        s["items"] = {"type": "number"}
        if isinstance(dims, int):
            s["minItems"] = s["maxItems"] = dims
    elif base == "array":
        for kw in _ARRAY_OPTS:
            if kw in opts:
                s[kw] = opts[kw]
        if "items" in p:
            s["items"] = _schema_from_prop(p["items"], f"{where}[]", warnings)
    elif lt == "map":
        m = _as_dict(p.get("map"))
        if "value" in m:
            s["additionalProperties"] = _schema_from_prop(m["value"], f"{where}{{}}", warnings)
    elif base == "object":
        for kw in _OBJECT_OPTS:
            if kw in opts:
                s[kw] = opts[kw]
    if isinstance(p.get("properties"), list):
        s["properties"] = {}
        for i, child in enumerate(p["properties"]):
            cname = child.get("name") if isinstance(child, dict) else None
            if not isinstance(cname, str):
                raise OdcsError(f"{where}.properties[{i}]: missing name")
            s["properties"][cname] = _schema_from_prop(child, f"{where}.{cname}", warnings)
        req = opts.get("required")
        if isinstance(req, list) and req:
            s["required"] = sorted({str(r) for r in req})

    values: list[Any] | None = None
    if isinstance(p.get("enum"), list):  # ODCS v3.2.0 (RFC 0033)
        values = [e.get("value") for e in p["enum"] if isinstance(e, dict) and "value" in e]
    for q in p.get("quality") or []:
        found = _enum_from_quality(q, where, warnings)
        if found is not None:
            values = found
    if values is not None:
        if nullable and base is not None and None not in values:
            values = values + [None]
        s["enum"] = values
    return s


def _schema_from_object(obj: dict[str, Any], *, warnings: list[str]) -> dict[str, Any]:
    props = obj.get("properties") or []
    if not isinstance(props, list):
        raise OdcsError("schema object 'properties' must be a list")
    out: dict[str, Any] = {"$schema": JSON_SCHEMA_DIALECT, "type": "object", "properties": {}}
    if isinstance(obj.get("description"), str):
        out["description"] = obj["description"]
    required = []
    for i, p in enumerate(props):
        pname = p.get("name") if isinstance(p, dict) else None
        if not isinstance(pname, str):
            raise OdcsError(f"properties[{i}]: missing name")
        out["properties"][pname] = _schema_from_prop(p, pname, warnings)
        if p.get("required") is True:
            required.append(pname)
    if required:
        out["required"] = sorted(required)
    for q in obj.get("quality") or []:
        warnings.append(
            f"{obj.get('name')}: object-level quality rule {q.get('metric') or q.get('type')!r} "
            "is not enforced"
        )
    return out


def _embedded_schema(obj: dict[str, Any]) -> Any:
    for cp in obj.get("customProperties") or []:
        if isinstance(cp, dict) and cp.get("property") == EMBEDDED_SCHEMA_PROPERTY:
            return cp.get("value")
    return None


def _jsonable(v: Any) -> Any:
    """YAML may parse dates; make everything plain JSON."""
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, (_dt.date, _dt.datetime, _dt.time)):
        return v.isoformat()
    return v


def from_odcs(doc: Any, *, object_name: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Import one schema object of an ODCS v3 document as a contract.

    Returns:
        (contract, warnings): warnings list what could not be carried over
        (for example quality rules other than a strict valid-values list).

    Raises:
        OdcsError: if the document is not ODCS v3 or the object is ambiguous.
    """
    doc = _jsonable(doc)
    if not isinstance(doc, dict) or doc.get("kind", "DataContract") != "DataContract":
        raise OdcsError("not an ODCS data contract (kind must be DataContract)")
    api = str(doc.get("apiVersion", ""))
    if not api.startswith("v3."):
        raise OdcsError(f"unsupported ODCS apiVersion {api!r} (expected v3.x)")
    objects = [o for o in doc.get("schema") or [] if isinstance(o, dict)]
    if not objects:
        raise OdcsError("the ODCS document has no schema objects")
    if object_name is not None:
        chosen = [o for o in objects if o.get("name") == object_name]
        if not chosen:
            names = [o.get("name") for o in objects]
            raise OdcsError(f"no schema object named {object_name!r}; found {names}")
        obj = chosen[0]
    elif len(objects) == 1:
        obj = objects[0]
    else:
        names = [o.get("name") for o in objects]
        raise OdcsError(f"the document has several schema objects {names}; choose one")

    warnings: list[str] = []
    fields_schema = _schema_from_object(obj, warnings=warnings)
    schema: Any = fields_schema
    embedded = _embedded_schema(obj)
    if embedded is not None:
        try:
            check_schema(embedded)
            view = _odcs_object(embedded, object_name=str(obj.get("name")), lossy=[])
            same = normalize_schema(_schema_from_object(view, warnings=[])) == normalize_schema(
                fields_schema
            )
        except (SchemaError, OdcsError):
            same = False
        if same:
            schema = embedded
        else:
            warnings.append(
                "embedded jsonSchema no longer matches the ODCS fields; using the ODCS fields"
            )
    contract: dict[str, Any] = {"version": CONTRACT_VERSION, "schema": schema}
    if isinstance(doc.get("name"), str):
        contract["name"] = doc["name"]
    load_contract(contract)
    return contract, warnings


# --------------------------------------------------------------------------- #
# YAML
# --------------------------------------------------------------------------- #


def dump_yaml(doc: dict[str, Any]) -> str:
    """Serialize an ODCS document as YAML (requires the ``odcs`` extra: PyYAML)."""
    try:
        import yaml
    except ImportError as e:  # pragma: no cover - exercised without the extra
        raise OdcsError(
            "YAML output needs PyYAML: pip install 'toolkit-data-contracts[odcs]' "
            "(or write a .json file)"
        ) from e
    return str(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def parse_document(text: str) -> Any:
    """Parse an ODCS document from JSON or YAML text."""
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return json.loads(text)
    try:
        import yaml
    except ImportError as e:  # pragma: no cover - exercised without the extra
        raise OdcsError(
            "Reading YAML needs PyYAML: pip install 'toolkit-data-contracts[odcs]'"
        ) from e
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise OdcsError(f"invalid YAML: {e}") from e
