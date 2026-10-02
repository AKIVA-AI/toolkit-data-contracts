"""Contracts (JSON Schema), streaming inference, validation, profiling and drift.

A contract is ``{"version": 2, "schema": <JSON Schema>}``. The schema is a
draft 2020-12 JSON Schema restricted to the subset implemented in
:mod:`.schema`. Version 1 contracts (``fields`` / ``types`` / ``required``)
and bare JSON Schema documents are accepted and converted on load.

Every function that takes ``records`` accepts any iterable and reads it once,
so large JSONL files are processed in constant memory (apart from the schema,
the profile and the bounded per-field category counts).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .schema import JSON_TYPES, SchemaError, Validator, check_schema, json_type, resolve_ref
from .text import (
    CENTROID_METRICS,
    WHITESPACE,
    is_vector,
    length_bin,
    make_language_detector,
    make_tokenizer,
)
from .types import ValidationIssue

CONTRACT_VERSION = 2
PROFILE_VERSION = 2
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

MAX_INFER_DEPTH = 32
"""Inference describes nested objects/arrays down to this depth; deeper values
get a ``type`` only."""

MAX_TRACKED_CATEGORIES = 50
"""A string/boolean field with more distinct values than this in a profile is
treated as high-cardinality (IDs, free text) and gets no categorical drift check."""

_PSI_EPSILON = 1e-4


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _v1_field_to_schema(f: Mapping[str, Any], allow_extra: bool) -> dict[str, Any] | bool:
    types = sorted({str(t) for t in (f.get("types") or [])})
    if not types:
        return False  # a v1 field with no types accepted no value
    s: dict[str, Any] = {"type": types[0] if len(types) == 1 else types}
    props = f.get("properties")
    if isinstance(props, dict):
        s["properties"] = {str(k): _v1_field_to_schema(v, allow_extra) for k, v in props.items()}
        required = sorted(str(k) for k, v in props.items() if v.get("required"))
        if required:
            s["required"] = required
        s["additionalProperties"] = bool(allow_extra)
    return s


def contract_from_v1(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a version 1 contract (``fields``/``types``/``required``) to version 2."""
    allow_extra = bool(obj.get("allow_extra_fields", True))
    fields = obj.get("fields") or {}
    if not isinstance(fields, dict):
        raise SchemaError("contract 'fields' must be an object")
    root = _v1_field_to_schema({"types": ["object"], "properties": fields}, allow_extra=allow_extra)
    if not isinstance(root, dict):  # unreachable: the root always has a type
        raise SchemaError("invalid v1 contract")
    schema = {"$schema": JSON_SCHEMA_DIALECT, **root}
    return {"version": CONTRACT_VERSION, "schema": schema}


def load_contract(obj: Any) -> dict[str, Any]:
    """Normalize a contract document to version 2 and check its schema.

    Accepts a version 2 contract, a version 1 contract, or a bare JSON Schema.

    Raises:
        ValueError: (``SchemaError``) if the document is not a usable contract.
    """
    if not isinstance(obj, dict):
        raise SchemaError("contract must be a JSON object")
    if "schema" in obj:
        contract = dict(obj)
        contract["version"] = int(obj.get("version") or CONTRACT_VERSION)
    elif "fields" in obj or "allow_extra_fields" in obj:
        contract = contract_from_v1(obj)
    elif any(k in obj for k in ("type", "properties", "$schema", "$ref", "anyOf", "oneOf")):
        contract = {"version": CONTRACT_VERSION, "schema": obj}
    else:
        raise SchemaError("not a contract: expected 'schema', 'fields' or a JSON Schema")
    check_schema(contract["schema"])
    return contract


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #


