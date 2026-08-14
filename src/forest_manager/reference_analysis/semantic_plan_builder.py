from __future__ import annotations

from dataclasses import dataclass

from forest_manager.placement.composition_plan import CompositionPlan

from .semantic import SemanticLandscapeAnalysis


class SemanticPlanError(RuntimeError):
    pass


@dataclass(frozen=True)
class SemanticCompositionPlanBuilder:
    minimum_confidence: float = 0.50

    def build(
        self,
        analysis: SemanticLandscapeAnalysis,
        *,
        image_filename: str,
    ) -> CompositionPlan:
        if analysis.confidence < self.minimum_confidence:
            raise SemanticPlanError(
                "Semantic analysis confidence is below the automatic planning threshold."
            )

        if not analysis.plant_candidates:
            raise SemanticPlanError(
                "Semantic analysis produced no plant candidates."
            )

        seen: set[str] = set()
        items: list[dict[str, object]] = []

        for candidate in analysis.plant_candidates:
            key = candidate.query.casefold().strip()
            if key in seen:
                raise SemanticPlanError(
                    "Semantic analysis contains duplicate plant candidates."
                )
            seen.add(key)
            items.append({
                "query": candidate.query.strip(),
                "weight": float(candidate.weight),
            })

        return CompositionPlan.from_dict({
            "name": f"Reference composition - {image_filename}",
            "items": items,
        })
