from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .types import Contract, FieldContract, JsonScalarType, ValidationIssue, json_type


def infer_contract(
    records: list[dict[str, Any]],
    *,
    allow_extra_fields: bool = True,
) -> Contract:
    field_types: dict[str, set[JsonScalarType]] = defaultdict(set)
    present_counts: Counter[str] = Counter()

    for rec in records:
        for k, v in rec.items():
            present_counts[k] += 1
            field_types[k].add(json_type(v))

    fields: dict[str, FieldContract] = {}
    total = len(records)
    for field, types in field_types.items():
        fields[field] = FieldContract(
            types=sorted(types),
            required=present_counts[field] == total,
        )

    return {"version": 1, "allow_extra_fields": bool(allow_extra_fields), "fields": fields}


@dataclass(frozen=True)
class Profile:
    version: int
    field_stats: dict[str, dict[str, Any]]

    def to_json(self) -> dict[str, Any]:
        return {"version": int(self.version), "field_stats": dict(self.field_stats)}

    @staticmethod
    def from_json(obj: Any) -> Profile:
        if not isinstance(obj, dict):
            raise ValueError("profile_not_object")
        version = int(obj.get("version", 0))
        stats = obj.get("field_stats")
        if not isinstance(stats, dict):
            raise ValueError("profile_missing_field_stats")
        return Profile(
            version=version, field_stats={str(k): dict(v) for k, v in stats.items()}
        )


def validate_records(
    *,
    contract: Contract,
    records: list[dict[str, Any]],
) -> list[ValidationIssue]:
    issues: dict[tuple[str, str, str], int] = {}

    allow_extra = bool(contract.get("allow_extra_fields", True))
    fields = contract.get("fields") or {}

    for rec in records:
        # required missing
        for fname, f in fields.items():
            if bool(f.get("required")) and fname not in rec:
                key = ("missing_required", fname, "missing_required")
                issues[key] = issues.get(key, 0) + 1

        # type mismatches and extras
        for k, v in rec.items():
            if k not in fields:
                if not allow_extra:
                    key = ("unexpected_field", k, "unexpected_field")
                    issues[key] = issues.get(key, 0) + 1
                continue
            allowed_types = set(fields[k].get("types") or [])
            actual = json_type(v)
            if actual not in allowed_types:
                key = ("type_mismatch", k, f"type_mismatch:{actual}")
                issues[key] = issues.get(key, 0) + 1

    return [
        ValidationIssue(kind=k[0], field=k[1], message=k[2], count=v)
        for k, v in sorted(issues.items())
    ]


def profile_records(*, contract: Contract, records: list[dict[str, Any]]) -> Profile:
    fields = contract.get("fields") or {}
    total = max(1, len(records))
    stats: dict[str, dict[str, Any]] = {}

    numeric_values: dict[str, list[float]] = defaultdict(list)
    missing_counts: Counter[str] = Counter()
    type_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for rec in records:
        for fname in fields.keys():
            if fname not in rec:
                missing_counts[fname] += 1
                continue
            v = rec.get(fname)
            jt = json_type(v)
            type_counts[fname][jt] += 1
            if jt in {"integer", "number"}:
                numeric_values[fname].append(float(v))  # type: ignore[arg-type]

    for fname in fields.keys():
        miss_rate = float(missing_counts.get(fname, 0)) / float(total)
        types = dict(type_counts.get(fname, Counter()))
        out: dict[str, Any] = {"missing_rate": miss_rate, "type_counts": types}
        nums = numeric_values.get(fname) or []
        if nums:
            mean = sum(nums) / len(nums)
            var = sum((x - mean) ** 2 for x in nums) / max(1, (len(nums) - 1))
            out["numeric"] = {
                "count": len(nums),
                "mean": mean,
                "std": math.sqrt(var),
                "min": min(nums),
                "max": max(nums),
            }
        stats[fname] = out

    return Profile(version=1, field_stats=stats)


def drift_check(
    *,
    baseline: Profile,
    current: Profile,
    max_missing_rate: float = 0.01,
    max_mean_shift_sigma: float = 3.0,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

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

    return issues