class _Node:
    """Accumulates what was seen at one position in the records."""

    __slots__ = ("types", "obj_count", "key_counts", "children", "items", "strings", "depth")

    def __init__(self, depth: int) -> None:
        self.types: set[str] = set()
        self.obj_count = 0
        self.key_counts: Counter[str] = Counter()
        self.children: dict[str, _Node] = {}
        self.items: _Node | None = None
        self.strings: set[str] | None = set()
        self.depth = depth

    def add(self, v: Any, enum_max: int) -> None:
        jt = json_type(v)
        self.types.add(jt)
        if jt == "string" and enum_max > 0 and self.strings is not None:
            self.strings.add(v)
            if len(self.strings) > enum_max:
                self.strings = None
        if self.depth >= MAX_INFER_DEPTH:
            return
        if jt == "object":
            self.obj_count += 1
            for k, child in v.items():
                self.key_counts[k] += 1
                node = self.children.get(k)
                if node is None:
                    node = self.children[k] = _Node(self.depth + 1)
                node.add(child, enum_max)
        elif jt == "array":
            if self.items is None:
                self.items = _Node(self.depth + 1)
            for elem in v:
                self.items.add(elem, enum_max)

    def to_schema(self, *, allow_extra: bool, enum_max: int) -> dict[str, Any]:
        types = set(self.types)
        if "number" in types:
            types.discard("integer")  # JSON Schema "number" includes integers
        ordered = [t for t in JSON_TYPES if t in types]
        s: dict[str, Any] = {}
        if ordered:
            s["type"] = ordered[0] if len(ordered) == 1 else ordered
        if "object" in types and self.depth < MAX_INFER_DEPTH:
            s["properties"] = {
                k: n.to_schema(allow_extra=allow_extra, enum_max=enum_max)
                for k, n in sorted(self.children.items())
            }
            required = sorted(k for k, c in self.key_counts.items() if c == self.obj_count)
            if required:
                s["required"] = required
            s["additionalProperties"] = bool(allow_extra)
        if "array" in types and self.items is not None and self.items.types:
            s["items"] = self.items.to_schema(allow_extra=allow_extra, enum_max=enum_max)
        if enum_max > 0 and self.strings and types <= {"string", "null"} and "string" in types:
            s["enum"] = sorted(self.strings) + ([None] if "null" in types else [])
        return s


class SchemaInferrer:
    """Streaming contract inference: call :meth:`add` per record, then :meth:`contract`."""

    def __init__(self, *, allow_extra_fields: bool = True, enum_max: int = 0) -> None:
        self.allow_extra_fields = bool(allow_extra_fields)
        self.enum_max = max(0, int(enum_max))
        self.records = 0
        self._root = _Node(0)

    def add(self, record: Mapping[str, Any]) -> None:
        self.records += 1
        self._root.add(dict(record), self.enum_max)

    def contract(self) -> dict[str, Any]:
        root = self._root
        if not root.types:
            root.types.add("object")
        schema = root.to_schema(allow_extra=self.allow_extra_fields, enum_max=self.enum_max)
        schema.setdefault("properties", {})
        schema.setdefault("additionalProperties", self.allow_extra_fields)
        return {"version": CONTRACT_VERSION, "schema": {"$schema": JSON_SCHEMA_DIALECT, **schema}}


def infer_contract(
    records: Iterable[Mapping[str, Any]],
    *,
    allow_extra_fields: bool = True,
    enum_max: int = 0,
) -> dict[str, Any]:
    """Infer a version 2 contract (JSON Schema) from records.

    Nested objects are described with ``properties``/``required`` and arrays
    with ``items`` (the merged shape of every element), to depth
    ``MAX_INFER_DEPTH``. A key is ``required`` when it is present in every
    object seen at that position. ``null`` joins the ``type`` list when seen,
    and ``integer`` is dropped when ``number`` is also seen.

    Args:
        records: Iterable of JSON objects, read once.
        allow_extra_fields: Sets ``additionalProperties`` on every object.
        enum_max: If > 0, a string field with at most this many distinct
            values gets an ``enum`` of those values.
    """
    inf = SchemaInferrer(allow_extra_fields=allow_extra_fields, enum_max=enum_max)
    for rec in records:
        inf.add(rec)
    return inf.contract()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


