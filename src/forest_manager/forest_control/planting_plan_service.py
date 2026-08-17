from __future__ import annotations

from dataclasses import asdict
from typing import Any

from forest_manager.max_bridge.runtime_bridge import ensure_primary_forest_for_spline
from forest_manager.site_model import PlantingPlan, SiteModel


class PlantingPlanExecutionError(RuntimeError):
    pass


class Forest01FoundationService:
    """Stage 8 boundary/Forest bootstrap layer.

    Image/CAD/PDF analysis produces a PlantingPlan. Asset resolution and Forest
    execution remain separate so visual analysis never writes Forest Pack
    internals directly.
    """

    def ensure_forest(self, site_model: SiteModel) -> dict[str, Any]:
        result = ensure_primary_forest_for_spline(site_model.primary_boundary.node_name)
        return {
            "site_boundary": asdict(site_model.primary_boundary),
            "forest": result,
            "verified": bool(result.get("verified")),
        }

    def validate_plan(self, plan: PlantingPlan) -> dict[str, Any]:
        weights = [float(group.coverage_weight) for group in plan.groups]
        total = sum(weights)
        if not plan.groups:
            raise PlantingPlanExecutionError("PlantingPlan contains no Plant Groups.")
        if total <= 0.0:
            raise PlantingPlanExecutionError("PlantingPlan coverage weights must sum to more than zero.")
        return {
            "forest_name": plan.forest_name,
            "group_count": len(plan.groups),
            "coverage_total": total,
            "visual_intent_ready": plan.visual_intent_ready,
            "execution_ready": plan.execution_ready,
            "unresolved_group_ids": [group.group_id for group in plan.groups if not group.source_names],
            "groups": [
                {
                    "group_id": group.group_id,
                    "label": group.label,
                    "semantic_role": group.semantic_role,
                    "coverage_weight": group.coverage_weight,
                    "naturalness": group.naturalness,
                    "cluster_character": group.cluster_character,
                    "zone_mask_path": group.zone_mask_path,
                    "visual_confidence": group.visual_confidence,
                    "source_names": list(group.source_names),
                }
                for group in plan.groups
            ],
            "verified": True,
        }
