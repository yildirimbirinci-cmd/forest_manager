from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReferenceImageInfo:
    path: str
    filename: str
    extension: str
    width: int
    height: int
    aspect_ratio: float
    orientation: str
    file_size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlantingIntent:
    style: str
    density: str
    diversity: str
    canopy_bias: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "density": self.density,
            "diversity": self.diversity,
            "canopy_bias": self.canopy_bias,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ReferenceAnalysisResult:
    image: ReferenceImageInfo
    intent: PlantingIntent
    suggested_queries: tuple[str, ...]
    confidence: float
    analyzer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image.to_dict(),
            "intent": self.intent.to_dict(),
            "suggested_queries": list(self.suggested_queries),
            "confidence": self.confidence,
            "analyzer": self.analyzer,
        }