class RecordValidator:
    """Streaming validation with issue counts aggregated per (kind, path, message).

    ``checks`` are extra per-record callables (for example a preset's
    tool-argument checks) returning ``(kind, path, message)`` tuples; their
    issues are counted the same way.
    """

    def __init__(
        self,
        contract: Any,
        *,
        strict_integer: bool = False,
        checks: Iterable[Callable[[Any], list[tuple[str, str, str]]]] = (),
    ) -> None:
        self.contract = load_contract(contract)
        self._validator = Validator(self.contract["schema"], strict_integer=strict_integer)
        self._checks = list(checks)
        self._counts: Counter[tuple[str, str, str]] = Counter()
        self.records = 0
        self.invalid_records = 0

    def add(self, record: Any) -> None:
        self.records += 1
        errs = self._validator.errors(record)
        for check in self._checks:
            errs.extend(check(record))
        if errs:
            self.invalid_records += 1
        for e in errs:
            self._counts[e] += 1

    def issues(self) -> list[ValidationIssue]:
        return [
            ValidationIssue(kind=k, field=p, message=m, count=n)
            for (k, p, m), n in sorted(self._counts.items())
        ]


def validate_records(
    *,
    contract: Any,
    records: Iterable[Any],
    strict_integer: bool = False,
) -> list[ValidationIssue]:
    """Validate records against a contract.

    Issues are aggregated per (kind, path, message) with a count. Paths are
    dotted keys with ``[]`` for array items (``messages[].role``); ``$`` is
    the record itself.

    Args:
        contract: A version 2 or version 1 contract, or a bare JSON Schema.
        records: Records to validate (any iterable, read once).
        strict_integer: If True, ``integer`` rejects fractional numbers as JSON
            Schema specifies. The default False treats integer and number as
            one JSON numeric type, so a field inferred from whole numbers
            accepts ``10.5``.

    Returns:
        ValidationIssue list; empty means every record is valid.
    """
    v = RecordValidator(contract, strict_integer=strict_integer)
    for rec in records:
        v.add(rec)
    return v.issues()


# --------------------------------------------------------------------------- #
# Profiling
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Profile:
    version: int
    field_stats: dict[str, dict[str, Any]]
    records: int = 0
    config: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Serialize the profile to a JSON-compatible dictionary."""
        return {
            "version": int(self.version),
            "records": int(self.records),
            "config": dict(self.config),
            "field_stats": dict(self.field_stats),
        }

    @staticmethod
    def from_json(obj: Any) -> Profile:
        """Deserialize a Profile (version 1 or 2) from a JSON-parsed dictionary.

        Raises:
            ValueError: If obj is not a dict or is missing field_stats.
        """
        if not isinstance(obj, dict):
            raise ValueError("profile_not_object")
        version = int(obj.get("version", 0))
        stats = obj.get("field_stats")
        if not isinstance(stats, dict):
            raise ValueError("profile_missing_field_stats")
        return Profile(
            version=version,
            field_stats={str(k): dict(v) for k, v in stats.items()},
            records=int(obj.get("records") or 0),
            config=dict(obj.get("config") or {}),
        )


def _category_key(value: Any) -> str | None:
    """Return the categorical bucket for a value, or None if it is not categorical."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return None


