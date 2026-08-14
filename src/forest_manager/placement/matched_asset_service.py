from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from forest_manager.asset_matching.t2_asset_matcher import (
    T2AssetMatch,
    T2MatchReport,
    T2SemanticAssetMatcher,
)


class BridgeResponseLike(Protocol):
    ok: bool
    data: dict[str, Any]
    error: str


class MaxBridgeLike(Protocol):
    def ping(self) -> BridgeResponseLike: ...
    def reset_managed_forest_from_selection(self) -> BridgeResponseLike: ...
    def append_t2_asset_geometry(
        self,
        asset_path: str,
        probability: float = 50.0,
    ) -> BridgeResponseLike: ...
    def set_geometry_probabilities(
        self,
        probabilities: list[float],
    ) -> BridgeResponseLike: ...
    def normalize_reference_sources(self) -> BridgeResponseLike: ...
    def configure_fixed_distribution_units(self) -> BridgeResponseLike: ...
    def get_forest_geometry_summary(self) -> BridgeResponseLike: ...


class MatchedAssetApplyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SelectedMatchedAsset:
    source_term: str
    asset_name: str
    file_path: str
    score: float
    probability: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_term": self.source_term,
            "asset_name": self.asset_name,
            "file_path": self.file_path,
            "score": round(float(self.score), 4),
            "probability": round(float(self.probability), 6),
        }


class MatchedAssetForestService:
    """
    Applies the best real T2 match for each semantic source term.

    Stage 5B deliberately uses equal probability per matched semantic term.
    The vision model has not yet produced reliable quantitative coverage data,
    so inventing unequal weights would be less trustworthy than equal weights.
    """

    def __init__(
        self,
        matcher: T2SemanticAssetMatcher,
        client: MaxBridgeLike,
    ) -> None:
        self.matcher = matcher
        self.client = client

    @staticmethod
    def select_best_per_term(
        report: T2MatchReport,
        *,
        max_terms: int = 5,
    ) -> tuple[SelectedMatchedAsset, ...]:
        best_by_term: dict[str, T2AssetMatch] = {}

        for match in report.matches:
            previous = best_by_term.get(match.source_term)
            if previous is None or match.score > previous.score:
                best_by_term[match.source_term] = match

        ordered: list[T2AssetMatch] = []
        for term in report.observed.terms:
            match = best_by_term.get(term)
            if match is not None:
                ordered.append(match)
            if len(ordered) >= max_terms:
                break

        if not ordered:
            return ()

        probability = 100.0 / float(len(ordered))
        return tuple(
            SelectedMatchedAsset(
                source_term=match.source_term,
                asset_name=match.asset_name,
                file_path=match.file_path,
                score=match.score,
                probability=probability,
            )
            for match in ordered
        )

    def preview(self, text: str, *, max_terms: int = 5) -> dict[str, Any]:
        report = self.matcher.match_text(text, max_matches=max(5, max_terms * 2))
        selected = self.select_best_per_term(report, max_terms=max_terms)
        return {
            "match_report": report.to_dict(),
            "selected_assets": [item.to_dict() for item in selected],
            "probability_policy": "equal_per_matched_semantic_term",
            "will_modify_3ds_max": False,
        }

    @staticmethod
    def _require_ok(response: BridgeResponseLike, label: str) -> dict[str, Any]:
        if not response.ok:
            raise MatchedAssetApplyError(f"{label}: {response.error}")
        return response.data

    def apply(self, text: str, *, max_terms: int = 5) -> dict[str, Any]:
        report = self.matcher.match_text(text, max_matches=max(5, max_terms * 2))
        selected = self.select_best_per_term(report, max_terms=max_terms)
        if not selected:
            raise MatchedAssetApplyError(
                "No real T2 assets matched the local-vision observation."
            )

        self._require_ok(self.client.ping(), "Bridge PING failed")
        reset = self._require_ok(
            self.client.reset_managed_forest_from_selection(),
            "Managed Forest reset failed",
        )

        appended: list[dict[str, Any]] = []
        for item in selected:
            response = self.client.append_t2_asset_geometry(
                item.file_path,
                probability=item.probability,
            )
            appended.append(
                self._require_ok(
                    response,
                    f"Could not append T2 asset {item.asset_name}",
                )
            )

        probabilities = [item.probability for item in selected]
        probability_result = self._require_ok(
            self.client.set_geometry_probabilities(probabilities),
            "Forest probability update failed",
        )
        distribution_result = self._require_ok(
            self.client.configure_fixed_distribution_units(),
            "Forest distribution normalization failed",
        )
        reference_result = self._require_ok(
            self.client.normalize_reference_sources(),
            "Reference source normalization failed",
        )
        summary = self._require_ok(
            self.client.get_forest_geometry_summary(),
            "Forest geometry verification failed",
        )

        geometry_names = list(summary.get("geometry_names") or [])
        verified = bool(
            reset.get("verified")
            and probability_result.get("verified")
            and reference_result.get("verified")
            and len(geometry_names) == len(selected)
            and abs(float(probability_result.get("probability_total", 0.0)) - 100.0) < 0.05
            and reference_result.get("layer_visible") is False
        )

        return {
            "match_report": report.to_dict(),
            "selected_assets": [item.to_dict() for item in selected],
            "probability_policy": "equal_per_matched_semantic_term",
            "forest_reset": reset,
            "appended_assets": appended,
            "probabilities": probability_result,
            "distribution": distribution_result,
            "reference_sources": reference_result,
            "geometry_summary": summary,
            "verified": verified,
        }
