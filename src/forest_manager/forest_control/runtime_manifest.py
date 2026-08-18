from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from forest_manager.site_model import PlantingPlan

from .planting_plan_service import PlantingPlanExecutionError


@dataclass(frozen=True)
class MapFreeManifestPolicy:
    """Explicit scene-space spacing policy for map-free Plant Group execution.

    Spacing is deliberately supplied by the caller. Reference-image pixel masks
    and image dimensions are never projected into Forest Pack scene space.
    """

    spacing_system_by_group: Mapping[str, float]

    def spacing_for(self, group_id: str) -> float:
        try:
            value = float(self.spacing_system_by_group[group_id])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlantingPlanExecutionError(
                f"No explicit scene-space spacing is defined for Plant Group '{group_id}'."
            ) from exc
        if value <= 0.0:
            raise PlantingPlanExecutionError(
                f"Scene-space spacing must be positive for Plant Group '{group_id}'."
            )
        return value


class MapFreeRuntimeManifestBuilder:
    """Translate an execution-ready PlantingPlan to the stable manifest schema."""

    def build(
        self,
        plan: PlantingPlan,
        *,
        policy: MapFreeManifestPolicy,
    ) -> dict[str, Any]:
        if not plan.groups:
            raise PlantingPlanExecutionError("PlantingPlan contains no Plant Groups.")
        unresolved = [group.group_id for group in plan.groups if not group.source_names]
        if unresolved:
            raise PlantingPlanExecutionError(
                "PlantingPlan is not execution-ready; unresolved groups: " + ", ".join(unresolved)
            )

        boundary_name = str(plan.site_model.primary_boundary.node_name or "").strip()
        if not boundary_name:
            raise PlantingPlanExecutionError("PlantingPlan has no primary scene boundary.")

        total = sum(max(0.0, float(group.coverage_weight)) for group in plan.groups)
        if total <= 0.0:
            raise PlantingPlanExecutionError("PlantingPlan coverage weights must sum to more than zero.")

        groups: list[dict[str, Any]] = []
        for group in plan.groups:
            spacing = policy.spacing_for(group.group_id)
            groups.append(
                {
                    "group_id": group.group_id,
                    "label": group.label,
                    "semantic_role": group.semantic_role,
                    "coverage_weight": max(0.0, float(group.coverage_weight)) / total,
                    "source_names": list(group.source_names),
                    "spacing_system": [spacing, spacing],
                    "area_nodes": [boundary_name],
                    "naturalness": group.naturalness,
                    "cluster_character": group.cluster_character,
                    "visual_confidence": float(group.visual_confidence),
                }
            )

        return {
            "primary_forest": str(plan.forest_name or "FM_Forest_001").strip() or "FM_Forest_001",
            "groups": groups,
            "reference_image_path": plan.reference_image_path,
            "generated_by": plan.generated_by,
            "map_policy": "parked_not_projected_from_reference_image",
        }
