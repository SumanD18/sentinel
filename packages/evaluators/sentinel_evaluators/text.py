"""Small, dependency-free text utilities shared by the heuristic evaluators."""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z0-9']+")


def tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity in [0, 1]."""
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cosine_bow(a: str, b: str) -> float:
    """Bag-of-words cosine similarity in [0, 1]. A cheap, model-free proxy for
    semantic overlap - good enough for drift alerts, not for ranking."""
    ca, cb = Counter(tokenize(a)), Counter(tokenize(b))
    if not ca or not cb:
        return 0.0
    common = set(ca) & set(cb)
    dot = sum(ca[t] * cb[t] for t in common)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def repetition_ratio(text: str) -> float:
    """Fraction of tokens that are repeats of an earlier token. High values flag
    degenerate / looping output."""
    toks = tokenize(text)
    if len(toks) < 4:
        return 0.0
    unique = len(set(toks))
    return 1.0 - (unique / len(toks))
