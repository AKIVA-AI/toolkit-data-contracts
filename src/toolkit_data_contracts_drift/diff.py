"""Classify the changes between two contracts for review.

Every change gets a *direction*:

- ``tightens``: the new contract rejects some data the old one accepted, so
  existing data and producers may start failing (for example a new required
  field, a narrower type, a removed enum value, a smaller ``maxLength``).
- ``loosens``: the new contract accepts some data the old one rejected, so
  consumers written against the old contract may receive data they do not
  expect (for example a nullable field, a new enum value, a larger range).
- ``both``: the change can do either (for example a changed ``pattern``, or a
  change inside ``anyOf`` that is not analysed further).
- ``annotation``: no effect on validity (``description``, ``title``,
  ``examples``, ``format`` and so on).

The compatibility *mode* decides which directions are breaking, using the
schema-registry vocabulary:

- ``backward`` (default): the new contract must accept everything the old one
  accepted; ``tightens`` and ``both`` are breaking.
- ``forward``: the old contract must accept everything the new one accepts;
  ``loosens`` and ``both`` are breaking.
- ``full``: both; every non-annotation change is breaking.

The analysis is structural and conservative: it compares keyword by keyword
and never reports a validity-changing edit as an annotation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .contract import load_contract
from .schema import JSON_TYPES, resolve_ref

MODES = ("backward", "forward", "full")
_BREAKING = {
    "backward": {"tightens", "both"},
    "forward": {"loosens", "both"},
    "full": {"tightens", "loosens", "both"},
}
_ANNOTATIONS = {
    "$schema",
    "$id",
    "$comment",
    "title",
    "description",
    "default",
    "examples",
    "deprecated",
    "readOnly",
    "writeOnly",
    "format",
    "contentMediaType",
    "contentEncoding",
}
_LOWER = ("minimum", "exclusiveMinimum", "minLength", "minItems", "minProperties", "minContains")
_UPPER = ("maximum", "exclusiveMaximum", "maxLength", "maxItems", "maxProperties", "maxContains")
_STRUCTURAL = {
    "type",
    "enum",
    "const",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "pattern",
    "uniqueItems",
    "multipleOf",
    "$ref",
    "$defs",
    "definitions",
    *_LOWER,
    *_UPPER,
}
_MAX_DEPTH = 64


@dataclass(frozen=True)
class Change:
    path: str
    change: str
    direction: str
    old: Any = None
    new: Any = None

    def to_json(self, mode: str) -> dict[str, Any]:
        return {
            "path": self.path,
            "change": self.change,
            "direction": self.direction,
            "breaking": self.direction in _BREAKING[mode],
            "old": self.old,
            "new": self.new,
        }


def _child(path: str, key: str) -> str:
    return key if path == "$" else f"{path}.{key}"


def _deref(node: Any, root: Any) -> Any:
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 32:
        target = resolve_ref(root, node["$ref"])
        extra = {k: v for k, v in node.items() if k != "$ref"}
        node = {**target, **extra} if isinstance(target, dict) else target
        seen += 1
    return node


def _types(s: dict[str, Any]) -> set[str] | None:
    t = s.get("type")
    if t is None:
        return None
    return {t} if isinstance(t, str) else set(t)


def _covers(types: set[str] | None, t: str) -> bool:
    if types is None:
        return True
    return t in types or (t == "integer" and "number" in types)


def _enum(s: dict[str, Any]) -> list[Any] | None:
    if "const" in s:
        return [s["const"]]
    e = s.get("enum")
    return list(e) if isinstance(e, list) else None


def _key(v: Any) -> str:
    return json.dumps(v, sort_keys=True)


def _trivial(s: Any) -> bool:
    """True for a schema that accepts anything (``true``, ``{}`` or annotations only)."""
    if s is True:
        return True
    return isinstance(s, dict) and all(k in _ANNOTATIONS for k in s)


class _Differ:
    def __init__(self, old_root: Any, new_root: Any) -> None:
        self.old_root = old_root
        self.new_root = new_root
        self.changes: list[Change] = []

    def add(self, path: str, change: str, direction: str, old: Any = None, new: Any = None) -> None:
        self.changes.append(Change(path, change, direction, old, new))

    def node(self, o: Any, n: Any, path: str, depth: int = 0) -> None:
        if depth > _MAX_DEPTH:
            return
        o = _deref(o, self.old_root)
        n = _deref(n, self.new_root)
        if _key(o) == _key(n):
            return
        if isinstance(o, bool) or isinstance(n, bool):
            if _trivial(o) and _trivial(n):
                return
            direction = "loosens" if _trivial(n) else "tightens" if _trivial(o) else "both"
            self.add(path, "schema replaced", direction, o, n)
            return
        if not isinstance(o, dict) or not isinstance(n, dict):
            self.add(path, "schema replaced", "both", o, n)
            return
        self._types(o, n, path)
        self._enum(o, n, path)
        self._bounds(o, n, path)
        self._simple(o, n, path)
        self._object(o, n, path, depth)
        if "items" in o or "items" in n:
            oi, ni = o.get("items", True), n.get("items", True)
            if isinstance(oi, list) or isinstance(ni, list):
                if _key(oi) != _key(ni):
                    self.add(path, "tuple items changed (not analysed)", "both", oi, ni)
            else:
                self.node(oi, ni, f"{path}[]", depth + 1)
        for k in sorted(set(o) | set(n)):
            if k in _STRUCTURAL or k in ("$schema", "$id", "$comment"):
                continue
            ov, nv = o.get(k), n.get(k)
            if _key(ov) == _key(nv):
                continue
            if k in _ANNOTATIONS:
                self.add(path, f"{k} changed", "annotation", ov, nv)
            elif k not in o:
                self.add(path, f"{k} added (not analysed)", "tightens", None, nv)
            elif k not in n:
                self.add(path, f"{k} removed (not analysed)", "loosens", ov, None)
            else:
                self.add(path, f"{k} changed (not analysed)", "both", ov, nv)

    def _types(self, o: dict[str, Any], n: dict[str, Any], path: str) -> None:
        ot, nt = _types(o), _types(n)
        if ot == nt:
            return
        lost = [t for t in JSON_TYPES if (ot is None or t in ot) and not _covers(nt, t)]
        gained = [t for t in JSON_TYPES if (nt is None or t in nt) and not _covers(ot, t)]
        if not lost and not gained:
            return
        direction = "both" if lost and gained else "tightens" if lost else "loosens"
        label = "type changed"
        if gained == ["null"] and not lost:
            label = "became nullable"
        elif lost == ["null"] and not gained:
            label = "no longer nullable"
        self.add(path, label, direction, o.get("type"), n.get("type"))

    def _enum(self, o: dict[str, Any], n: dict[str, Any], path: str) -> None:
        oe, ne = _enum(o), _enum(n)
        if oe is None and ne is None:
            return
        if oe is None:
            self.add(path, "enum added", "tightens", None, ne)
            return
        if ne is None:
            self.add(path, "enum removed", "loosens", oe, None)
            return
        okeys, nkeys = {_key(v) for v in oe}, {_key(v) for v in ne}
        removed = [v for v in oe if _key(v) not in nkeys]
        added = [v for v in ne if _key(v) not in okeys]
        if removed:
            self.add(path, "enum values removed", "tightens", removed, None)
        if added:
            self.add(path, "enum values added", "loosens", None, added)

    def _bounds(self, o: dict[str, Any], n: dict[str, Any], path: str) -> None:
        for kw, lower in [(k, True) for k in _LOWER] + [(k, False) for k in _UPPER]:
            ov, nv = o.get(kw), n.get(kw)
            if ov == nv:
                continue
            if ov is None:
                direction = "tightens"
            elif nv is None:
                direction = "loosens"
            else:
                raised = nv > ov
                direction = "tightens" if raised == lower else "loosens"
            self.add(path, f"{kw} changed", direction, ov, nv)
        ov, nv = o.get("multipleOf"), n.get("multipleOf")
        if ov != nv:
            if ov is None:
                direction = "tightens"
            elif nv is None:
                direction = "loosens"
            elif isinstance(ov, int) and isinstance(nv, int) and nv % ov == 0:
                direction = "tightens"
            elif isinstance(ov, int) and isinstance(nv, int) and ov % nv == 0:
                direction = "loosens"
            else:
                direction = "both"
            self.add(path, "multipleOf changed", direction, ov, nv)

    def _simple(self, o: dict[str, Any], n: dict[str, Any], path: str) -> None:
        op, np_ = o.get("pattern"), n.get("pattern")
        if op != np_:
            direction = "tightens" if op is None else "loosens" if np_ is None else "both"
            self.add(path, "pattern changed", direction, op, np_)
        ou, nu = bool(o.get("uniqueItems")), bool(n.get("uniqueItems"))
        if ou != nu:
            self.add(path, "uniqueItems changed", "tightens" if nu else "loosens", ou, nu)

    def _object(self, o: dict[str, Any], n: dict[str, Any], path: str, depth: int) -> None:
        oreq, nreq = set(o.get("required") or []), set(n.get("required") or [])
        for k in sorted(nreq - oreq):
            self.add(_child(path, k), "became required", "tightens")
        for k in sorted(oreq - nreq):
            self.add(_child(path, k), "no longer required", "loosens")
        oprops: dict[str, Any] = o.get("properties") or {}
        nprops: dict[str, Any] = n.get("properties") or {}
        oextra, nextra = o.get("additionalProperties", True), n.get("additionalProperties", True)
        for k in sorted(set(oprops) | set(nprops)):
            cp = _child(path, k)
            if k in oprops and k in nprops:
                self.node(oprops[k], nprops[k], cp, depth + 1)
            elif k in nprops:
                # Before: the key fell under additionalProperties of the old object.
                self._added_field(oextra, nprops[k], cp)
            else:
                self._removed_field(oprops[k], nextra, cp)
        if _key(oextra) != _key(nextra):
            if isinstance(oextra, bool) and isinstance(nextra, bool):
                self.add(
                    path,
                    "additionalProperties changed",
                    "tightens" if not nextra else "loosens",
                    oextra,
                    nextra,
                )
            else:
                self.node(oextra, nextra, f"{path}.*", depth + 1)

    def _added_field(self, old_extra: Any, new_schema: Any, path: str) -> None:
        if old_extra is False:
            self.add(path, "field added", "loosens", None, new_schema)
        elif _trivial(old_extra):
            if _trivial(new_schema):
                self.add(path, "field added", "annotation", None, new_schema)
            else:
                self.add(path, "field added", "tightens", None, new_schema)
        else:
            self.add(path, "field added", "both", old_extra, new_schema)

    def _removed_field(self, old_schema: Any, new_extra: Any, path: str) -> None:
        if new_extra is False:
            self.add(path, "field removed", "tightens", old_schema, None)
        elif _trivial(new_extra):
            direction = "annotation" if _trivial(old_schema) else "loosens"
            self.add(path, "field removed", direction, old_schema, None)
        else:
            self.add(path, "field removed", "both", old_schema, new_extra)


def diff_contracts(old: Any, new: Any) -> list[Change]:
    """Changes from ``old`` to ``new`` (contracts, v1 contracts or bare schemas)."""
    o = load_contract(old)["schema"]
    n = load_contract(new)["schema"]
    d = _Differ(o, n)
    d.node(o, n, "$")
    return d.changes


def summarize(changes: list[Change], mode: str) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; choose from {MODES}")
    breaking = sum(1 for c in changes if c.direction in _BREAKING[mode])
    return {
        "mode": mode,
        "changes": len(changes),
        "breaking": breaking,
        "non_breaking": len(changes) - breaking,
        "ok": breaking == 0,
    }
