"""Tests for drift_check edge cases — Task 3: zero std, missing fields, empty profiles.
Also covers Task 4: json_type() missing branches (dict, list, fallback).
"""

from __future__ import annotations

from toolkit_data_contracts_drift.contract import Profile, drift_check, profile_records
from toolkit_data_contracts_drift.types import json_type

# ============================================================================
# Task 3: drift_check Edge Cases
# ============================================================================


class TestDriftCheckZeroStdDeviation:
    """Test drift_check when baseline has zero standard deviation."""

    def test_zero_std_no_drift_issue(self):
        """When baseline std is 0, mean shift check is skipped (no division by zero)."""
        baseline = Profile(
            version=1,
            field_stats={
                "age": {
                    "missing_rate": 0.0,
                    "type_counts": {"integer": 10},
                    "numeric": {"count": 10, "mean": 5.0, "std": 0.0, "min": 5, "max": 5},
                }
            },
        )
        current = Profile(
            version=1,
            field_stats={
                "age": {
                    "missing_rate": 0.0,
                    "type_counts": {"integer": 10},
                    "numeric": {"count": 10, "mean": 100.0, "std": 0.0, "min": 100, "max": 100},
                }
            },
        )
        # Even though means are very different, std=0 means we skip the sigma check
        issues = drift_check(baseline=baseline, current=current)
        drift_mean_issues = [i for i in issues if i.kind == "drift_mean_shift"]
        assert len(drift_mean_issues) == 0


class TestDriftCheckMissingFields:
    """Test drift_check when fields are missing from current profile."""

    def test_field_in_baseline_not_in_current(self):
        """Field present in baseline but absent from current uses empty dict."""
        baseline = Profile(
            version=1,
            field_stats={
                "age": {"missing_rate": 0.0, "type_counts": {"integer": 10}},
                "name": {"missing_rate": 0.0, "type_counts": {"string": 10}},
            },
        )
        current = Profile(
            version=1,
            field_stats={
                "age": {"missing_rate": 0.0, "type_counts": {"integer": 10}},
                # "name" is missing entirely
            },
        )
        # missing_rate defaults to 0.0 for missing field, which is not > max_missing_rate
        issues = drift_check(baseline=baseline, current=current, max_missing_rate=0.01)
        assert isinstance(issues, list)

    def test_field_missing_with_high_baseline_missing(self):
        """Field missing from current but baseline also has high missing rate."""
        baseline = Profile(
            version=1,
            field_stats={
                "optional": {"missing_rate": 0.5, "type_counts": {"string": 5}},
            },
        )
        current = Profile(
            version=1,
            field_stats={},
        )
        issues = drift_check(baseline=baseline, current=current, max_missing_rate=0.01)
        # current missing_rate=0.0 (default), not > baseline missing_rate=0.5
        missing_issues = [i for i in issues if i.kind == "drift_missing_rate"]
        assert len(missing_issues) == 0


class TestDriftCheckEmptyProfiles:
    """Test drift_check with empty profiles."""

    def test_both_profiles_empty(self):
        """Two empty profiles produce no issues."""
        baseline = Profile(version=1, field_stats={})
        current = Profile(version=1, field_stats={})
        issues = drift_check(baseline=baseline, current=current)
        assert issues == []

    def test_baseline_empty_current_has_fields(self):
        """Empty baseline with non-empty current produces no issues (only iterates baseline)."""
        baseline = Profile(version=1, field_stats={})
        current = Profile(
            version=1,
            field_stats={"new_field": {"missing_rate": 0.0}},
        )
        issues = drift_check(baseline=baseline, current=current)
        assert issues == []


class TestDriftCheckMissingRate:
    """Test drift missing rate detection."""

    def test_missing_rate_exceeds_threshold(self):
        """Detects drift when current missing rate exceeds threshold and baseline."""
        baseline = Profile(
            version=1,
            field_stats={"age": {"missing_rate": 0.0}},
        )
        current = Profile(
            version=1,
            field_stats={"age": {"missing_rate": 0.5}},
        )
        issues = drift_check(baseline=baseline, current=current, max_missing_rate=0.01)
        assert len(issues) == 1
        assert issues[0].kind == "drift_missing_rate"
        assert issues[0].field == "age"

    def test_missing_rate_below_threshold(self):
        """No drift when current missing rate is below threshold."""
        baseline = Profile(
            version=1,
            field_stats={"age": {"missing_rate": 0.0}},
        )
        current = Profile(
            version=1,
            field_stats={"age": {"missing_rate": 0.005}},
        )
        issues = drift_check(baseline=baseline, current=current, max_missing_rate=0.01)
        assert len(issues) == 0


