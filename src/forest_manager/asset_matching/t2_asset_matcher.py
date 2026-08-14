from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Protocol, Sequence

from .semantic_terms import (
    SemanticSearchTerms,
    extract_semantic_search_terms,
    normalize_token,
    variants_for_term,
)


class AssetRecordLike(Protocol):
    name: str
    file_path: Any


class T2CatalogLike(Protocol):
    def search_max_assets(
        self,
        query: str,
        *,
        limit: int = 20,
        require_existing_file: bool = True,
    ) -> Sequence[AssetRecordLike]:
        ...


@dataclass(frozen=True)
class T2AssetMatch:
    source_term: str
    score: float
    asset_name: str
    file_path: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "source_term": self.source_term,
            "score": round(float(self.score), 4),
            "asset_name": self.asset_name,
            "file_path": self.file_path,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class T2MatchReport:
    observed: SemanticSearchTerms
    matches: tuple[T2AssetMatch, ...]
    unmatched_terms: tuple[str, ...]

    @property
    def matched(self) -> bool:
        return bool(self.matches)

    def to_dict(self) -> dict:
        return {
            "observed": self.observed.to_dict(),
            "matches": [item.to_dict() for item in self.matches],
            "unmatched_terms": list(self.unmatched_terms),
            "matched": self.matched,
        }


def _name_tokens(value: str) -> set[str]:
    result: set[str] = set()
    for chunk in re.findall(r"[A-Za-z][A-Za-z'-]*", value):
        token = normalize_token(chunk)
        if token:
            result.add(token)
    return result


class T2SemanticAssetMatcher:
    """
    Maps local-vision observations to real T2 .max assets.

    The matcher never invents an asset. Every returned item must originate from
    T2AssetCatalog.search_max_assets().
    """

    def __init__(self, catalog: T2CatalogLike):
        self.catalog = catalog

    @staticmethod
    def _score_asset(
        *,
        source_term: str,
        query_variant: str,
        asset: AssetRecordLike,
    ) -> tuple[float, tuple[str, ...]]:
        asset_name = str(getattr(asset, "name", "") or "")
        asset_path = str(getattr(asset, "file_path", "") or "")
        name_folded = asset_name.casefold()
        path_folded = asset_path.casefold()
        name_tokens = _name_tokens(asset_name)

        score = 0.0
        reasons: list[str] = []

        if query_variant.casefold() in name_folded:
            score += 100.0
            reasons.append("query_in_name")

        if source_term.casefold() in name_folded:
            score += 60.0
            reasons.append("source_term_in_name")

        if query_variant in name_tokens:
            score += 45.0
            reasons.append("name_token_exact")

        if query_variant.casefold() in path_folded:
            score += 20.0
            reasons.append("query_in_path")

        # Search result existence itself is weak evidence because the T2
        # catalog may use category/path fallback matching.
        score += 5.0
        reasons.append("t2_catalog_match")

        return score, tuple(reasons)

    def match_text(
        self,
        text: str,
        *,
        per_query_limit: int = 20,
        max_matches: int = 5,
    ) -> T2MatchReport:
        observed = extract_semantic_search_terms(text)

        best_by_asset: dict[str, T2AssetMatch] = {}
        matched_source_terms: set[str] = set()

        for source_term in observed.terms:
            variants = variants_for_term(source_term)
            source_had_match = False

            for query_variant in variants:
                results = self.catalog.search_max_assets(
                    query_variant,
                    limit=per_query_limit,
                    require_existing_file=True,
                )

                for asset in results:
                    asset_name = str(getattr(asset, "name", "") or "").strip()
                    asset_path = str(getattr(asset, "file_path", "") or "").strip()
                    if not asset_name or not asset_path:
                        continue

                    # Guard against non-.max records even if a catalog
                    # implementation is permissive.
                    if Path(asset_path).suffix.casefold() != ".max":
                        continue

                    score, reasons = self._score_asset(
                        source_term=source_term,
                        query_variant=query_variant,
                        asset=asset,
                    )

                    candidate = T2AssetMatch(
                        source_term=source_term,
                        score=score,
                        asset_name=asset_name,
                        file_path=asset_path,
                        reasons=reasons,
                    )

                    key = str(Path(asset_path)).casefold()
                    previous = best_by_asset.get(key)
                    if previous is None or candidate.score > previous.score:
                        best_by_asset[key] = candidate

                    source_had_match = True

                # Direct/source query matched; do not let unrelated global
                # synonyms swamp the score.
                if source_had_match and query_variant == source_term:
                    break

            if source_had_match:
                matched_source_terms.add(source_term)

        ordered = sorted(
            best_by_asset.values(),
            key=lambda item: (-item.score, item.asset_name.casefold()),
        )

        # Prefer unique source terms first so one botanical family cannot fill
        # the whole composition candidate list.
        selected: list[T2AssetMatch] = []
        selected_assets: set[str] = set()
        selected_terms: set[str] = set()

        for candidate in ordered:
            if candidate.source_term in selected_terms:
                continue
            key = candidate.file_path.casefold()
            if key in selected_assets:
                continue
            selected.append(candidate)
            selected_assets.add(key)
            selected_terms.add(candidate.source_term)
            if len(selected) >= max_matches:
                break

        if len(selected) < max_matches:
            for candidate in ordered:
                key = candidate.file_path.casefold()
                if key in selected_assets:
                    continue
                selected.append(candidate)
                selected_assets.add(key)
                if len(selected) >= max_matches:
                    break

        unmatched = tuple(
            term for term in observed.terms
            if term not in matched_source_terms
        )

        return T2MatchReport(
            observed=observed,
            matches=tuple(selected),
            unmatched_terms=unmatched,
        )
