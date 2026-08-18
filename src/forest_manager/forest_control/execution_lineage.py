from __future__ import annotations

from typing import Any


class ExecutionLineageError(RuntimeError):
    pass


def build_execution_lineage(*, plan: Any, ai_asset_resolution: list[dict[str, Any]], geometry_result: dict[str, Any], execution: dict[str, Any], diagnostics: dict[str, Any], color_id_results: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    resolution_by_group = {str(item.get("group_id") or ""): item for item in ai_asset_resolution if isinstance(item, dict) and str(item.get("group_id") or "")}
    source_name_map = {str(key): str(value) for key, value in (geometry_result.get("source_name_map") or {}).items() if str(key) and str(value)}
    execution_by_group = {str(item.get("group_id") or ""): item for item in execution.get("groups") or [] if isinstance(item, dict) and str(item.get("group_id") or "")}
    generated_by_species = {int(item.get("species_id") or 0): int(item.get("generated_items") or 0) for item in diagnostics.get("generated_geometry_ids") or [] if isinstance(item, dict) and int(item.get("species_id") or 0) > 0}
    configured_species = {int(value) for value in diagnostics.get("configured_species_ids") or [] if int(value) > 0}
    map_free_mode = execution.get("map_source_kind") == "disabled_map_free"
    structural_binding_mode = map_free_mode or (not generated_by_species and diagnostics.get("species_binding_verified") is True)
    generated_total = int(diagnostics.get("generated_items") or 0)
    color_by_species: dict[int, tuple[int, int, int]] = {}


    lineage: list[dict[str, Any]] = []
    seen_species: set[int] = set()
    for group in plan.groups:
        group_id = str(group.group_id)
        resolution = resolution_by_group.get(group_id)
        if resolution is None:
            raise ExecutionLineageError(f"Missing AI asset resolution lineage for group '{group_id}'.")
        expected_asset_path = str(group.resolved_asset_path or "").strip()
        resolved_asset_path = str(resolution.get("resolved_asset_path") or "").strip()
        if not expected_asset_path:
            raise ExecutionLineageError(f"Resolved group '{group_id}' has no exact T2 asset path in the prepared plan.")
        if not resolved_asset_path:
            raise ExecutionLineageError(f"AI asset resolution lineage has no exact T2 asset path for '{group_id}'.")
        if expected_asset_path != resolved_asset_path:
            raise ExecutionLineageError(f"AI asset lineage mismatch for '{group_id}': plan={expected_asset_path} resolver={resolved_asset_path}")
        requested_sources = [str(value) for value in group.source_names if str(value).strip()]
        if not requested_sources:
            raise ExecutionLineageError(f"Resolved group '{group_id}' has no source name.")
        actual_sources = [source_name_map.get(name, name) for name in requested_sources]
        executed = execution_by_group.get(group_id)
        if executed is None:
            raise ExecutionLineageError(f"Forest execution omitted plant group '{group_id}'.")
        species_ids = [int(value) for value in executed.get("species_ids") or [] if int(value) > 0]
        if not species_ids:
            raise ExecutionLineageError(f"Forest execution produced no species IDs for '{group_id}'.")
        duplicated = [value for value in species_ids if value in seen_species]
        if duplicated:
            raise ExecutionLineageError(f"Forest species IDs are shared across plant groups unexpectedly: group={group_id} species={duplicated}")
        seen_species.update(species_ids)
        if structural_binding_mode:
            missing_configured = [value for value in species_ids if value not in configured_species]
            if missing_configured:
                raise ExecutionLineageError(
                    f"Forest execution species are not present in the verified Single-Forest binding: group={group_id} species={missing_configured}"
                )
            if generated_total <= 0:
                raise ExecutionLineageError("Forest execution generated no items for the verified Single-Forest binding.")
            generated_items: int | None = None
        else:
            generated_items = sum(generated_by_species.get(value, 0) for value in species_ids)
            if generated_items <= 0:
                raise ExecutionLineageError(f"Forest execution generated no instances for plant group '{group_id}' species={species_ids}.")
        colors: list[tuple[int, int, int]] = []
        lineage.append({
            "group_id": group_id,
            "label": group.label,
            "resolved_asset_path": resolved_asset_path or expected_asset_path,
            "requested_source_names": requested_sources,
            "scene_source_names": actual_sources,
            "species_ids": species_ids,
            "generated_items": generated_items,
            "generated_item_verification_mode": "map_free_total_binding" if map_free_mode else ("single_forest_binding" if structural_binding_mode else "per_species_runtime"),
            "color_ids": [],
            "diversity_binding_mode": "map_free_random",
            "model_match_confidence": float(group.model_match_confidence),
            "verified": True,
        })
    if len(lineage) != len(plan.groups):
        raise ExecutionLineageError(f"Execution lineage count mismatch: planned={len(plan.groups)} verified={len(lineage)}")
    return lineage