@dataclass
class _FieldAcc:
    opportunities: int = 0
    missing: int = 0
    type_counts: Counter[str] = field(default_factory=Counter)
    n: int = 0
    total: float = 0.0
    mean: float = 0.0
    m2: float = 0.0
    lo: float = math.inf
    hi: float = -math.inf
    cat_count: int = 0
    cats: Counter[str] | None = field(default_factory=Counter)
    text_n: int = 0
    chars_sum: int = 0
    tokens_sum: int = 0
    chars_hist: Counter[str] = field(default_factory=Counter)
    tokens_hist: Counter[str] = field(default_factory=Counter)
    langs: Counter[str] | None = None
    emb_sum: list[float] | None = None
    emb_n: int = 0
    emb_skipped: int = 0

    def observe_text(
        self, text: str, tokenize: Callable[[str], int], detect: Callable[[str], str] | None
    ) -> None:
        chars, tokens = len(text), tokenize(text)
        self.text_n += 1
        self.chars_sum += chars
        self.tokens_sum += tokens
        self.chars_hist[length_bin(chars)] += 1
        self.tokens_hist[length_bin(tokens)] += 1
        if detect is not None:
            if self.langs is None:
                self.langs = Counter()
            self.langs[detect(text)] += 1

    def observe_vector(self, v: Any) -> None:
        if not is_vector(v) or (self.emb_sum is not None and len(v) != len(self.emb_sum)):
            self.emb_skipped += 1
            return
        if self.emb_sum is None:
            self.emb_sum = [0.0] * len(v)
        for i, x in enumerate(v):
            self.emb_sum[i] += float(x)
        self.emb_n += 1

    def observe(self, v: Any) -> None:
        jt = json_type(v)
        self.type_counts[jt] += 1
        if jt in ("integer", "number"):
            x = float(v)
            self.n += 1
            self.total += x
            delta = x - self.mean
            self.mean += delta / self.n
            self.m2 += delta * (x - self.mean)
            self.lo = min(self.lo, x)
            self.hi = max(self.hi, x)
        key = _category_key(v)
        if key is not None:
            self.cat_count += 1
            if self.cats is not None:
                self.cats[key] += 1
                if len(self.cats) > MAX_TRACKED_CATEGORIES:
                    self.cats = None

    def to_json(self) -> dict[str, Any]:
        opp = self.opportunities
        out: dict[str, Any] = {
            "missing_rate": (self.missing / opp) if opp else 0.0,
            "type_counts": dict(self.type_counts),
        }
        if self.n:
            var = self.m2 / (self.n - 1) if self.n > 1 else 0.0
            out["numeric"] = {
                "count": self.n,
                "mean": self.total / self.n,
                "std": math.sqrt(max(var, 0.0)),
                "min": self.lo,
                "max": self.hi,
            }
        if self.cat_count:
            cat: dict[str, Any] = {"count": self.cat_count, "truncated": self.cats is None}
            if self.cats is not None:
                cat["values"] = dict(self.cats)
            out["categorical"] = cat
        if self.text_n:
            out["text"] = {
                "count": self.text_n,
                "chars": {"mean": self.chars_sum / self.text_n, "hist": dict(self.chars_hist)},
                "tokens": {"mean": self.tokens_sum / self.text_n, "hist": dict(self.tokens_hist)},
            }
        if self.langs is not None:
            out["language"] = {"count": sum(self.langs.values()), "values": dict(self.langs)}
        if self.emb_sum is not None or self.emb_skipped:
            emb: dict[str, Any] = {"count": self.emb_n, "skipped": self.emb_skipped}
            if self.emb_sum is not None and self.emb_n:
                emb["dims"] = len(self.emb_sum)
                emb["centroid"] = [x / self.emb_n for x in self.emb_sum]
            out["embedding"] = emb
        return out


