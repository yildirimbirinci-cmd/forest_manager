from __future__ import annotations

from dataclasses import dataclass

from forest_manager.placement.composition_plan import CompositionPlan

from .models import ReferenceAnalysisResult


class ReferencePlanError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReferencePlanBuilder:
    """
    Converts semantic analysis results into the existing CompositionPlan contract.

    Stage 4I deliberately refuses to invent species when the analyzer has not
    supplied semantic suggestions. This prevents fake AI behavior.
    """

    default_weight: float = 1.0

    def build(self, analysis: ReferenceAnalysisResult) -> CompositionPlan:
        queries = [
            str(query).strip()
            for query in analysis.suggested_queries
            if str(query).strip()
        ]

        if not queries:
            raise ReferencePlanError(
                "Reference analysis produced no plant queries. "
                "A semantic vision analyzer is required before automatic T2 selection."
            )

        return CompositionPlan.from_dict({
            "name": f"Reference composition - {analysis.image.filename}",
            "items": [
                {"query": query, "weight": self.default_weight}
                for query in queries
            ],
        })
