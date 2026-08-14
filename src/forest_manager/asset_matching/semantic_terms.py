from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


_STOPWORDS = {
    "a", "an", "and", "another", "are", "as", "at", "be", "by", "for",
    "from", "high", "image", "in", "is", "landscape", "low", "medium",
    "of", "or", "plant", "plants", "planting", "short", "some", "term",
    "the", "to", "visible", "with",
    "purple", "white", "green", "yellow", "pink", "red",
}

_CANONICAL = {
    "lillies": "lily",
    "lilies": "lily",
    "trees": "tree",
    "shrubs": "shrub",
    "grasses": "grass",
    "flowers": "flower",
    "maples": "maple",
    "alders": "alder",
}

_SYNONYMS = {
    "maple": ("acer",),
    "alder": ("alnus",),
    "lavender": ("lavandula",),
    "lily": ("lilium",),
    "grass": ("graminaceae", "poaceae"),
    "shrub": ("bush",),
}


def _ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        ch for ch in normalized
        if not unicodedata.combining(ch)
    )


def normalize_token(value: str) -> str:
    value = _ascii_fold(value).casefold()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return _CANONICAL.get(value, value)


def variants_for_term(term: str) -> tuple[str, ...]:
    normalized = normalize_token(term)
    if not normalized:
        return ()

    variants: list[str] = [normalized]
    for candidate in _SYNONYMS.get(normalized, ()):
        candidate_normalized = normalize_token(candidate)
        if candidate_normalized and candidate_normalized not in variants:
            variants.append(candidate_normalized)

    return tuple(variants)


@dataclass(frozen=True)
class SemanticSearchTerms:
    raw_text: str
    terms: tuple[str, ...]
    query_variants: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "terms": list(self.terms),
            "query_variants": list(self.query_variants),
        }


def extract_semantic_search_terms(text: str) -> SemanticSearchTerms:
    raw = str(text or "").strip()
    if not raw:
        return SemanticSearchTerms("", (), ())

    # Prefer the content after PLANTS: when the model emitted a partial
    # Forest Manager response.
    plant_match = re.search(
        r"(?is)\bPLANTS?\s*:\s*(.+)",
        raw,
    )
    working = plant_match.group(1).strip() if plant_match else raw

    tokens: list[str] = []
    for chunk in re.findall(r"[A-Za-z][A-Za-z'-]*", working):
        token = normalize_token(chunk)
        if not token or token in _STOPWORDS or len(token) < 3:
            continue
        if token not in tokens:
            tokens.append(token)

    variants: list[str] = []
    for token in tokens:
        for normalized in variants_for_term(token):
            if normalized not in variants:
                variants.append(normalized)

    return SemanticSearchTerms(
        raw_text=raw,
        terms=tuple(tokens),
        query_variants=tuple(variants),
    )
