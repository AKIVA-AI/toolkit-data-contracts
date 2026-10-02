"""A small, dependency-free JSON Schema (draft 2020-12) validator.

It implements the validation vocabulary that data contracts and LLM tool
schemas use in practice:

- any value: ``type``, ``enum``, ``const``
- numbers: ``minimum``, ``maximum``, ``exclusiveMinimum``, ``exclusiveMaximum``,
  ``multipleOf``
- strings: ``minLength``, ``maxLength``, ``pattern`` (Python ``re`` syntax)
- arrays: ``items``, ``prefixItems`` (and the draft-07 array form of ``items``
  with ``additionalItems``), ``contains``, ``minContains``, ``maxContains``,
  ``minItems``, ``maxItems``, ``uniqueItems``
- objects: ``properties``, ``required``, ``additionalProperties``,
  ``patternProperties``, ``propertyNames``, ``minProperties``,
  ``maxProperties``, ``dependentRequired``, ``dependentSchemas``
- combinators: ``allOf``, ``anyOf``, ``oneOf``, ``not``, ``if``/``then``/``else``
- references: ``$ref`` to a JSON pointer inside the same document
  (``#``, ``#/$defs/...``, ``#/definitions/...``)

Annotations (``title``, ``description``, ``default``, ``format`` and so on) are
accepted and ignored, as the specification allows; unknown keywords are ignored
too. Keywords from the specification that this module does **not** implement
(``unevaluatedProperties``, ``unevaluatedItems``, ``$dynamicRef``, ``$anchor``,
remote references, ``$id`` inside a subschema) make :func:`check_schema` raise
:class:`SchemaError`, so an unsupported contract fails loudly instead of
passing everything.

The validator is checked against the official JSON-Schema-Test-Suite
(``tests/test_json_schema_suite.py``).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from functools import lru_cache
from typing import Any
from urllib.parse import unquote

JSON_TYPES = ("null", "boolean", "integer", "number", "string", "object", "array")

MAX_DEPTH = 200
"""Maximum combined schema/data nesting before validation gives up (guards
against ``$ref`` cycles that never consume data)."""

UNSUPPORTED_KEYWORDS = frozenset(
    {
        "unevaluatedProperties",
        "unevaluatedItems",
        "$dynamicRef",
        "$dynamicAnchor",
        "$recursiveRef",
        "$recursiveAnchor",
        "$anchor",
    }
)

Issue = tuple[str, str, str]
"""(kind, path, message). ``path`` is ``$`` for the record itself, then dotted
keys, with ``[]`` for array items: ``messages[].content``."""


class SchemaError(ValueError):
    """The schema is malformed or uses a keyword this validator does not support."""


def json_type(value: Any) -> str:
    """The JSON type name of a parsed JSON value (``integer`` for Python ints)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _canon(v: Any) -> Any:
    """A hashable form in which JSON-equal values are equal (1 == 1.0, false != 0)."""
    if isinstance(v, bool):
        return ("b", v)
    if _is_number(v):
        if isinstance(v, float) and v.is_integer() and math.isfinite(v):
            return ("n", int(v))
        return ("n", v)
    if isinstance(v, str):
        return ("s", v)
    if v is None:
        return ("z",)
    if isinstance(v, list):
        return ("a", tuple(_canon(x) for x in v))
    if isinstance(v, dict):
        return ("o", frozenset((k, _canon(x)) for k, x in v.items()))
    return ("?", repr(v))


def json_equal(a: Any, b: Any) -> bool:
    """Equality with JSON semantics."""
    return _canon(a) == _canon(b)


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as e:
        raise SchemaError(f"invalid pattern {pattern!r}: {e}") from e


def _child(path: str, key: str) -> str:
    return key if path == "$" else f"{path}.{key}"


def _items(path: str) -> str:
    return f"{path}[]"


def _fewest(branches: list[list[Issue]]) -> list[Issue]:
    """The branch with the fewest issues (the first one on a tie)."""
    best = branches[0]
    for b in branches[1:]:
        if len(b) < len(best):
            best = b
    return best


def _is_multiple(value: float, divisor: float) -> bool:
    if isinstance(value, int) and isinstance(divisor, int):
        return value % divisor == 0
    try:
        with localcontext() as ctx:
            ctx.prec = 1000  # exact for any finite double
            return Decimal(repr(value)) % Decimal(repr(divisor)) == 0
    except (InvalidOperation, ValueError):
        return False


# --------------------------------------------------------------------------- #
# Schema checking
# --------------------------------------------------------------------------- #

