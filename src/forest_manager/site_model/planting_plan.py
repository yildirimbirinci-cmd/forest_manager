from __future__ import annotations

from .model import PlantingGroupIntent, PlantingPlan, SiteModel
from .reference_image import ReferenceImageAnalysis


class PlantingPlanBuilder:
    """Create a semantic planting plan without exposing Forest Pack internals to AI."""

    DEFAULT_GROUPS = (
        ("foreground_mass", "Foreground Mass", 0.40),
        ("mid_accent", "Mid Accent", 0.25),
        ("structural_shrub", "Structural Shrub", 0.35),
    )

    def bootstrap(
        self,
        site_model: SiteModel,
        *,
        reference_image_path: str | None = None,
        source_names: dict[str, tuple[str, ...]] | None = None,
    ) -> PlantingPlan:
        source_names = source_names or {}
        groups = []
        for order, (key, label, weight) in enumerate(self.DEFAULT_GROUPS, start=1):
            groups.append(
                PlantingGroupIntent(
                    group_id=f"plant_group:{order}:{key}",
                    label=label,
                    order=order,
                    semantic_role=key,
                    coverage_weight=float(weight),
                    source_names=tuple(source_names.get(key) or ()),
                )
            )
        return PlantingPlan(
            site_model=site_model,
            forest_name="FM_Forest_001",
            groups=tuple(groups),
            reference_image_path=reference_image_path or site_model.reference_image_path,
        )

    def from_reference_image(
        self,
        site_model: SiteModel,
        analysis: ReferenceImageAnalysis,
        *,
        source_names: dict[str, tuple[str, ...]] | None = None,
    ) -> PlantingPlan:
        source_names = source_names or {}
        groups = []
        for order, zone in enumerate(analysis.zones, start=1):
            groups.append(
                PlantingGroupIntent(
                    group_id=f"plant_group:{order}:{zone.semantic_role}",
                    label=zone.label,
                    order=order,
                    semantic_role=zone.semantic_role,
                    coverage_weight=float(zone.coverage_weight),
                    source_names=tuple(source_names.get(zone.semantic_role) or zone.source_names or ()),
                    naturalness=zone.naturalness,
                    cluster_character=zone.cluster_character,
                    zone_mask_path=zone.mask_path,
                    visual_confidence=float(zone.confidence),
                )
            )
        return PlantingPlan(
            site_model=site_model,
            forest_name="FM_Forest_001",
            groups=tuple(groups),
            reference_image_path=analysis.image_path,
            generated_by=analysis.analysis_version,
        )
