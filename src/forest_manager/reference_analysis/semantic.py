from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class SemanticVisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SemanticPlantCandidate:
    query: str
    weight: float

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("Semantic plant query must not be empty.")
        if float(self.weight) <= 0.0:
            raise ValueError("Semantic plant weight must be greater than zero.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "weight": float(self.weight),
        }


@dataclass(frozen=True)
class SemanticLandscapeAnalysis:
    style: str
    density: str
    diversity: str
    canopy_bias: str
    composition_notes: tuple[str, ...]
    plant_candidates: tuple[SemanticPlantCandidate, ...]
    confidence: float
    provider: str

    def __post_init__(self) -> None:
        if not self.style.strip():
            raise ValueError("Semantic style must not be empty.")
        if not self.density.strip():
            raise ValueError("Semantic density must not be empty.")
        if not self.diversity.strip():
            raise ValueError("Semantic diversity must not be empty.")
        if not self.canopy_bias.strip():
            raise ValueError("Semantic canopy bias must not be empty.")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("Semantic confidence must be between 0 and 1.")
        if not self.provider.strip():
            raise ValueError("Semantic provider name must not be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "density": self.density,
            "diversity": self.diversity,
            "canopy_bias": self.canopy_bias,
            "composition_notes": list(self.composition_notes),
            "plant_candidates": [
                candidate.to_dict()
                for candidate in self.plant_candidates
            ],
            "confidence": float(self.confidence),
            "provider": self.provider,
        }


@runtime_checkable
class SemanticVisionProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    def analyze_image(
        self,
        image_path: str,
        *,
        width: int,
        height: int,
        orientation: str,
    ) -> SemanticLandscapeAnalysis:
        ...
