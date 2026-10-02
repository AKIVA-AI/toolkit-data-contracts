"""Text and embedding statistics for LLM data drift.

- Length and token-count distributions use fixed power-of-two bins
  (``n.bit_length()``: 0, 1, 2-3, 4-7, 8-15, ...), so a profile can be built
  in one streaming pass and two profiles always share bin edges. Drift between
  two histograms is measured with the Population Stability Index.
- Token counts use whitespace splitting by default, or a ``tiktoken``
  encoding (``tiktoken:cl100k_base``; optional extra ``tiktoken``).
- Language distribution uses ``langdetect`` (optional extra ``lang``), seeded
  for deterministic results. Texts shorter than ``MIN_LANGUAGE_CHARS``
  non-space characters count as ``und`` (undetermined).
- Embedding drift compares the centroid (mean vector) of the baseline and
  current embeddings with the Euclidean or cosine distance, following the
  "distance between mean embeddings" method used by Evidently.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

WHITESPACE = "whitespace"
MIN_LANGUAGE_CHARS = 20
UNDETERMINED = "und"


class OptionalDependencyError(ValueError):
    """An optional extra is needed for the requested feature."""


def length_bin(n: int) -> str:
    """Power-of-two bin label for a non-negative count (JSON object keys are strings)."""
    return str(max(0, int(n)).bit_length())


def make_tokenizer(spec: str) -> Callable[[str], int]:
    """Return a token-counting function for ``whitespace`` or ``tiktoken:<encoding>``."""
    if spec == WHITESPACE:
        return lambda s: len(s.split())
    if spec.startswith("tiktoken:"):
        try:
            import tiktoken  # pyright: ignore[reportMissingImports]
        except ImportError as e:
            raise OptionalDependencyError(
                "tiktoken token counts need: pip install 'toolkit-data-contracts[tiktoken]'"
            ) from e
        enc = tiktoken.get_encoding(spec.split(":", 1)[1])
        return lambda s: len(enc.encode(s, disallowed_special=()))
    raise ValueError(f"unknown tokenizer {spec!r}; use 'whitespace' or 'tiktoken:<encoding>'")


def make_language_detector() -> Callable[[str], str]:
    """Return a deterministic ``text -> ISO 639-1 code`` function (``und`` if unknown)."""
    try:
        from langdetect import DetectorFactory, detect  # pyright: ignore[reportMissingImports]
        from langdetect.lang_detect_exception import (  # pyright: ignore[reportMissingImports]
            LangDetectException,
        )
    except ImportError as e:
        raise OptionalDependencyError(
            "language drift needs: pip install 'toolkit-data-contracts[lang]'"
        ) from e
    DetectorFactory.seed = 0

    def _detect(text: str) -> str:
        if len("".join(text.split())) < MIN_LANGUAGE_CHARS:
            return UNDETERMINED
        try:
            return str(detect(text))
        except LangDetectException:
            return UNDETERMINED

    return _detect


def is_vector(v: Any) -> bool:
    return (
        isinstance(v, list)
        and len(v) > 0
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    )


def euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """``1 - cos(a, b)``; 1.0 when either vector is all zeros."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


CENTROID_METRICS: dict[str, Callable[[Sequence[float], Sequence[float]], float]] = {
    "euclidean": euclidean,
    "cosine": cosine_distance,
}
