"""Text length, token count, language and embedding-centroid drift.

References used below:
- PSI equals the Jeffreys divergence KL(a||e) + KL(e||a); checked against
  scipy.stats.entropy (reference KL implementation).
- tiktoken: OpenAI Cookbook, "How to count tokens with tiktoken":
  "tiktoken is great!" is 6 tokens in cl100k_base.
- langdetect README: detect("War doesn't show who's right, just who's left.") == "en".
- Centroid distances: numpy.linalg.norm and scipy.spatial.distance.cosine.
  The mean-embedding distance method (default threshold 0.2) follows
  Evidently's embedding drift "distance" method.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.distance import cosine as scipy_cosine
from scipy.stats import entropy

from toolkit_data_contracts_drift.cli import EXIT_CHECK_FAILED, EXIT_CLI_ERROR, EXIT_SUCCESS, main
from toolkit_data_contracts_drift.contract import (
    Profiler,
    drift_check,
    infer_contract,
    population_stability_index,
    profile_records,
)
from toolkit_data_contracts_drift.text import (
    cosine_distance,
    euclidean,
    length_bin,
    make_language_detector,
    make_tokenizer,
)


def _drift(base, cur, **kw):
    contract = infer_contract(base)
    opts = {k: kw.pop(k) for k in ("tokenizer", "language_paths", "embedding_paths") if k in kw}
    return [
        (d.kind, d.field)
        for d in drift_check(
            baseline=profile_records(contract=contract, records=base, **opts),
            current=profile_records(contract=contract, records=cur, **opts),
            **kw,
        )
    ]


class TestReferences:
    def test_psi_is_jeffreys_divergence(self):
        rng = random.Random(5)
        for _ in range(50):
            k = rng.randint(2, 8)
            e = np.array([rng.random() + 0.01 for _ in range(k)])
            a = np.array([rng.random() + 0.01 for _ in range(k)])
            e, a = e / e.sum(), a / a.sum()
            ours = population_stability_index(
                {str(i): float(x) for i, x in enumerate(e)},
                {str(i): float(x) for i, x in enumerate(a)},
            )
            assert ours == pytest.approx(entropy(a, e) + entropy(e, a), rel=1e-9)

    def test_length_bins_are_floor_log2_plus_one(self):
        assert length_bin(0) == "0"
        for n in range(1, 5000):
            assert length_bin(n) == str(math.floor(math.log2(n)) + 1)

    def test_whitespace_tokens(self):
        tok = make_tokenizer("whitespace")
        assert tok("  Hello,\tworld \n again ") == 3
        assert tok("") == 0

    def test_tiktoken_cookbook_example(self):
        pytest.importorskip("tiktoken")
        assert make_tokenizer("tiktoken:cl100k_base")("tiktoken is great!") == 6

    def test_langdetect_readme_example(self):
        detect = make_language_detector()
        assert detect("War doesn't show who's right, just who's left.") == "en"
        assert detect("Ein, zwei, drei, vier") == "und"  # below 20 non-space characters

    def test_centroid_distances_match_numpy_and_scipy(self):
        rng = random.Random(9)
        for _ in range(20):
            a = [rng.gauss(0, 1) for _ in range(16)]
            b = [rng.gauss(0, 1) for _ in range(16)]
            assert euclidean(a, b) == pytest.approx(float(np.linalg.norm(np.subtract(a, b))))
            assert cosine_distance(a, b) == pytest.approx(float(scipy_cosine(a, b)))

    def test_unknown_tokenizer(self):
        with pytest.raises(ValueError, match="unknown tokenizer"):
            make_tokenizer("bpe")


SHORT = [{"answer": "Yes."}, {"answer": "No, sorry."}, {"answer": "Sure thing."}] * 20
LONG = [{"answer": " ".join(["This answer rambles on at length."] * 12)}] * 60


class TestTextDrift:
    def test_profile_records_text_stats(self):
        prof = profile_records(contract=infer_contract(SHORT), records=SHORT)
        text = prof.field_stats["answer"]["text"]
        assert text["count"] == 60
        assert text["chars"]["mean"] == pytest.approx((4 + 10 + 11) / 3)
        assert text["tokens"]["mean"] == pytest.approx((1 + 2 + 2) / 3)
        assert text["chars"]["hist"] == {"3": 20, "4": 40}
        assert prof.config["tokenizer"] == "whitespace"

    def test_longer_answers_drift(self):
        # The answers are also a low-cardinality category, so PSI flags them too.
        assert set(_drift(SHORT, LONG)) == {
            ("drift_text_length", "answer"),
            ("drift_token_count", "answer"),
            ("drift_categorical", "answer"),
        }

    def test_same_lengths_do_not_drift(self):
        assert _drift(SHORT, list(reversed(SHORT))) == []

    def test_threshold(self):
        assert _drift(SHORT, LONG, max_length_psi=1000) == [("drift_categorical", "answer")]

    def test_tokenizer_mismatch_is_an_error(self):
        pytest.importorskip("tiktoken")
        contract = infer_contract(SHORT)
        with pytest.raises(ValueError, match="tokenizer mismatch"):
            drift_check(
                baseline=profile_records(contract=contract, records=SHORT),
                current=profile_records(
                    contract=contract, records=SHORT, tokenizer="tiktoken:cl100k_base"
                ),
            )


EN = [
    {"t": "The weather today is sunny with a light breeze from the west."},
    {"t": "Please remember to submit your report before the end of the week."},
]
FR = [
    {"t": "Le temps aujourd'hui est ensoleillé avec une légère brise de l'ouest."},
    {"t": "N'oubliez pas de rendre votre rapport avant la fin de la semaine."},
]


class TestLanguageDrift:
    def test_language_shift(self):
        shifted = _drift(EN * 10, FR * 10, language_paths=["t"], max_length_psi=1000)
        assert ("drift_language", "t") in shifted
        assert _drift(EN * 10, FR * 10, max_length_psi=1000) == [("drift_categorical", "t")]
        prof = profile_records(contract=infer_contract(EN), records=EN * 3, language_paths=["t"])
        assert prof.field_stats["t"]["language"] == {"count": 6, "values": {"en": 6}}

    def test_no_language_block_without_opt_in(self):
        prof = profile_records(contract=infer_contract(EN), records=EN)
        assert "language" not in prof.field_stats["t"]

    def test_undeclared_path_rejected(self):
        with pytest.raises(ValueError, match="not declared"):
            Profiler(infer_contract(EN), language_paths=["nope"])


def _vectors(center: list[float], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    return [{"embedding": [c + rng.gauss(0, 0.05) for c in center]} for _ in range(n)]


class TestEmbeddingDrift:
    def test_centroid_shift(self):
        base = _vectors([1.0, 0.0, 0.0, 0.0], 50, 1)
        same = _vectors([1.0, 0.0, 0.0, 0.0], 50, 2)
        moved = _vectors([0.0, 1.0, 0.0, 0.0], 50, 3)
        assert _drift(base, same, embedding_paths=["embedding"]) == []
        assert _drift(base, moved, embedding_paths=["embedding"]) == [
            ("drift_embedding_centroid", "embedding")
        ]
        assert _drift(base, moved, embedding_paths=["embedding"], centroid_metric="cosine") == [
            ("drift_embedding_centroid", "embedding")
        ]

    def test_centroid_is_the_mean_vector(self):
        rows = [{"embedding": [1, 2]}, {"embedding": [3, 4]}, {"embedding": [1]}]
        prof = profile_records(
            contract=infer_contract(rows), records=rows, embedding_paths=["embedding"]
        )
        assert prof.field_stats["embedding"]["embedding"] == {
            "count": 2,
            "skipped": 1,
            "dims": 2,
            "centroid": [2.0, 3.0],
        }

    def test_dimension_change(self):
        base = _vectors([1.0, 0.0], 5, 1)
        cur = _vectors([1.0, 0.0, 0.0], 5, 2)
        assert _drift(base, cur, embedding_paths=["embedding"]) == [
            ("drift_embedding_centroid", "embedding")
        ]


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


class TestCli:
    def test_profile_options_carry_into_check(self, tmp_path: Path):
        base = _jsonl(
            tmp_path / "base.jsonl",
            [
                {"id": f"c{i}", "text": "short chunk text", **v}
                for i, v in enumerate(_vectors([1.0, 0.0, 0.0], 30, 1))
            ],
        )
        cur = _jsonl(
            tmp_path / "cur.jsonl",
            [
                {"id": f"c{i}", "text": "short chunk text", **v}
                for i, v in enumerate(_vectors([0.0, 0.0, 1.0], 30, 2))
            ],
        )
        prof, out = tmp_path / "p.json", tmp_path / "r.json"
        args = [
            "profile",
            "--input",
            str(base),
            "--preset",
            "rag-chunks",
            "--out",
            str(prof),
            "--embedding",
            "embedding",
        ]
        assert main(args) == EXIT_SUCCESS
        cfg = json.loads(prof.read_text(encoding="utf-8"))["config"]
        assert cfg == {
            "tokenizer": "whitespace",
            "language_paths": [],
            "embedding_paths": ["embedding"],
        }
        check = [
            "check",
            "--input",
            str(cur),
            "--preset",
            "rag-chunks",
            "--baseline",
            str(prof),
            "--out",
            str(out),
        ]
        assert main(check) == EXIT_CHECK_FAILED
        drift = json.loads(out.read_text(encoding="utf-8"))["predicate"]["details"]["drift_issues"]
        assert [(d["kind"], d["field"]) for d in drift] == [
            ("drift_embedding_centroid", "embedding")
        ]
        assert main([*check[:-2], "--max-centroid-distance", "5"]) == EXIT_SUCCESS

    def test_unknown_embedding_path_is_cli_error(self, tmp_path: Path):
        data = _jsonl(tmp_path / "d.jsonl", [{"id": "a", "text": "x"}])
        args = [
            "profile",
            "--input",
            str(data),
            "--preset",
            "rag-chunks",
            "--out",
            str(tmp_path / "p.json"),
            "--embedding",
            "vector",
        ]
        assert main(args) == EXIT_CLI_ERROR