_SCHEMA_MAP_KEYWORDS = ("properties", "patternProperties", "$defs", "definitions")
_SCHEMA_LIST_KEYWORDS = ("allOf", "anyOf", "oneOf", "prefixItems")
_SCHEMA_KEYWORDS = (
    "additionalProperties",
    "additionalItems",
    "contains",
    "propertyNames",
    "not",
    "if",
    "then",
    "else",
)
_NONNEG_INT_KEYWORDS = (
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minProperties",
    "maxProperties",
    "minContains",
    "maxContains",
)
_NUMBER_KEYWORDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")


def _is_schema(s: Any) -> bool:
    return isinstance(s, (dict, bool))


def check_schema(schema: Any) -> None:
    """Raise :class:`SchemaError` unless ``schema`` is a well-formed schema that
    uses only supported keywords, and every ``$ref`` resolves."""
    _check(schema, schema, "#", is_root=True)


def _check(node: Any, root: Any, where: str, *, is_root: bool = False) -> None:
    if isinstance(node, bool):
        return
    if not isinstance(node, dict):
        raise SchemaError(f"{where}: a schema must be an object or a boolean")
    bad = UNSUPPORTED_KEYWORDS.intersection(node)
    if bad:
        raise SchemaError(f"{where}: unsupported keyword(s) {sorted(bad)}")
    if "$id" in node and not is_root:
        raise SchemaError(f"{where}: $id inside a subschema is not supported")

    t = node.get("type")
    if t is not None:
        names = [t] if isinstance(t, str) else t
        if not isinstance(names, list) or not names:
            raise SchemaError(f"{where}/type: must be a type name or a non-empty list")
        for n in names:
            if n not in JSON_TYPES:
                raise SchemaError(f"{where}/type: unknown type {n!r}")
    if "enum" in node and not isinstance(node["enum"], list):
        raise SchemaError(f"{where}/enum: must be an array")
    if "required" in node and (
        not isinstance(node["required"], list)
        or not all(isinstance(x, str) for x in node["required"])
    ):
        raise SchemaError(f"{where}/required: must be an array of strings")
    for kw in _NONNEG_INT_KEYWORDS:
        if kw in node:
            v = node[kw]
            ok = (isinstance(v, int) and not isinstance(v, bool)) or (
                isinstance(v, float) and v.is_integer()
            )
            if not ok or v < 0:
                raise SchemaError(f"{where}/{kw}: must be a non-negative integer")
    for kw in _NUMBER_KEYWORDS:
        if kw in node and not _is_number(node[kw]):
            raise SchemaError(
                f"{where}/{kw}: must be a number (draft-04 boolean form is not supported)"
            )
    if "multipleOf" in node and (not _is_number(node["multipleOf"]) or node["multipleOf"] <= 0):
        raise SchemaError(f"{where}/multipleOf: must be a number > 0")
    if "pattern" in node:
        if not isinstance(node["pattern"], str):
            raise SchemaError(f"{where}/pattern: must be a string")
        _compile(node["pattern"])
    if "dependentRequired" in node:
        dr = node["dependentRequired"]
        if not isinstance(dr, dict) or not all(
            isinstance(v, list) and all(isinstance(x, str) for x in v) for v in dr.values()
        ):
            raise SchemaError(f"{where}/dependentRequired: must map names to string arrays")
    if "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str):
            raise SchemaError(f"{where}/$ref: must be a string")
        resolve_ref(root, ref)

    for kw in _SCHEMA_MAP_KEYWORDS + ("dependentSchemas",):
        if kw in node:
            m = node[kw]
            if not isinstance(m, dict):
                raise SchemaError(f"{where}/{kw}: must be an object")
            for k, sub in m.items():
                if kw == "patternProperties":
                    _compile(k)
                _check(sub, root, f"{where}/{kw}/{k}")
    for kw in _SCHEMA_LIST_KEYWORDS:
        if kw in node:
            lst = node[kw]
            if not isinstance(lst, list) or (kw != "prefixItems" and not lst):
                raise SchemaError(f"{where}/{kw}: must be a non-empty array of schemas")
            for i, sub in enumerate(lst):
                _check(sub, root, f"{where}/{kw}/{i}")
    if "items" in node:
        items = node["items"]
        if isinstance(items, list):  # draft-07 tuple form
            for i, sub in enumerate(items):
                _check(sub, root, f"{where}/items/{i}")
        else:
            _check(items, root, f"{where}/items")
    for kw in _SCHEMA_KEYWORDS:
        if kw in node:
            _check(node[kw], root, f"{where}/{kw}")


