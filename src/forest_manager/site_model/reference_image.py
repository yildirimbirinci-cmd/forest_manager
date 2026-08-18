from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class ReferenceZoneIntent:
    semantic_role: str
    label: str
    coverage_weight: float
    naturalness: str
    cluster_character: str
    confidence: float
    mask_path: str | None = None
    source_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReferenceImageAnalysis:
    image_path: str
    width: int
    height: int
    zones: tuple[ReferenceZoneIntent, ...]
    analysis_version: str = "stage8-reference-image-v1"

    @property
    def coverage_total(self) -> float:
        return sum(float(zone.coverage_weight) for zone in self.zones)


class ReferenceImageAnalyzer:
    """Deterministic visual-intent extractor for the Stage 8 foundation.

    This is deliberately separated from Forest Pack. It creates three semantic
    planting masks from the reference image using image-space composition,
    colourfulness and local texture. Later AI/CAD/PDF analyzers can replace or
    override these zones without changing Forest execution code.
    """

    ROLE_SPECS = (
        ("foreground_mass", "Foreground Mass"),
        ("mid_accent", "Mid Accent"),
        ("structural_shrub", "Structural Shrub"),
    )

    def from_group_intents(
        self,
        image_path: str,
        group_intents: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> ReferenceImageAnalysis:
        """Build variable-count semantic analysis from externally inferred AI group intents.

        This path carries semantic/species intent only. It deliberately does not
        project image masks into scene space; mask_path remains optional while
        the official map-free runtime is active.
        """
        path = Path(image_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Reference image does not exist: {path}")
        if not group_intents:
            raise ValueError("AI group-intent analysis must contain at least one Plant Group.")

        image = Image.open(path)
        width, height = image.size
        zones: list[ReferenceZoneIntent] = []
        raw_weights: list[float] = []
        for index, item in enumerate(group_intents, start=1):
            if not isinstance(item, dict):
                raise TypeError(f"AI group intent #{index} must be a dictionary.")
            role = str(item.get("semantic_role") or "").strip()
            if not role:
                raise ValueError(f"AI group intent #{index} has no semantic_role.")
            label = str(item.get("label") or role.replace("_", " ").title()).strip()
            weight = float(item.get("coverage_weight") or 0.0)
            if weight < 0.0:
                raise ValueError(f"AI group intent '{role}' has a negative coverage_weight.")
            raw_weights.append(weight)
            sources = item.get("source_names") or ()
            if isinstance(sources, str):
                sources = (sources,)
            else:
                sources = tuple(str(value).strip() for value in sources if str(value).strip())
            zones.append(
                ReferenceZoneIntent(
                    semantic_role=role,
                    label=label,
                    coverage_weight=weight,
                    naturalness=str(item.get("naturalness") or "Balanced"),
                    cluster_character=str(item.get("cluster_character") or "Medium Clusters"),
                    confidence=float(item.get("confidence") or item.get("visual_confidence") or 0.0),
                    mask_path=None if not item.get("mask_path") else str(item.get("mask_path")),
                    source_names=tuple(sources),
                )
            )

        total = sum(raw_weights)
        if total <= 0.0:
            raise ValueError("AI group-intent coverage weights must sum to more than zero.")
        normalized = tuple(
            ReferenceZoneIntent(
                semantic_role=zone.semantic_role,
                label=zone.label,
                coverage_weight=float(zone.coverage_weight / total),
                naturalness=zone.naturalness,
                cluster_character=zone.cluster_character,
                confidence=zone.confidence,
                mask_path=zone.mask_path,
                source_names=zone.source_names,
            )
            for zone in zones
        )
        return ReferenceImageAnalysis(
            image_path=str(path),
            width=int(width),
            height=int(height),
            zones=normalized,
            analysis_version="stage8-reference-image-variable-groups-v2",
        )

    def analyze(self, image_path: str, *, output_dir: str | None = None) -> ReferenceImageAnalysis:
        path = Path(image_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Reference image does not exist: {path}")

        image = Image.open(path).convert("RGB")
        original_size = image.size
        work = image.copy()
        work.thumbnail((512, 512), Image.Resampling.LANCZOS)
        rgb = np.asarray(work, dtype=np.float32) / 255.0
        height, width, _ = rgb.shape
        if width < 8 or height < 8:
            raise ValueError("Reference image is too small for planting-intent analysis.")

        # Visual features. No semantic species claims are made here.
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        saturation = maximum - minimum
        luminance = (0.2126 * rgb[:, :, 0]) + (0.7152 * rgb[:, :, 1]) + (0.0722 * rgb[:, :, 2])
        green_bias = np.clip(rgb[:, :, 1] - ((rgb[:, :, 0] + rgb[:, :, 2]) * 0.5), -1.0, 1.0)

        gray = Image.fromarray(np.uint8(np.clip(luminance * 255.0, 0, 255)), mode="L")
        edge = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
        edge = np.clip(edge, 0.0, 1.0)

        yy = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
        xx = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
        center_bias = 1.0 - np.clip(np.abs(xx - 0.5) * 2.0, 0.0, 1.0)

        # Foreground favours lower image-space mass and softer continuous areas.
        foreground = (0.52 * yy) + (0.18 * saturation) + (0.16 * np.maximum(green_bias, 0.0)) + (0.14 * (1.0 - edge))
        # Mid accent favours central colourful/contrasty regions.
        mid = (0.30 * center_bias) + (0.30 * saturation) + (0.24 * edge) + (0.16 * (1.0 - np.abs(yy - 0.52) * 2.0))
        # Structural shrub favours upper/deeper image-space and stronger form edges.
        structural = (0.38 * (1.0 - yy)) + (0.32 * edge) + (0.18 * np.maximum(green_bias, 0.0)) + (0.12 * (1.0 - luminance))

        scores = np.stack([foreground, mid, structural], axis=2)
        labels = np.argmax(scores, axis=2)
        # Ensure every role has a usable mask even on extremely uniform images.
        counts = np.bincount(labels.ravel(), minlength=3).astype(np.int64)
        total_pixels = int(labels.size)
        if np.any(counts == 0):
            thirds = np.minimum((np.arange(width, dtype=np.int64) * 3) // max(width, 1), 2)
            labels = np.repeat(thirds[None, :], height, axis=0)
            counts = np.bincount(labels.ravel(), minlength=3).astype(np.int64)

        output = Path(output_dir).expanduser().resolve() if output_dir else path.parent / "forest_manager_analysis"
        output.mkdir(parents=True, exist_ok=True)

        global_texture = float(np.mean(edge))
        global_sat = float(np.mean(saturation))
        zones: list[ReferenceZoneIntent] = []
        for index, (role, label) in enumerate(self.ROLE_SPECS):
            mask = labels == index
            coverage = float(np.count_nonzero(mask)) / float(total_pixels)
            confidence = float(np.mean(np.max(scores, axis=2)[mask] - np.partition(scores, -2, axis=2)[:, :, -2][mask]))
            confidence = float(np.clip(0.45 + confidence, 0.45, 0.98))

            zone_edge = float(np.mean(edge[mask])) if np.any(mask) else global_texture
            zone_sat = float(np.mean(saturation[mask])) if np.any(mask) else global_sat
            naturalness = self._naturalness(zone_edge, zone_sat)
            cluster = self._cluster_character(mask, zone_edge)

            mask_image = Image.fromarray(np.uint8(mask) * 255, mode="L")
            mask_image = mask_image.resize(original_size, Image.Resampling.NEAREST)
            mask_path = output / f"{path.stem}_{index + 1}_{role}.png"
            mask_image.save(mask_path)

            zones.append(
                ReferenceZoneIntent(
                    semantic_role=role,
                    label=label,
                    coverage_weight=coverage,
                    naturalness=naturalness,
                    cluster_character=cluster,
                    confidence=confidence,
                    mask_path=str(mask_path),
                )
            )

        # Normalize after raster assignment to avoid floating point drift.
        coverage_total = sum(zone.coverage_weight for zone in zones) or 1.0
        zones = [
            ReferenceZoneIntent(
                semantic_role=zone.semantic_role,
                label=zone.label,
                coverage_weight=float(zone.coverage_weight / coverage_total),
                naturalness=zone.naturalness,
                cluster_character=zone.cluster_character,
                confidence=zone.confidence,
                mask_path=zone.mask_path,
                source_names=zone.source_names,
            )
            for zone in zones
        ]

        return ReferenceImageAnalysis(
            image_path=str(path),
            width=int(original_size[0]),
            height=int(original_size[1]),
            zones=tuple(zones),
        )

    @staticmethod
    def _naturalness(edge_density: float, saturation: float) -> str:
        score = (0.68 * edge_density) + (0.32 * saturation)
        if score < 0.16:
            return "Ordered"
        if score < 0.27:
            return "Balanced"
        if score < 0.40:
            return "Natural"
        return "Wild"

    @staticmethod
    def _cluster_character(mask: np.ndarray, edge_density: float) -> str:
        # Estimate fragmentation using horizontal/vertical label transitions.
        horizontal = float(np.mean(mask[:, 1:] != mask[:, :-1])) if mask.shape[1] > 1 else 0.0
        vertical = float(np.mean(mask[1:, :] != mask[:-1, :])) if mask.shape[0] > 1 else 0.0
        fragmentation = horizontal + vertical + (0.35 * edge_density)
        if fragmentation > 0.52:
            return "Solitary"
        if fragmentation > 0.32:
            return "Small Groups"
        if fragmentation > 0.18:
            return "Medium Clusters"
        return "Large Masses"

    @staticmethod
    def to_dict(analysis: ReferenceImageAnalysis) -> dict[str, Any]:
        return {
            "image_path": analysis.image_path,
            "width": analysis.width,
            "height": analysis.height,
            "analysis_version": analysis.analysis_version,
            "coverage_total": analysis.coverage_total,
            "zones": [
                {
                    "semantic_role": zone.semantic_role,
                    "label": zone.label,
                    "coverage_weight": zone.coverage_weight,
                    "naturalness": zone.naturalness,
                    "cluster_character": zone.cluster_character,
                    "confidence": zone.confidence,
                    "mask_path": zone.mask_path,
                    "source_names": list(zone.source_names),
                }
                for zone in analysis.zones
            ],
        }
