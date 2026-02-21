from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

JsonScalarType = Literal["null", "boolean", "integer", "number", "string", "object", "array"]


class FieldContract(TypedDict):
    types: list[JsonScalarType]
    required: bool


class Contract(TypedDict):
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
