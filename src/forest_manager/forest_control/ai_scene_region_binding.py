from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


class AISceneRegionBindingError(RuntimeError):
    pass


ROLE_TO_REGION = {
    "foreground_mass": "foreground",
    "mid_accent": "midground",
    "purple_accent": "midground",
    "flower_accent": "midground",
    "structural_shrub": "background",
}


@dataclass(frozen=True)
class ResolvedPlantGroup:
    group_id: str
    semantic_role: str
    source_names: tuple[str, ...]
    raw: Mapping[str, Any]


def _as_nonempty_strings(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return ()
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _semantic_role(group: Mapping[str, Any]) -> str:
    for key in ("semantic_role", "role", "group_role", "planting_role"):
        value = str(group.get(key) or "").strip()
        if value:
            return value
    group_id = str(group.get("group_id") or group.get("id") or "").strip()
    if ":" in group_id:
        tail = group_id.rsplit(":", 1)[-1].strip()
        if tail:
            return tail
    return ""


def _source_names(group: Mapping[str, Any]) -> tuple[str, ...]:
    for key in ("source_names", "resolved_source_names", "sources", "geometry_sources"):
        names = _as_nonempty_strings(group.get(key))
        if names:
            return names

    source_name = str(
        group.get("source_name")
        or group.get("resolved_source_name")
        or group.get("geometry_source")
        or ""
    ).strip()
    return (source_name,) if source_name else ()


def _group_id(group: Mapping[str, Any], index: int) -> str:
    value = str(group.get("group_id") or group.get("id") or "").strip()
    return value or f"plant_group:{index + 1}"


def extract_resolved_groups(groups: Iterable[Mapping[str, Any]]) -> tuple[ResolvedPlantGroup, ...]:
    resolved = []
    for index, group in enumerate(groups):
        names = _source_names(group)
        if not names:
            continue
        role = _semantic_role(group)
        if not role:
            raise AISceneRegionBindingError(
                f"Resolved plant group {_group_id(group, index)} has no semantic role."
            )
        resolved.append(
            ResolvedPlantGroup(
                group_id=_group_id(group, index),
                semantic_role=role,
                source_names=names,
                raw=group,
            )
        )
    return tuple(resolved)


def _region_index(scene_region_plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    regions = scene_region_plan.get("regions")
    if not isinstance(regions, list) or not regions:
        raise AISceneRegionBindingError("Scene region plan contains no semantic regions.")

    result: dict[str, Mapping[str, Any]] = {}
    for region in regions:
        if not isinstance(region, Mapping):
            raise AISceneRegionBindingError("Invalid scene region record.")
        role = str(region.get("semantic_role") or "").strip()
        if not role:
            raise AISceneRegionBindingError("Scene region has no semantic role.")
        if role in result:
            raise AISceneRegionBindingError(f"Duplicate scene region role: {role}")
        if region.get("inside_site_polygon_required") is not True:
            raise AISceneRegionBindingError(
                f"Scene region {role} is not constrained to the site polygon."
            )
        result[role] = region
    return result


def _binding_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def build_ai_scene_region_binding_plan(
    *,
    plant_groups: Sequence[Mapping[str, Any]],
    scene_region_plan: Mapping[str, Any],
) -> dict[str, Any]:
    if scene_region_plan.get("verified") is not True:
        raise AISceneRegionBindingError("Scene region plan is not verified.")
    if scene_region_plan.get("reference_image_coordinates_used") is not False:
        raise AISceneRegionBindingError(
            "Scene region plan must not contain projected reference-image coordinates."
        )
    if scene_region_plan.get("forest_pack_mutated") is not False:
        raise AISceneRegionBindingError(
            "Binding planning requires the read-only semantic region stage."
        )

    regions = _region_index(scene_region_plan)
    resolved_groups = extract_resolved_groups(plant_groups)
    if not resolved_groups:
        raise AISceneRegionBindingError("No resolved plant groups are available for binding.")

    bindings = []
    for group in resolved_groups:
        target_region = ROLE_TO_REGION.get(group.semantic_role)
        if target_region is None:
            raise AISceneRegionBindingError(
                "No approved scene-region binding exists for semantic role: "
                + group.semantic_role
            )
        region = regions.get(target_region)
        if region is None:
            raise AISceneRegionBindingError(
                f"Required scene region is missing: {target_region}"
            )

        bindings.append(
            {
                "group_id": group.group_id,
                "semantic_role": group.semantic_role,
                "source_names": list(group.source_names),
                "scene_region_role": target_region,
                "scene_region_id": str(region.get("region_id") or ""),
                "region_constraint_type": str(region.get("constraint_type") or ""),
                "normalized_depth_interval": dict(
                    region.get("normalized_depth_interval") or {}
                ),
                "inside_site_polygon_required": True,
                "coordinate_source": "selected_3ds_max_boundary",
                "reference_image_coordinates_used": False,
                "execution_ready": True,
            }
        )

    bindings.sort(key=lambda item: (item["group_id"], item["semantic_role"], item["source_names"]))

    core = {
        "node_name": str(scene_region_plan.get("node_name") or ""),
        "coordinate_system": str(scene_region_plan.get("coordinate_system") or ""),
        "orientation_source": str(scene_region_plan.get("orientation_source") or ""),
        "site_front_confirmed": bool(scene_region_plan.get("site_front_confirmed")),
        "bindings": bindings,
    }

    return {
        "verified": True,
        **core,
        "binding_plan_id": "ai_scene_binding:" + _binding_hash(core)[:20],
        "resolved_group_count": len(resolved_groups),
        "bound_group_count": len(bindings),
        "all_resolved_groups_bound": len(resolved_groups) == len(bindings),
        "unresolved_groups_excluded": True,
        "reference_image_role": "semantic_composition_guidance_only",
        "reference_image_coordinates_used": False,
        "coordinate_source": "selected_3ds_max_boundary",
        "forest_pack_mutated": False,
        "map_policy": "parked_not_projected_from_reference_image",
    }
