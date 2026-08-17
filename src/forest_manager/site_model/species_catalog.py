from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .model import PlantingPlan
from .planting_plan import PlantingPlanBuilder


@dataclass(frozen=True)
class SpeciesCatalogEntry:
    semantic_role: str
    source_name: str
    label: str
    confidence: float = 1.0


class SpeciesCatalogResolver:
    """Resolve semantic planting roles to known scene/library source identities.

    Stage 8 keeps this resolver separate from image analysis so the visual model
    only describes planting intent. The resolver can later be replaced by a T2
    asset-library backed implementation without changing the PlantingPlan model.
    """

    DEFAULT_ENTRIES = (
        SpeciesCatalogEntry(
            semantic_role="foreground_mass",
            source_name="Lavandula angustifolia 'Hidcote' (Lavender)",
            label="Lavandula",
        ),
        SpeciesCatalogEntry(
            semantic_role="mid_accent",
            source_name="Butomus umbellatus (Flowering rush )",
            label="Butomus",
        ),
        SpeciesCatalogEntry(
            semantic_role="structural_shrub",
            source_name="Bush_Berberis",
            label="Bush_Berberis",
        ),
    )

    def __init__(self, entries: tuple[SpeciesCatalogEntry, ...] | None = None) -> None:
        self._entries = entries or self.DEFAULT_ENTRIES
        self._by_role = {entry.semantic_role: entry for entry in self._entries}

    def resolve_sources(self, plan: PlantingPlan) -> dict[str, tuple[str, ...]]:
        resolved: dict[str, tuple[str, ...]] = {}
        for group in plan.groups:
            entry = self._by_role.get(group.semantic_role)
            if entry is not None:
                resolved[group.semantic_role] = (entry.source_name,)
        return resolved

    def resolve_plan(self, plan: PlantingPlan) -> PlantingPlan:
        sources = self.resolve_sources(plan)
        if not sources:
            return plan
        builder = PlantingPlanBuilder()
        # Rebuild from the already-analyzed groups while preserving visual intent.
        groups = []
        for group in plan.groups:
            names = tuple(sources.get(group.semantic_role) or group.source_names)
            groups.append(group.__class__(
                group_id=group.group_id,
                label=group.label,
                order=group.order,
                semantic_role=group.semantic_role,
                coverage_weight=group.coverage_weight,
                source_names=names,
                naturalness=group.naturalness,
                cluster_character=group.cluster_character,
                zone_mask_path=group.zone_mask_path,
                visual_confidence=group.visual_confidence,
            ))
        return plan.__class__(
            site_model=plan.site_model,
            forest_name=plan.forest_name,
            groups=tuple(groups),
            reference_image_path=plan.reference_image_path,
            generated_by=plan.generated_by,
        )

    def summary(self) -> list[dict[str, object]]:
        return [
            {
                "semantic_role": entry.semantic_role,
                "source_name": entry.source_name,
                "label": entry.label,
                "confidence": entry.confidence,
            }
            for entry in self._entries
        ]
