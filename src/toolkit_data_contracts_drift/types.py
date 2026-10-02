from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from .schema import json_type as _json_type

JsonScalarType = Literal["null", "boolean", "integer", "number", "string", "object", "array"]


class Contract(TypedDict):
    """A version 2 contract: a draft 2020-12 JSON Schema for one record."""

    version: int
    schema: dict[str, Any]


class _FieldContractBase(TypedDict):
    types: list[JsonScalarType]
    required: bool


class FieldContract(_FieldContractBase, total=False):
    """One field of a version 1 contract (still accepted on load)."""

    properties: dict[str, FieldContract]


class LegacyContract(TypedDict):
    """A version 1 contract: flat ``fields`` map (still accepted on load)."""

    version: int
    allow_extra_fields: bool
    fields: dict[str, FieldContract]


@dataclass(frozen=True)
class ValidationIssue:
    kind: str
    field: str
    message: str
    count: int = 1


def json_type(value: Any) -> JsonScalarType:
    """The JSON type name of a parsed JSON value."""
    return _json_type(value)  # type: ignore[return-value]