def _declared_paths(schema: Any) -> tuple[dict[str, list[str]], set[str]]:
    """Paths a schema declares: object keys per parent path, and array paths with items.

    Follows ``properties``, ``items``/``prefixItems``, combinator branches and
    local ``$ref`` (each schema node once per path, so recursive schemas stop).
    """
    children: dict[str, list[str]] = {}
    arrays: set[str] = set()
    seen: set[tuple[int, str]] = set()

    def walk(node: Any, path: str, depth: int) -> None:
        if not isinstance(node, dict) or depth > MAX_INFER_DEPTH:
            return
        key = (id(node), path)
        if key in seen:
            return
        seen.add(key)
        if "$ref" in node:
            walk(resolve_ref(schema, node["$ref"]), path, depth)
        for k, sub in (node.get("properties") or {}).items():
            cp = k if path == "$" else f"{path}.{k}"
            lst = children.setdefault(path, [])
            if k not in lst:
                lst.append(k)
            walk(sub, cp, depth + 1)
        item_schemas: list[Any] = []
        items = node.get("items")
        if isinstance(items, list):
            item_schemas.extend(items)
        elif items is not None:
            item_schemas.append(items)
        item_schemas.extend(node.get("prefixItems") or [])
        if item_schemas:
            arrays.add(path)
            for sub in item_schemas:
                walk(sub, f"{path}[]", depth + 1)
        for kw in ("allOf", "anyOf", "oneOf"):
            for sub in node.get(kw) or []:
                walk(sub, path, depth)
        for kw in ("if", "then", "else"):
            if kw in node:
                walk(node[kw], path, depth)

    walk(schema, "$", 0)
    return children, arrays


class Profiler:
    """Streaming profile of every path the contract declares (nested and array items).

    For an object key the missing rate is relative to the parent objects seen
    at that position; for array items (``path[]``) every element counts.
    """

    def __init__(
        self,
        contract: Any,
        *,
        tokenizer: str = WHITESPACE,
        language_paths: Iterable[str] = (),
        embedding_paths: Iterable[str] = (),
    ) -> None:
        self.contract = load_contract(contract)
        self._children, self._arrays = _declared_paths(self.contract["schema"])
        self._acc: dict[str, _FieldAcc] = {}
        for parent, keys in self._children.items():
            for k in keys:
                self._acc[k if parent == "$" else f"{parent}.{k}"] = _FieldAcc()
        for a in self._arrays:
            self._acc[f"{a}[]"] = _FieldAcc()
        self.language_paths = sorted(set(language_paths))
        self.embedding_paths = sorted(set(embedding_paths))
        for path in self.language_paths + self.embedding_paths:
            if path not in self._acc:
                raise ValueError(f"path {path!r} is not declared by the contract")
        self.tokenizer = tokenizer
        self._tokenize = make_tokenizer(tokenizer)
        self._detect = make_language_detector() if self.language_paths else None
        self._lang = set(self.language_paths)
        self._emb = set(self.embedding_paths)
        self.records = 0

    @property
    def config(self) -> dict[str, Any]:
        return {
            "tokenizer": self.tokenizer,
            "language_paths": self.language_paths,
            "embedding_paths": self.embedding_paths,
        }

    @classmethod
    def like(cls, contract: Any, baseline: Profile) -> Profiler:
        """A profiler with the same text/language/embedding settings as ``baseline``."""
        cfg = baseline.config
        return cls(
            contract,
            tokenizer=str(cfg.get("tokenizer") or WHITESPACE),
            language_paths=list(cfg.get("language_paths") or []),
            embedding_paths=list(cfg.get("embedding_paths") or []),
        )

    def _observe(self, acc: _FieldAcc, path: str, v: Any) -> None:
        acc.observe(v)
        if isinstance(v, str):
            acc.observe_text(v, self._tokenize, self._detect if path in self._lang else None)
        if path in self._emb:
            acc.observe_vector(v)

    def add(self, record: Any) -> None:
        self.records += 1
        self._walk(record, "$")

    def _walk(self, v: Any, path: str) -> None:
        if isinstance(v, dict):
            for k in self._children.get(path, ()):
                cp = k if path == "$" else f"{path}.{k}"
                acc = self._acc[cp]
                acc.opportunities += 1
                if k not in v:
                    acc.missing += 1
                    continue
                self._observe(acc, cp, v[k])
                self._walk(v[k], cp)
        elif isinstance(v, list) and path in self._arrays:
            ip = f"{path}[]"
            acc = self._acc[ip]
            for elem in v:
                acc.opportunities += 1
                self._observe(acc, ip, elem)
                self._walk(elem, ip)

    def profile(self) -> Profile:
        stats = {p: a.to_json() for p, a in sorted(self._acc.items())}
        return Profile(
            version=PROFILE_VERSION, field_stats=stats, records=self.records, config=self.config
        )


