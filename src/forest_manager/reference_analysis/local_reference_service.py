from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forest_manager.placement.composition_service import CompositionPlanService

from .analyzer import ReferenceImageAnalyzer
from .local_semantic_provider import LocalSemanticVisionProvider
from .semantic_plan_builder import SemanticCompositionPlanBuilder


@dataclass
class LocalReferenceCompositionService:
    provider: LocalSemanticVisionProvider
    structural_analyzer: ReferenceImageAnalyzer
    plan_builder: SemanticCompositionPlanBuilder
    composition_service: CompositionPlanService

    @classmethod
    def create_default(cls) -> "LocalReferenceCompositionService":
        return cls(
            provider=LocalSemanticVisionProvider(),
            structural_analyzer=ReferenceImageAnalyzer(),
            plan_builder=SemanticCompositionPlanBuilder(),
            composition_service=CompositionPlanService(),
        )

    def analyze_only(self, image_path: Path | str) -> dict[str, Any]:
        structural = self.structural_analyzer.analyze(image_path)
        semantic = self.provider.analyze_image(
            structural.image.path,
            width=structural.image.width,
            height=structural.image.height,
            orientation=structural.image.orientation,
        )
        plan = self.plan_builder.build(
            semantic,
            image_filename=structural.image.filename,
        )

        return {
            "image": structural.image.to_dict(),
            "semantic": semantic.to_dict(),
            "composition_plan": {
                "name": plan.name,
                "items": [
                    {"query": item.query, "weight": item.weight}
                    for item in plan.items
                ],
                "normalized_probabilities": plan.normalized_probabilities,
            },
            "_plan": plan,
        }

    def analyze_and_apply(self, image_path: Path | str) -> dict[str, Any]:
        result = self.analyze_only(image_path)
        plan = result.pop("_plan")
        result["forest_apply"] = self.composition_service.apply(plan)
        return result
