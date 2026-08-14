from __future__ import annotations

from pathlib import Path
from typing import Any

from .local_backend import LocalVisionBackend, LocalVisionBackendError
from .semantic import (
    SemanticLandscapeAnalysis,
    SemanticPlantCandidate,
    SemanticVisionError,
)
from .smolvlm500m_local_backend import SmolVLM500MLocalBackend


class LocalSemanticVisionProvider:
    def __init__(self, backend: LocalVisionBackend | None = None):
        self.backend = backend or SmolVLM500MLocalBackend()

    @property
    def name(self) -> str:
        return "forest_manager_local_vision"

    @staticmethod
    def _prompt(width: int, height: int, orientation: str) -> str:
        return (
            "Analyze the visible landscape planting. "
            "Do not repeat this request. "
            "Reply only with these seven lines:\\n"
            "STYLE: <short style>\\n"
            "DENSITY: <low|medium|high>\\n"
            "DIVERSITY: <low|medium|high>\\n"
            "CANOPY_BIAS: <short description>\\n"
            "NOTES: <note>; <note>\\n"
            "PLANTS: <visible plant term>|<weight>; <visible plant term>|<weight>\\n"
            "CONFIDENCE: <0 to 1>\\n"
            "Use broad plant terms if species is uncertain. Do not invent cultivars. "
            f"Image is {width}x{height}, {orientation}."
        )

    @staticmethod
    def _to_semantic(
        payload: dict[str, Any],
        *,
        provider: str,
    ) -> SemanticLandscapeAnalysis:
        required = {
            "style",
            "density",
            "diversity",
            "canopy_bias",
            "plant_candidates",
            "confidence",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise SemanticVisionError(
                "Local vision output is missing fields: " + ", ".join(missing)
            )

        raw_candidates = payload["plant_candidates"]
        if not isinstance(raw_candidates, list):
            raise SemanticVisionError(
                "Local vision plant_candidates must be an array."
            )

        candidates = tuple(
            SemanticPlantCandidate(
                query=str(item["query"]).strip(),
                weight=float(item["weight"]),
            )
            for item in raw_candidates
        )

        raw_notes = payload.get("composition_notes", [])
        if not isinstance(raw_notes, list):
            raise SemanticVisionError(
                "Local vision composition_notes must be an array."
            )

        return SemanticLandscapeAnalysis(
            style=str(payload["style"]).strip(),
            density=str(payload["density"]).strip(),
            diversity=str(payload["diversity"]).strip(),
            canopy_bias=str(payload["canopy_bias"]).strip(),
            composition_notes=tuple(
                str(note).strip()
                for note in raw_notes
                if str(note).strip()
            ),
            plant_candidates=candidates,
            confidence=float(payload["confidence"]),
            provider=provider,
        )

    def analyze_image(
        self,
        image_path: str,
        *,
        width: int,
        height: int,
        orientation: str,
    ) -> SemanticLandscapeAnalysis:
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            raise SemanticVisionError(
                f"Reference image does not exist: {path}"
            )

        if not self.backend.is_available():
            raise SemanticVisionError(
                "Local vision backend is not available. "
                "Install/bundle the model and dependencies under models/vision."
            )

        try:
            payload = self.backend.analyze(
                str(path),
                self._prompt(width, height, orientation),
            )
        except LocalVisionBackendError as exc:
            raise SemanticVisionError(str(exc)) from exc

        return self._to_semantic(payload, provider=self.name)
