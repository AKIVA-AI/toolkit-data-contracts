"""Categorical-distribution drift (PSI) and null-rate drift."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.contract import (
    MAX_TRACKED_CATEGORIES,
    Profile,
    drift_check,
    infer_contract,
    population_stability_index,
    profile_records,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _drift(baseline_rows, current_rows, **kwargs):
    contract = infer_contract(baseline_rows + current_rows)
    baseline = profile_records(contract=contract, records=baseline_rows)
    current = profile_records(contract=contract, records=current_rows)
    return drift_check(baseline=baseline, current=current, **kwargs)


def _kinds(issues):
    return [(i.kind, i.field) for i in issues]


class TestPopulationStabilityIndex:
    def test_identical_distributions_score_zero(self):
        assert population_stability_index({"a": 0.5, "b": 0.5}, {"a": 0.5, "b": 0.5}) == 0.0

    def test_small_shift_is_small(self):
        psi = population_stability_index({"a": 0.5, "b": 0.5}, {"a": 0.55, "b": 0.45})
        assert 0 < psi < 0.05

    def test_disjoint_distributions_score_high(self):
        psi = population_stability_index({"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0})
        assert psi > 5


class TestCategoricalProfile:
    def test_profile_records_value_counts_for_strings(self):
        contract = infer_contract([{"c": "US"}])
        prof = profile_records(contract=contract, records=[{"c": "US"}, {"c": "CA"}, {"c": "US"}])
        cat = prof.field_stats["c"]["categorical"]
        assert cat == {"count": 3, "truncated": False, "values": {"US": 2, "CA": 1}}

    def test_profile_records_value_counts_for_booleans(self):
        contract = infer_contract([{"b": True}])
        prof = profile_records(contract=contract, records=[{"b": True}, {"b": False}])
        assert prof.field_stats["b"]["categorical"]["values"] == {"true": 1, "false": 1}

    def test_high_cardinality_is_truncated(self):
        rows = [{"id": f"u{i}"} for i in range(MAX_TRACKED_CATEGORIES + 1)]
        prof = profile_records(contract=infer_contract(rows), records=rows)
        cat = prof.field_stats["id"]["categorical"]
        assert cat["truncated"] is True
        assert "values" not in cat

    def test_numeric_field_has_no_categorical_block(self):
        rows = [{"x": 1}, {"x": 2}]
        prof = profile_records(contract=infer_contract(rows), records=rows)
        assert "categorical" not in prof.field_stats["x"]


class TestCategoricalDrift:
    def test_all_new_category_is_drift(self):
        """Verdict probe: baseline country in {US, CA}, batch is 100% CN."""
        baseline = [{"country": "US"}] * 50 + [{"country": "CA"}] * 50
        current = [{"country": "CN"}] * 100
        assert ("drift_categorical", "country") in _kinds(_drift(baseline, current))

    def test_same_distribution_is_not_drift(self):
        baseline = [{"country": "US"}] * 50 + [{"country": "CA"}] * 50
        current = [{"country": "CA"}] * 50 + [{"country": "US"}] * 50
        assert _drift(baseline, current) == []

    def test_small_wobble_is_not_drift(self):
        baseline = [{"country": "US"}] * 50 + [{"country": "CA"}] * 50
        current = [{"country": "US"}] * 55 + [{"country": "CA"}] * 45
        assert _drift(baseline, current) == []

    def test_proportion_swing_is_drift(self):
        baseline = [{"tier": "free"}] * 90 + [{"tier": "paid"}] * 10
        current = [{"tier": "free"}] * 20 + [{"tier": "paid"}] * 80
        assert ("drift_categorical", "tier") in _kinds(_drift(baseline, current))

    def test_boolean_flip_is_drift(self):
        baseline = [{"flag": True}] * 50 + [{"flag": False}] * 50
        current = [{"flag": True}] * 100
        assert ("drift_categorical", "flag") in _kinds(_drift(baseline, current))

    def test_threshold_is_configurable(self):
        baseline = [{"tier": "free"}] * 90 + [{"tier": "paid"}] * 10
        current = [{"tier": "free"}] * 20 + [{"tier": "paid"}] * 80
        assert _drift(baseline, current, max_psi=100.0) == []

    def test_high_cardinality_baseline_is_skipped(self):
        baseline = [{"id": f"a{i}"} for i in range(200)]
        current = [{"id": f"b{i}"} for i in range(200)]
        assert _drift(baseline, current) == []

    def test_low_cardinality_baseline_exploding_is_drift(self):
        """Fail closed: current batch has too many distinct values to compare."""
        baseline = [{"status": "ok"}] * 50 + [{"status": "err"}] * 50
        current = [{"status": f"s{i}"} for i in range(MAX_TRACKED_CATEGORIES + 10)]
        assert ("drift_categorical", "status") in _kinds(_drift(baseline, current))

    def test_profile_without_categorical_block_is_tolerated(self):
        """Baselines written before categorical profiling do not crash."""
        old = Profile(version=1, field_stats={"c": {"missing_rate": 0.0, "type_counts": {}}})
        new = Profile(
            version=1,
            field_stats={
                "c": {
                    "missing_rate": 0.0,
                    "type_counts": {"string": 1},
                    "categorical": {"count": 1, "truncated": False, "values": {"x": 1}},
                }
            },
        )
        assert drift_check(baseline=old, current=new) == []


class TestNullRateDrift:
    def test_column_going_all_null_is_drift(self):
        """Verdict probe: baseline with some nulls, batch 100% null."""
        baseline = [{"v": 1.0}] * 90 + [{"v": None}] * 10
        current = [{"v": None}] * 100
        assert ("drift_null_rate", "v") in _kinds(_drift(baseline, current))

    def test_null_only_string_column_is_drift(self):
        baseline = [{"s": "a"}] * 100
        current = [{"s": None}] * 100
        assert ("drift_null_rate", "s") in _kinds(_drift(baseline, current))

    def test_small_null_increase_is_not_drift(self):
        baseline = [{"v": 1.0}] * 90 + [{"v": None}] * 10
        current = [{"v": 1.0}] * 85 + [{"v": None}] * 15
        assert _drift(baseline, current) == []

    def test_null_decrease_is_not_drift(self):
        baseline = [{"v": 1.0}] * 50 + [{"v": None}] * 50
        current = [{"v": 1.0}] * 100
        assert _drift(baseline, current) == []

    def test_null_threshold_is_configurable(self):
        baseline = [{"v": 1.0}] * 90 + [{"v": None}] * 10
        current = [{"v": 1.0}] * 85 + [{"v": None}] * 15
        issues = _drift(baseline, current, max_null_rate_increase=0.01)
        assert ("drift_null_rate", "v") in _kinds(issues)


class TestCliCategoricalAndNullDrift:
    def _run(self, tmp_path: Path, baseline_rows, current_rows, extra=()):
        base = tmp_path / "base.jsonl"
        cur = tmp_path / "cur.jsonl"
        _write_jsonl(base, baseline_rows)
        _write_jsonl(cur, current_rows)
        contract = tmp_path / "contract.json"
        profile = tmp_path / "base.profile.json"
        report = tmp_path / "report.json"
        assert main(["infer", "--input", str(base), "--out", str(contract)]) == EXIT_SUCCESS
        assert (
            main(
                [
                    "profile",
                    "--input",
                    str(base),
                    "--contract",
                    str(contract),
                    "--out",
                    str(profile),
                ]
            )
            == EXIT_SUCCESS
        )
        code = main(
            [
                "check",
                "--input",
                str(cur),
                "--contract",
                str(contract),
                "--baseline",
                str(profile),
                "--out",
                str(report),
                *extra,
            ]
        )
        return code, json.loads(report.read_text(encoding="utf-8"))

    def test_categorical_shift_fails_check(self, tmp_path: Path):
        base = [{"country": "US"}] * 50 + [{"country": "CA"}] * 50
        cur = [{"country": "US"}] * 5 + [{"country": "CA"}] * 95
        code, report = self._run(tmp_path, base, cur)
        assert code == EXIT_CHECK_FAILED
        drift = report["predicate"]["details"]["drift_issues"]
        assert [d["kind"] for d in drift] == ["drift_categorical"]

    def test_max_psi_flag(self, tmp_path: Path):
        base = [{"country": "US"}] * 50 + [{"country": "CA"}] * 50
        cur = [{"country": "US"}] * 5 + [{"country": "CA"}] * 95
        code, report = self._run(tmp_path, base, cur, extra=["--max-psi", "50"])
        assert code == EXIT_SUCCESS

    def test_null_shift_fails_check(self, tmp_path: Path):
        base = [{"v": 1}] * 90 + [{"v": None}] * 10
        cur = [{"v": None}] * 100
        code, report = self._run(tmp_path, base, cur)
        assert code == EXIT_CHECK_FAILED
        drift = report["predicate"]["details"]["drift_issues"]
        assert "drift_null_rate" in [d["kind"] for d in drift]

    def test_max_null_increase_flag(self, tmp_path: Path):
        base = [{"v": 1}] * 90 + [{"v": None}] * 10
        cur = [{"v": 1}] * 70 + [{"v": None}] * 30
        code, _ = self._run(tmp_path, base, cur, extra=["--max-null-increase", "0.5"])
        assert code == EXIT_SUCCESS