def profile_records(
    *,
    contract: Any,
    records: Iterable[Any],
    tokenizer: str = WHITESPACE,
    language_paths: Iterable[str] = (),
    embedding_paths: Iterable[str] = (),
) -> Profile:
    """Compute a statistical profile of records for drift detection.

    For each path the contract declares (top-level keys, nested keys such as
    ``meta.source``, and array items such as ``messages[].role``): missing
    rate, JSON type counts, numeric count/mean/std/min/max, and value counts
    for string and boolean values (``categorical``). A path with more than
    ``MAX_TRACKED_CATEGORIES`` distinct values is marked ``truncated`` and its
    value counts are not stored.
    """
    p = Profiler(
        contract,
        tokenizer=tokenizer,
        language_paths=language_paths,
        embedding_paths=embedding_paths,
    )
    for rec in records:
        p.add(rec)
    return p.profile()


# --------------------------------------------------------------------------- #
# Drift
# --------------------------------------------------------------------------- #


def population_stability_index(expected: dict[str, float], actual: dict[str, float]) -> float:
    """Population Stability Index between two categorical distributions.

    ``PSI = sum((a - e) * ln(a / e))`` over the union of buckets, where ``e``
    and ``a`` are the expected (baseline) and actual (current) proportions.
    Proportions are floored at 1e-4 so an empty bucket does not divide by zero.
    Rule of thumb: below 0.1 is stable, 0.1 to 0.25 is a moderate shift, and
    above 0.25 is a significant shift.
    """
    psi = 0.0
    for key in set(expected) | set(actual):
        e = max(float(expected.get(key, 0.0)), _PSI_EPSILON)
        a = max(float(actual.get(key, 0.0)), _PSI_EPSILON)
        psi += (a - e) * math.log(a / e)
    return psi


def _null_rate(type_counts: Any) -> float | None:
    """Fraction of present values that are null, or None if nothing was present."""
    if not isinstance(type_counts, dict):
        return None
    present = sum(int(n) for n in type_counts.values())
    if present <= 0:
        return None
    return float(type_counts.get("null", 0)) / float(present)


def _categorical_issue(
    fname: str, b_cat: Any, c_cat: Any, max_psi: float
) -> ValidationIssue | None:
    """Compare the categorical blocks of a baseline and current field profile."""
    if not isinstance(b_cat, dict) or not isinstance(c_cat, dict):
        return None
    b_values = b_cat.get("values")
    if b_cat.get("truncated") or not isinstance(b_values, dict):
        return None  # high-cardinality baseline: no categorical check
    b_total = sum(int(n) for n in b_values.values())
    c_total = int(c_cat.get("count") or 0)
    if b_total <= 0 or c_total <= 0:
        return None
    if c_cat.get("truncated"):
        return ValidationIssue(
            kind="drift_categorical",
            field=fname,
            message=f"distinct_values>{MAX_TRACKED_CATEGORIES} (baseline had {len(b_values)})",
            count=1,
        )
    c_values = c_cat.get("values") or {}
    expected = {str(k): int(n) / b_total for k, n in b_values.items()}
    actual: dict[str, float] = {}
    unseen = 0
    for k, n in c_values.items():
        if k in expected:
            actual[k] = int(n) / c_total
        else:
            unseen += int(n)
    # Values the baseline never saw share one "unseen" bucket (baseline share 0).
    if unseen:
        actual["\x00unseen"] = unseen / c_total
    psi = population_stability_index(expected, actual)
    if psi > max_psi:
        return ValidationIssue(
            kind="drift_categorical",
            field=fname,
            message=f"psi={psi:.3f} exceeds {max_psi:.3f}",
            count=1,
        )
    return None