def resolve_ref(root: Any, ref: str) -> Any:
    """Resolve a same-document ``$ref`` (``#`` or ``#/json/pointer``)."""
    if not ref.startswith("#"):
        root_id = root.get("$id") if isinstance(root, dict) else None
        if isinstance(root_id, str) and ref.startswith(root_id + "#"):
            ref = ref[len(root_id) :]
        elif isinstance(root_id, str) and ref == root_id:
            return root
        else:
            raise SchemaError(f"$ref {ref!r}: only same-document references are supported")
    fragment = unquote(ref[1:])
    if fragment == "":
        return root
    if not fragment.startswith("/"):
        raise SchemaError(f"$ref {ref!r}: anchors are not supported")
    node = root
    for raw in fragment[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            raise SchemaError(f"$ref {ref!r} does not resolve")
    if not _is_schema(node):
        raise SchemaError(f"$ref {ref!r} does not point to a schema")
    return node


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


@dataclass
class Validator:
    """Validates instances against one (checked) schema.

    Args:
        schema: A JSON Schema (object or boolean).
        strict_integer: If False, ``integer`` accepts any number, so a field
            inferred from whole numbers accepts ``10.5``. JSON Schema itself is
            strict (the default here): ``integer`` accepts ``10`` and ``10.0``
            but not ``10.5``.
    """

    schema: Any
    strict_integer: bool = True
    _checked: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        check_schema(self.schema)
        self._checked = True

    def errors(self, instance: Any) -> list[Issue]:
        """All issues for ``instance``; empty when it is valid."""
        return self._errors(self.schema, instance, "$", 0)

    def is_valid(self, instance: Any) -> bool:
        return not self.errors(instance)

    # -- internals ---------------------------------------------------------- #

    def _is_type(self, v: Any, name: str) -> bool:
        if name == "integer":
            if isinstance(v, bool):
                return False
            if isinstance(v, int):
                return True
            if isinstance(v, float):
                return (not self.strict_integer) or v.is_integer()
            return False
        if name == "number":
            return _is_number(v)
        return json_type(v) == name

    def _errors(self, schema: Any, inst: Any, path: str, depth: int) -> list[Issue]:
        if depth > MAX_DEPTH:
            raise SchemaError("schema or data nesting too deep (reference cycle?)")
        if schema is True:
            return []
        if schema is False:
            return [("false_schema", path, "false_schema")]
        errs: list[Issue] = []

        if "$ref" in schema:
            target = resolve_ref(self.schema, schema["$ref"])
            errs.extend(self._errors(target, inst, path, depth + 1))

        t = schema.get("type")
        if t is not None:
            names = [t] if isinstance(t, str) else t
            if not any(self._is_type(inst, n) for n in names):
                errs.append(("type_mismatch", path, f"type_mismatch:{json_type(inst)}"))
                return errs

        if "enum" in schema and not any(json_equal(inst, e) for e in schema["enum"]):
            errs.append(("enum_mismatch", path, "enum"))
        if "const" in schema and not json_equal(inst, schema["const"]):
            errs.append(("const_mismatch", path, "const"))

        if _is_number(inst):
            errs.extend(self._number_errors(schema, inst, path))
        elif isinstance(inst, str):
            errs.extend(self._string_errors(schema, inst, path))
        elif isinstance(inst, list):
            errs.extend(self._array_errors(schema, inst, path, depth))
        elif isinstance(inst, dict):
            errs.extend(self._object_errors(schema, inst, path, depth))

        errs.extend(self._combinator_errors(schema, inst, path, depth))
        return errs

    def _number_errors(self, s: dict[str, Any], v: float, path: str) -> list[Issue]:
        errs: list[Issue] = []
        if "minimum" in s and v < s["minimum"]:
            errs.append(("range_violation", path, f"minimum:{s['minimum']}"))
        if "maximum" in s and v > s["maximum"]:
            errs.append(("range_violation", path, f"maximum:{s['maximum']}"))
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            errs.append(("range_violation", path, f"exclusiveMinimum:{s['exclusiveMinimum']}"))
        if "exclusiveMaximum" in s and v >= s["exclusiveMaximum"]:
            errs.append(("range_violation", path, f"exclusiveMaximum:{s['exclusiveMaximum']}"))
        if "multipleOf" in s and not _is_multiple(v, s["multipleOf"]):
            errs.append(("range_violation", path, f"multipleOf:{s['multipleOf']}"))
        return errs

    def _string_errors(self, s: dict[str, Any], v: str, path: str) -> list[Issue]:
        errs: list[Issue] = []
        n = len(v)  # code points, as JSON Schema specifies
        if "minLength" in s and n < s["minLength"]:
            errs.append(("length_violation", path, f"minLength:{int(s['minLength'])}"))
        if "maxLength" in s and n > s["maxLength"]:
            errs.append(("length_violation", path, f"maxLength:{int(s['maxLength'])}"))
        if "pattern" in s and not _compile(s["pattern"]).search(v):
            errs.append(("pattern_mismatch", path, f"pattern:{s['pattern']}"))
        return errs

    def _array_errors(self, s: dict[str, Any], v: list[Any], path: str, depth: int) -> list[Issue]:
        errs: list[Issue] = []
        ip = _items(path)
        items = s.get("items")
        if isinstance(items, list):  # draft-07 tuple form
            prefix, rest = items, s.get("additionalItems", True)
        else:
            prefix, rest = s.get("prefixItems", []), items if "items" in s else True
        for i, elem in enumerate(v):
            sub = prefix[i] if i < len(prefix) else rest
            if sub is False:
                errs.append(("unexpected_item", ip, "unexpected_item"))
            else:
                errs.extend(self._errors(sub, elem, ip, depth + 1))
        if "contains" in s:
            hits = sum(1 for elem in v if not self._errors(s["contains"], elem, ip, depth + 1))
            lo = s.get("minContains", 1)
            if hits < lo:
                errs.append(("contains_violation", path, f"minContains:{int(lo)}"))
            if "maxContains" in s and hits > s["maxContains"]:
                errs.append(("contains_violation", path, f"maxContains:{int(s['maxContains'])}"))
        if "minItems" in s and len(v) < s["minItems"]:
            errs.append(("length_violation", path, f"minItems:{int(s['minItems'])}"))
        if "maxItems" in s and len(v) > s["maxItems"]:
            errs.append(("length_violation", path, f"maxItems:{int(s['maxItems'])}"))
        if s.get("uniqueItems") is True:
            seen = [_canon(x) for x in v]
            if len(set(seen)) != len(seen):
                errs.append(("unique_violation", path, "uniqueItems"))
        return errs

    def _object_errors(
        self, s: dict[str, Any], v: dict[str, Any], path: str, depth: int
    ) -> list[Issue]:
        errs: list[Issue] = []
        props: dict[str, Any] = s.get("properties") or {}
        pprops: dict[str, Any] = s.get("patternProperties") or {}
        for name in s.get("required") or []:
            if name not in v:
                errs.append(("missing_required", _child(path, name), "missing_required"))
        for dep, needed in (s.get("dependentRequired") or {}).items():
            if dep in v:
                for name in needed:
                    if name not in v:
                        errs.append(("missing_required", _child(path, name), "dependent_required"))
        for dep, sub in (s.get("dependentSchemas") or {}).items():
            if dep in v:
                errs.extend(self._errors(sub, v, path, depth + 1))
        extra = s.get("additionalProperties", True)
        names = s.get("propertyNames")
        for k, val in v.items():
            cp = _child(path, k)
            if names is not None and self._errors(names, k, cp, depth + 1):
                errs.append(("invalid_property_name", cp, "propertyNames"))
            matched = False
            if k in props:
                matched = True
                errs.extend(self._errors(props[k], val, cp, depth + 1))
            for pat, sub in pprops.items():
                if _compile(pat).search(k):
                    matched = True
                    errs.extend(self._errors(sub, val, cp, depth + 1))
            if not matched:
                if extra is False:
                    errs.append(("unexpected_field", cp, "unexpected_field"))
                elif extra is not True:
                    errs.extend(self._errors(extra, val, cp, depth + 1))
        if "minProperties" in s and len(v) < s["minProperties"]:
            errs.append(("length_violation", path, f"minProperties:{int(s['minProperties'])}"))
        if "maxProperties" in s and len(v) > s["maxProperties"]:
            errs.append(("length_violation", path, f"maxProperties:{int(s['maxProperties'])}"))
        return errs

    def _combinator_errors(
        self, s: dict[str, Any], inst: Any, path: str, depth: int
    ) -> list[Issue]:
        errs: list[Issue] = []
        for sub in s.get("allOf") or []:
            errs.extend(self._errors(sub, inst, path, depth + 1))
        if "anyOf" in s:
            branches = [self._errors(sub, inst, path, depth + 1) for sub in s["anyOf"]]
            if all(branches):
                # Report the closest branch (fewest issues) so a discriminated
                # union such as chat messages keyed by role gives useful detail.
                errs.extend(_fewest(branches))
        if "oneOf" in s:
            branches = [self._errors(sub, inst, path, depth + 1) for sub in s["oneOf"]]
            passing = sum(1 for b in branches if not b)
            if passing == 0:
                errs.extend(_fewest(branches))
            elif passing > 1:
                errs.append(("combinator_mismatch", path, "oneOf:multiple_match"))
        if "not" in s and not self._errors(s["not"], inst, path, depth + 1):
            errs.append(("combinator_mismatch", path, "not"))
        if "if" in s:
            if not self._errors(s["if"], inst, path, depth + 1):
                if "then" in s:
                    errs.extend(self._errors(s["then"], inst, path, depth + 1))
            elif "else" in s:
                errs.extend(self._errors(s["else"], inst, path, depth + 1))
        return errs


def validate(schema: Any, instance: Any, *, strict_integer: bool = True) -> list[Issue]:
    """Convenience wrapper: check ``schema`` and return the issues for ``instance``."""
    return Validator(schema, strict_integer=strict_integer).errors(instance)
