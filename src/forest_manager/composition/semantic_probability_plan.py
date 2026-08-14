from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "lavender": ("lavender", "lavandula"),
    "lily": ("lily", "lillies", "lilium"),
    "flower": ("flower", "flowering", "coneflower"),
    "shrub": ("shrub", "bush"),
    "maple": ("maple", "acer"),
    "alder": ("alder", "alnus"),
}

# Specific plant terms carry more semantic evidence than broad categories.
_TERM_SPECIFICITY: dict[str, float] = {
    "lavender": 3.0,
    "lily": 3.0,
    "maple": 3.0,
    "alder": 3.0,
    "flower": 2.0,
    "shrub": 2.0,
}


@dataclass(frozen=True)
class ProbabilityItem:
    geometry_name: str
    matched_term: str | None
    raw_weight: float
    probability: float


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z]+", text.lower())
    normalized: set[str] = set(raw)
    for token in raw:
        if token.endswith("ies") and len(token) > 3:
            normalized.add(token[:-3] + "y")
        if token.endswith("es") and len(token) > 2:
            normalized.add(token[:-2])
        if token.endswith("s") and len(token) > 1:
            normalized.add(token[:-1])
    return normalized


def observed_terms(text: str) -> list[str]:
    tokens = _tokens(text)
    terms: list[str] = []
    for term, aliases in _TERM_ALIASES.items():
        if any(alias in tokens for alias in aliases):
            terms.append(term)
    return terms


def _geometry_matches_term(geometry_name: str, term: str) -> bool:
    name = geometry_name.lower()
    return any(alias in name for alias in _TERM_ALIASES.get(term, (term,)))


def build_probability_plan(text: str, geometry_names: Iterable[str]) -> dict:
    names = list(geometry_names)
    if not names:
        raise ValueError("Forest geometry list is empty.")

    terms = observed_terms(text)
    items: list[tuple[str, str | None, float]] = []

    for name in names:
        candidates: list[tuple[str, float]] = []
        for term in terms:
            if _geometry_matches_term(name, term):
                candidates.append((term, _TERM_SPECIFICITY.get(term, 1.0)))

        if candidates:
            matched_term, weight = max(candidates, key=lambda item: item[1])
        else:
            matched_term, weight = None, 0.5
        items.append((name, matched_term, weight))

    total = sum(weight for _, _, weight in items)
    if total <= 0.0:
        raise ValueError("Semantic probability weight total is zero.")

    probabilities = [(weight / total) * 100.0 for _, _, weight in items]
    # Make the displayed total exactly 100 after rounding without changing order.
    rounded = [round(value, 4) for value in probabilities]
    rounded[-1] = round(rounded[-1] + (100.0 - sum(rounded)), 4)

    result_items = [
        ProbabilityItem(name, term, weight, probability)
        for (name, term, weight), probability in zip(items, rounded)
    ]

    return {
        "raw_text": text,
        "observed_terms": terms,
        "policy": "semantic_specificity_v1",
        "items": [
            {
                "geometry_name": item.geometry_name,
                "matched_term": item.matched_term,
                "raw_weight": item.raw_weight,
                "probability": item.probability,
            }
            for item in result_items
        ],
        "probabilities": [item.probability for item in result_items],
        "probability_total": round(sum(item.probability for item in result_items), 4),
    }