def drift_check(
    *,
    baseline: Profile,
    current: Profile,
    max_missing_rate: float = 0.01,
    max_mean_shift_sigma: float = 3.0,
    max_null_rate_increase: float = 0.10,
    max_psi: float = 0.25,
    max_length_psi: float = 0.25,
    max_centroid_distance: float = 0.2,
    centroid_metric: str = "euclidean",
) -> list[ValidationIssue]:
    """Compare current profile against a baseline to detect data drift.

    Signals, per baseline path (top-level, nested and array-item paths):

    - ``drift_missing_rate``: the path's missing rate is above
      ``max_missing_rate`` and higher than the baseline's.
    - ``drift_mean_shift``: the numeric mean moved more than
      ``max_mean_shift_sigma`` baseline standard deviations. This is a
      heuristic, not a statistical test: it does not scale with batch size.
    - ``drift_null_rate``: the share of present values that are null rose by
      more than ``max_null_rate_increase`` (absolute, e.g. 0.10 = 10 points).
    - ``drift_categorical``: for string/boolean values, the Population
      Stability Index between the baseline and current value distributions is
      above ``max_psi`` (0.25 is the common "significant shift" threshold).
      Values the baseline never saw are pooled into one bucket. Paths with
      more than ``MAX_TRACKED_CATEGORIES`` distinct baseline values are
      skipped; if the baseline was within that limit and the current batch is
      above it, that is reported as drift.

    - ``drift_text_length`` / ``drift_token_count``: PSI between the
      power-of-two histograms of string lengths (characters) or token counts
      is above ``max_length_psi``. Both profiles must use the same tokenizer.
    - ``drift_language``: PSI between detected-language distributions (paths
      profiled with language detection) is above ``max_psi``.
    - ``drift_embedding_centroid``: the distance (``centroid_metric``:
      ``euclidean`` or ``cosine``) between the baseline and current mean
      embedding is above ``max_centroid_distance``, or the dimension changed.

    Keys that the contract does not declare are not profiled, so they are not
    checked here; use ``additionalProperties: false`` to reject them.

    Returns:
        List of ValidationIssue instances describing detected drift. Empty means no drift.
    """
    issues: list[ValidationIssue] = []
    b_tok = str(baseline.config.get("tokenizer") or WHITESPACE)
    c_tok = str(current.config.get("tokenizer") or WHITESPACE)
    if b_tok != c_tok:
        raise ValueError(f"tokenizer mismatch: baseline {b_tok!r}, current {c_tok!r}")
    if centroid_metric not in CENTROID_METRICS:
        raise ValueError(f"unknown centroid metric {centroid_metric!r}")

    for fname, b in baseline.field_stats.items():
        c = current.field_stats.get(fname) or {}

        b_missing = float(b.get("missing_rate") or 0.0)
        c_missing = float(c.get("missing_rate") or 0.0)
        if c_missing > max_missing_rate and c_missing > b_missing:
            issues.append(
                ValidationIssue(
                    kind="drift_missing_rate",
                    field=fname,
                    message=f"missing_rate={c_missing:.4f} exceeds {max_missing_rate:.4f}",
                    count=1,
                )
            )

        b_null = _null_rate(b.get("type_counts"))
        c_null = _null_rate(c.get("type_counts"))
        if b_null is not None and c_null is not None and c_null - b_null > max_null_rate_increase:
            issues.append(
                ValidationIssue(
                    kind="drift_null_rate",
                    field=fname,
                    message=(
                        f"null_rate={c_null:.4f} rose from {b_null:.4f} "
                        f"by more than {max_null_rate_increase:.4f}"
                    ),
                    count=1,
                )
            )

        b_num = b.get("numeric")
        c_num = c.get("numeric")
        if isinstance(b_num, dict) and isinstance(c_num, dict):
            b_mean = float(b_num.get("mean") or 0.0)
            c_mean = float(c_num.get("mean") or 0.0)
            b_std = float(b_num.get("std") or 0.0)
            if b_std > 0:
                sigma = abs(c_mean - b_mean) / b_std
                if sigma > max_mean_shift_sigma:
                    issues.append(
                        ValidationIssue(
                            kind="drift_mean_shift",
                            field=fname,
                            message=(
                                f"mean_shift_sigma={sigma:.2f} exceeds {max_mean_shift_sigma:.2f}"
                            ),
                            count=1,
                        )
                    )

        cat_issue = _categorical_issue(fname, b.get("categorical"), c.get("categorical"), max_psi)
        if cat_issue is not None:
            issues.append(cat_issue)

        issues.extend(_text_issues(fname, b.get("text"), c.get("text"), max_length_psi))
        lang_issue = _distribution_issue(
            "drift_language", fname, b.get("language"), c.get("language"), max_psi
        )
        if lang_issue is not None:
            issues.append(lang_issue)
        emb_issue = _embedding_issue(
            fname, b.get("embedding"), c.get("embedding"), max_centroid_distance, centroid_metric
        )
        if emb_issue is not None:
            issues.append(emb_issue)

    return issues


