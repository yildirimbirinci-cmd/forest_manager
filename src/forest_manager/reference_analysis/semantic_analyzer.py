from __future__ import annotations

from pathlib import Path

from .analyzer import ReferenceImageAnalyzer, ReferenceImageError
from .models import PlantingIntent, ReferenceAnalysisResult
from .semantic import (
    SemanticLandscapeAnalysis,
    SemanticVisionError,
    SemanticVisionProvider,
)


class SemanticReferenceImageAnalyzer:
    """
    Product-level semantic analyzer.

    Structural validation always runs first. The external/local vision provider is
    then responsible for genuine semantic understanding of the image.
    """

    def __init__(
        self,
        provider: SemanticVisionProvider,
        structural_analyzer: ReferenceImageAnalyzer | None = None,
    ):
        self.provider = provider
        self.structural_analyzer = structural_analyzer or ReferenceImageAnalyzer()

    def analyze(self, image_path: Path | str) -> ReferenceAnalysisResult:
        structural = self.structural_analyzer.analyze(image_path)

        semantic = self.provider.analyze_image(
            structural.image.path,
            width=structural.image.width,
            height=structural.image.height,
            orientation=structural.image.orientation,
        )

        if not isinstance(semantic, SemanticLandscapeAnalysis):
            raise SemanticVisionError(
                "Vision provider returned an invalid semantic result type."
            )

        queries = tuple(
            candidate.query
            for candidate in semantic.plant_candidates
            if candidate.query.strip()
        )

        return ReferenceAnalysisResult(
            image=structural.image,
            intent=PlantingIntent(
                style=semantic.style,
                density=semantic.density,
                diversity=semantic.diversity,
                canopy_bias=semantic.canopy_bias,
                notes=semantic.composition_notes,
            ),
            suggested_queries=queries,
            confidence=semantic.confidence,
            analyzer=semantic.provider,
        )
