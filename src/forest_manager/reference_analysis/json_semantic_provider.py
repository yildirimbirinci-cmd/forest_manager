from __future__ import annotations

import json
from pathlib import Path

from .semantic import (
    SemanticLandscapeAnalysis,
    SemanticPlantCandidate,
    SemanticVisionError,
)


class JsonSemanticVisionProvider:
    """
    Contract-validation provider.

    Reads semantic analysis from a JSON file. It does not claim to perform image
    understanding. Its purpose is to verify the semantic provider interface end-to-end
    before a live vision model is attached.
    """

    def __init__(self, semantic_json_path: Path | str):
        self.semantic_json_path = Path(semantic_json_path)

    @property
    def name(self) -> str:
        return "json_contract_provider"

    def analyze_image(
        self,
        image_path: str,
        *,
        width: int,
        height: int,
        orientation: str,
    ) -> SemanticLandscapeAnalysis:
        if not self.semantic_json_path.exists():
            raise SemanticVisionError(
                f"Semantic JSON does not exist: {self.semantic_json_path}"
            )

        payload = json.loads(
            self.semantic_json_path.read_text(encoding="utf-8")
        )

        candidates = tuple(
            SemanticPlantCandidate(
                query=str(item["query"]).strip(),
                weight=float(item["weight"]),
            )
            for item in payload.get("plant_candidates", [])
        )

        return SemanticLandscapeAnalysis(
            style=str(payload["style"]).strip(),
            density=str(payload["density"]).strip(),
            diversity=str(payload["diversity"]).strip(),
            canopy_bias=str(payload["canopy_bias"]).strip(),
            composition_notes=tuple(
                str(note).strip()
                for note in payload.get("composition_notes", [])
                if str(note).strip()
            ),
            plant_candidates=candidates,
            confidence=float(payload["confidence"]),
            provider=self.name,
        )