def _shares(counts: dict[str, Any]) -> dict[str, float]:
    total = sum(int(n) for n in counts.values())
    return {str(k): int(n) / total for k, n in counts.items()} if total > 0 else {}


def _distribution_issue(
    kind: str, fname: str, b: Any, c: Any, threshold: float, extra: str = ""
) -> ValidationIssue | None:
    """PSI between two ``{"values"|"hist": counts}`` blocks."""
    if not isinstance(b, dict) or not isinstance(c, dict):
        return None
    key = "values" if "values" in b else "hist"
    expected, actual = _shares(b.get(key) or {}), _shares(c.get(key) or {})
    if not expected or not actual:
        return None
    psi = population_stability_index(expected, actual)
    if psi > threshold:
        return ValidationIssue(
            kind=kind, field=fname, message=f"psi={psi:.3f} exceeds {threshold:.3f}{extra}", count=1
        )
    return None


def _text_issues(fname: str, b: Any, c: Any, threshold: float) -> list[ValidationIssue]:
    if not isinstance(b, dict) or not isinstance(c, dict):
        return []
    out = []
    for kind, part in (("drift_text_length", "chars"), ("drift_token_count", "tokens")):
        bp, cp = b.get(part), c.get(part)
        if not isinstance(bp, dict) or not isinstance(cp, dict):
            continue
        extra = f" (mean {float(bp.get('mean') or 0):.1f} -> {float(cp.get('mean') or 0):.1f})"
        issue = _distribution_issue(kind, fname, bp, cp, threshold, extra)
        if issue is not None:
            out.append(issue)
    return out


def _embedding_issue(
    fname: str, b: Any, c: Any, threshold: float, metric: str
) -> ValidationIssue | None:
    if not isinstance(b, dict) or not isinstance(c, dict):
        return None
    bc, cc = b.get("centroid"), c.get("centroid")
    if not isinstance(bc, list) or not isinstance(cc, list):
        return None
    if len(bc) != len(cc):
        return ValidationIssue(
            kind="drift_embedding_centroid",
            field=fname,
            message=f"dimensions {len(bc)} -> {len(cc)}",
            count=1,
        )
    d = CENTROID_METRICS[metric]([float(x) for x in bc], [float(x) for x in cc])
    if d > threshold:
        return ValidationIssue(
            kind="drift_embedding_centroid",
            field=fname,
            message=f"{metric}={d:.4f} exceeds {threshold:.4f}",
            count=1,
        )
    return None
