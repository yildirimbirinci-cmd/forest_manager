from __future__ import annotations

from dataclasses import asdict
from typing import Any

from forest_manager.max_bridge.runtime_bridge import (
    get_single_forest_distribution_diagnostics,
    write_plant_group_manifest,
)
from forest_manager.site_model import PlantingPlan

from .plant_group_execution import execute_plant_group_manifest
from .stage8_asset_resolution import Stage8T2AssetResolver
from .planting_plan_service import Forest01FoundationService
from .service import ForestControlError, ForestPackControlService


_ROLE_SPACING_FACTORS = {
    "foreground_mass": 0.08,
    "mid_accent": 0.10,
    "structural_shrub": 0.18,
}


class Stage8SceneExecutionError(RuntimeError):
    pass


def _geometry_source_names(service: ForestPackControlService, forest_name: str) -> list[str]:
    inventory = service.inventory(forest_name, preflight=False)
    prop = next(
        (
            item
            for item in inventory.get("properties") or []
            if isinstance(item, dict) and str(item.get("name") or "").lower() == "cobjlist"
        ),
        None,
    )
    metadata = prop.get("array_metadata") if isinstance(prop, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    names: list[str] = []
    for index in range(count):
        row = service.get_array_element(forest_name, "cobjlist", index, preflight=False)
        value = str(row.get("value") or "").strip()
        if value:
            names.append(value)
    return names


def _ensure_required_geometry_sources(
    service: ForestPackControlService,
    forest_name: str,
    plan: PlantingPlan,
    *,
    asset_resolver: Stage8T2AssetResolver,
) -> tuple[dict[str, Any], PlantingPlan]:
    existing = _geometry_source_names(service, forest_name)
    added: list[dict[str, Any]] = []
    merged: list[dict[str, Any]] = []
    source_name_map: dict[str, str] = {}

    for group in plan.groups:
        for requested_name in group.source_names:
            if requested_name in existing:
                source_name_map[requested_name] = requested_name
                continue

            # First reuse a scene node if the source already exists outside the
            # Forest Geometry List. A clean Stage 8 scene normally falls through
            # to the T2 merge path below.
            try:
                result = service.add_geometry_source_by_name(forest_name, requested_name, preflight=False)
            except ForestControlError as exc:
                if "Source geometry node not found" not in str(exc):
                    raise
            else:
                added.append(result)
                existing = _geometry_source_names(service, forest_name)
                if requested_name not in existing:
                    raise Stage8SceneExecutionError(
                        f"Existing scene source '{requested_name}' was added but did not verify in the Geometry List."
                    )
                source_name_map[requested_name] = requested_name
                continue

            merge_result = asset_resolver.merge_missing_source(
                requested_name,
                group.semantic_role,
                geometry_count=len(existing),
            )
            actual_name = str(merge_result.get("source_name") or "").strip()
            if not actual_name:
                raise Stage8SceneExecutionError(f"T2 merge returned no source node for '{requested_name}'.")
            merged.append(merge_result)
            source_name_map[requested_name] = actual_name
            existing = _geometry_source_names(service, forest_name)
            if actual_name not in existing:
                raise Stage8SceneExecutionError(
                    f"T2 asset '{requested_name}' merged as '{actual_name}' but was not present in the Forest Geometry List."
                )

    effective_plan = asset_resolver.remap_plan(plan, source_name_map)
    required = [name for group in effective_plan.groups for name in group.source_names]
    missing = [name for name in required if name not in existing]
    if missing:
        raise Stage8SceneExecutionError(
            "Required Stage 8 species could not be bound to the Forest Geometry List: " + ", ".join(missing)
        )
    return ({
        "required": required,
        "existing_after": existing,
        "added_from_scene": added,
        "merged_from_t2": merged,
        "source_name_map": source_name_map,
        "verified": not missing,
    }, effective_plan)


def _scene_spacing_system(plan: PlantingPlan, semantic_role: str) -> float:
    boundary = plan.site_model.primary_boundary
    extent = min(float(boundary.width_system_units), float(boundary.depth_system_units))
    if extent <= 0.0:
        extent = max(float(boundary.width_system_units), float(boundary.depth_system_units), 100.0)
    factor = float(_ROLE_SPACING_FACTORS.get(semantic_role, 0.10))
    # Keep the initial Stage 8 plan proportional to the actual site.  This is a
    # baseline only; user edits remain exact values later.
    return max(5.0, extent * factor)


def plan_to_runtime_manifest(plan: PlantingPlan) -> dict[str, Any]:
    if not plan.execution_ready:
        unresolved = [group.group_id for group in plan.groups if not group.source_names]
        raise Stage8SceneExecutionError(
            "PlantingPlan is not execution-ready; unresolved groups: " + ", ".join(unresolved)
        )
    if not plan.visual_intent_ready:
        unresolved = [group.group_id for group in plan.groups if not group.zone_mask_path]
        raise Stage8SceneExecutionError(
            "PlantingPlan has no visual zone masks for: " + ", ".join(unresolved)
        )

    area_node = plan.site_model.primary_boundary.node_name
    groups: list[dict[str, Any]] = []
    for group in plan.groups:
        spacing = _scene_spacing_system(plan, group.semantic_role)
        artist_values = {
            "species_enabled": True,
            "species_scale_percent": 100.0,
            "naturalness": group.naturalness,
            "cluster_character": group.cluster_character,
        }
        groups.append(
            {
                "group_id": group.group_id,
                "label": group.label,
                "order": int(group.order),
                "semantic_role": group.semantic_role,
                "source_names": list(group.source_names),
                "spacing_system": [float(spacing), float(spacing)],
                "area_nodes": [area_node],
                "area_modes": [0],
                "coverage_weight": float(group.coverage_weight),
                "zone_mask_path": str(group.zone_mask_path or ""),
                "visual_confidence": float(group.visual_confidence),
                "artist_values": artist_values,
                "reset_defaults": {
                    "spacing_system": [float(spacing), float(spacing)],
                    "area_reference_system": min(
                        float(plan.site_model.primary_boundary.width_system_units),
                        float(plan.site_model.primary_boundary.depth_system_units),
                    ),
                    "artist_values": dict(artist_values),
                },
            }
        )
    return {
        "schema_version": 2,
        "primary_forest": plan.forest_name,
        "generated_by": plan.generated_by,
        "reference_image_path": plan.reference_image_path,
        "site_boundary": asdict(plan.site_model.primary_boundary),
        "groups": groups,
    }


class Stage8PlantingPlanSceneExecutor:
    def __init__(
        self,
        service: ForestPackControlService | None = None,
        asset_resolver: Stage8T2AssetResolver | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.foundation = Forest01FoundationService()
        self.asset_resolver = asset_resolver or Stage8T2AssetResolver()

    def execute(self, plan: PlantingPlan) -> dict[str, Any]:
        validation = self.foundation.validate_plan(plan)
        if not validation.get("execution_ready") or not validation.get("visual_intent_ready"):
            raise Stage8SceneExecutionError("Stage 8 PlantingPlan is not ready for scene execution.")

        forest_result = self.foundation.ensure_forest(plan.site_model)
        if not forest_result.get("verified"):
            raise Stage8SceneExecutionError("Primary Forest bootstrap did not verify.")

        geometry_result, effective_plan = _ensure_required_geometry_sources(
            self.service,
            plan.forest_name,
            plan,
            asset_resolver=self.asset_resolver,
        )
        manifest = plan_to_runtime_manifest(effective_plan)

        execution = execute_plant_group_manifest(manifest, service=self.service, strict_acceptance=True)
        if not execution.get("verified"):
            raise Stage8SceneExecutionError("PlantingPlan Forest execution did not verify.")

        manifest_write = write_plant_group_manifest(manifest)
        diagnostics = get_single_forest_distribution_diagnostics(plan.forest_name)
        generated = {
            int(item.get("species_id") or 0): int(item.get("generated_items") or 0)
            for item in diagnostics.get("generated_geometry_ids") or []
            if isinstance(item, dict)
        }
        executed_species = [
            int(species_id)
            for group in execution.get("groups") or []
            for species_id in (group.get("species_ids") or [])
        ]
        missing_generated = [species_id for species_id in executed_species if generated.get(species_id, 0) <= 0]
        if missing_generated:
            raise Stage8SceneExecutionError(
                "Stage 8 scene execution produced no instances for species IDs: "
                + ", ".join(str(value) for value in missing_generated)
            )

        return {
            "forest": forest_result,
            "geometry": geometry_result,
            "manifest": manifest,
            "manifest_write": manifest_write,
            "execution": execution,
            "diagnostics": diagnostics,
            "generated_species_ids": sorted(set(executed_species)),
            "missing_generated_species_ids": missing_generated,
            "verified": True,
        }