class TestDriftCheckMeanShift:
    """Test drift mean shift detection."""

    def test_mean_shift_detected(self):
        """Detects mean shift when sigma exceeds threshold."""
        baseline = Profile(
            version=1,
            field_stats={
                "age": {
                    "missing_rate": 0.0,
                    "numeric": {"count": 100, "mean": 30.0, "std": 5.0, "min": 0, "max": 100},
                }
            },
        )
        current = Profile(
            version=1,
            field_stats={
                "age": {
                    "missing_rate": 0.0,
                    "numeric": {"count": 100, "mean": 60.0, "std": 5.0, "min": 0, "max": 100},
                }
            },
        )
        issues = drift_check(baseline=baseline, current=current, max_mean_shift_sigma=3.0)
        mean_issues = [i for i in issues if i.kind == "drift_mean_shift"]
        assert len(mean_issues) == 1

    def test_no_numeric_in_current(self):
        """No mean shift issue when current has no numeric stats."""
        baseline = Profile(
            version=1,
            field_stats={
                "age": {
                    "missing_rate": 0.0,
                    "numeric": {"count": 100, "mean": 30.0, "std": 5.0, "min": 0, "max": 100},
                }
            },
        )
        current = Profile(
            version=1,
            field_stats={
                "age": {"missing_rate": 0.0, "type_counts": {"string": 100}},
            },
        )
        issues = drift_check(baseline=baseline, current=current)
        mean_issues = [i for i in issues if i.kind == "drift_mean_shift"]
        assert len(mean_issues) == 0


class TestProfileRecordsEdgeCases:
    """Test profile_records with edge cases."""

    def test_empty_records(self):
        """Profiling empty record list returns profile with zero missing rates."""
        contract = {"version": 1, "fields": {"age": {"types": ["integer"]}}}
        profile = profile_records(contract=contract, records=[])
        assert profile.field_stats["age"]["missing_rate"] == 0.0

    def test_all_missing(self):
        """All records missing a field gives missing_rate = 1.0."""
        contract = {"version": 1, "fields": {"age": {"types": ["integer"]}}}
        records = [{"name": "a"}, {"name": "b"}]
        profile = profile_records(contract=contract, records=records)
        assert profile.field_stats["age"]["missing_rate"] == 1.0

    def test_single_numeric_value(self):
        """Single numeric value: std is 0 (n-1 = 0, uses max(1, 0))."""
        contract = {"version": 1, "fields": {"x": {"types": ["integer"]}}}
        records = [{"x": 42}]
        profile = profile_records(contract=contract, records=records)
        # var = 0 / max(1, 0) = 0, std = 0
        assert profile.field_stats["x"]["numeric"]["std"] == 0.0
        assert profile.field_stats["x"]["numeric"]["mean"] == 42.0


# ============================================================================
# Task 4: json_type() Missing Branches
# ============================================================================


class TestJsonType:
    """Test json_type() for all type branches."""

    def test_null(self):
        assert json_type(None) == "null"

    def test_boolean_true(self):
        assert json_type(True) == "boolean"

    def test_boolean_false(self):
        assert json_type(False) == "boolean"

    def test_integer(self):
        assert json_type(42) == "integer"

    def test_float(self):
        assert json_type(3.14) == "number"

    def test_string(self):
        assert json_type("hello") == "string"

    def test_dict(self):
        """dict maps to 'object'."""
        assert json_type({"key": "value"}) == "object"

    def test_empty_dict(self):
        """Empty dict maps to 'object'."""
        assert json_type({}) == "object"

    def test_list(self):
        """list maps to 'array'."""
        assert json_type([1, 2, 3]) == "array"

    def test_empty_list(self):
        """Empty list maps to 'array'."""
        assert json_type([]) == "array"

    def test_fallback_type(self):
        """Unknown types fall back to 'string'."""
        assert json_type(b"bytes") == "string"
        assert json_type(set()) == "string"
        assert json_type((1, 2)) == "string"
