from __future__ import annotations

from typing import Any, Mapping, Sequence, TYPE_CHECKING

from forest_manager.max_bridge.runtime_bridge import (
    bind_stage8_vector_region_areas,
    get_geometry_source_world_diagnostic,
)

if TYPE_CHECKING:
    from .service import ForestPackControlService


class VectorAreaBindingError(RuntimeError):
    pass


_WALL_ROLES = {
    "structural_shrub",
    "tree_canopy",
    "background_tree",
    "tall_structural",
}
_WALKWAY_ROLES = {
    "foreground_mass",
    "flower_accent",
    "purple_accent",
    "groundcover",
    "low_perennial",
}
_INTERIOR_ROLES = {
    "mid_accent",
    "mixed_perennial",
    "midground",
    "interior_mix",
}


def _semantic_role(group: Mapping[str, Any]) -> str:
    for key in ("semantic_role", "role", "group_role", "planting_role"):
        value = str(group.get(key) or "").strip()
        if value:
            return value
    group_id = str(group.get("group_id") or group.get("id") or "").strip()
    if ":" in group_id:
        return group_id.rsplit(":", 1)[-1].strip()
    return ""


def _source_names(group: Mapping[str, Any]) -> tuple[str, ...]:
    for key in ("source_names", "resolved_source_names", "sources", "geometry_sources"):
        values = group.get(key)
        if isinstance(values, str):
            values = [values]
        if isinstance(values, (list, tuple)):
            result = tuple(str(value).strip() for value in values if str(value).strip())
            if result:
                return result
    for key in ("source_name", "resolved_source_name", "geometry_source"):
        value = str(group.get(key) or "").strip()
        if value:
            return (value,)
    return ()


def _source_species_map(forest_name: str, service: "ForestPackControlService") -> dict[str, int]:
    from .geometry import GeometrySourcesAdapter
    adapter = GeometrySourcesAdapter(service)
    inventory = service.inventory(forest_name, preflight=False)
    cobj = next(
        (item for item in inventory.get("properties") or [] if isinstance(item, dict) and item.get("name") == "cobjlist"),
        None,
    )
    metadata = cobj.get("array_metadata") if isinstance(cobj, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    result: dict[str, int] = {}
    for index in range(1, count + 1):
        record = adapter.read_record(forest_name, index)
        species_id = int(record.species_id or index)
        if record.source_node:
            result[str(record.source_node)] = species_id
        if record.name:
            result.setdefault(str(record.name), species_id)
    return result


def _bucket_for_role(role: str) -> str | None:
    if role in _WALL_ROLES:
        return "wall"
    if role in _WALKWAY_ROLES:
        return "walkway"
    if role in _INTERIOR_ROLES:
        return "interior"
    return None


def _apply_region_footprint_guard(
    *,
    forest_name: str,
    bucket_species: dict[str, list[int]],
    wall_band_meters: float,
    walkway_band_meters: float,
) -> tuple[dict[str, list[int]], dict[str, list[dict[str, Any]]]]:
    species_ids = sorted({sid for values in bucket_species.values() for sid in values})
    if not species_ids:
        return bucket_species, {"wall": [], "walkway": [], "interior": []}
    diagnostic = get_geometry_source_world_diagnostic(forest_name, species_ids, preflight=False)
    units = diagnostic.get("scene_units") or {}
    one_meter = float(units.get("one_meter_system_units") or 0.0)
    if one_meter <= 0.0:
        raise VectorAreaBindingError("Geometry source diagnostic did not provide valid scene unit conversion.")
    by_id = {int(item.get("species_id")): item for item in (diagnostic.get("items") or []) if item.get("species_id")}
    filtered = {key: list(values) for key, values in bucket_species.items()}
    excluded: dict[str, list[dict[str, Any]]] = {"wall": [], "walkway": [], "interior": []}
    limits = {
        "wall": max(float(wall_band_meters) * 4.0, 3.0),
        "walkway": max(float(walkway_band_meters) * 4.0, 2.0),
    }
    for bucket in ("wall", "walkway"):
        kept: list[int] = []
        for species_id in filtered[bucket]:
            item = by_id.get(species_id)
            if not item or item.get("bounds_ok") is not True:
                kept.append(species_id)
                continue
            footprint_m = max(float(item.get("width_system") or 0.0), float(item.get("depth_system") or 0.0)) / one_meter
            if footprint_m <= limits[bucket]:
                kept.append(species_id)
            else:
                excluded[bucket].append({
                    "species_id": species_id,
                    "source_node": item.get("source_node"),
                    "footprint_meters": round(footprint_m, 6),
                    "fit_limit_meters": round(limits[bucket], 6),
                    "reason": "source_footprint_exceeds_region_fit_limit",
                })
        if not kept:
            raise VectorAreaBindingError(
                f"Region-fit guard removed all resolved species from {bucket}; "
                f"band_m={wall_band_meters if bucket == 'wall' else walkway_band_meters}"
            )
        filtered[bucket] = kept
    return filtered, excluded


def build_vector_area_species_bindings(
    *,
    forest_name: str,
    source_node_name: str,
    helper_names: Sequence[str],
    plant_groups: Sequence[Mapping[str, Any]],
    service: "ForestPackControlService | None" = None,
    wall_band_meters: float | None = None,
    walkway_band_meters: float | None = None,
) -> list[dict[str, Any]]:
    if service is None:
        from .service import ForestPackControlService
        service = ForestPackControlService()
    svc = service
    source_to_species = _source_species_map(forest_name, svc)

    bucket_species: dict[str, list[int]] = {"wall": [], "walkway": [], "interior": []}
    unresolved_sources: list[str] = []
    unsupported_roles: list[str] = []
    role_species: dict[str, list[int]] = {}

    for group in plant_groups:
        role = _semantic_role(group)
        bucket = _bucket_for_role(role)
        if bucket is None:
            if role:
                unsupported_roles.append(role)
            continue
        names = _source_names(group)
        if not names:
            continue
        for name in names:
            species_id = source_to_species.get(name)
            if species_id is None:
                unresolved_sources.append(name)
                continue
            if species_id not in bucket_species[bucket]:
                bucket_species[bucket].append(species_id)
            role_species.setdefault(role, [])
            if species_id not in role_species[role]:
                role_species[role].append(species_id)

    if unresolved_sources:
        raise VectorAreaBindingError(
            "Resolved AI/T2 source is missing from FM_Forest_001 Geometry List: "
            + ", ".join(sorted(set(unresolved_sources)))
        )
    # Interior is allowed to reuse already-resolved low/flowering species when the
    # vision result has no dedicated mid/interior semantic group. This keeps the
    # plan grounded in the actual T2-resolved sources and deliberately excludes
    # structural shrubs/trees from automatic interior fallback.
    if not bucket_species["interior"]:
        for fallback_role in (
            "flower_accent",
            "foreground_mass",
            "purple_accent",
            "groundcover",
            "low_perennial",
        ):
            for species_id in role_species.get(fallback_role, []):
                if species_id not in bucket_species["interior"]:
                    bucket_species["interior"].append(species_id)

    excluded_by_bucket: dict[str, list[dict[str, Any]]] = {"wall": [], "walkway": [], "interior": []}
    if wall_band_meters is not None and walkway_band_meters is not None:
        bucket_species, excluded_by_bucket = _apply_region_footprint_guard(
            forest_name=forest_name,
            bucket_species=bucket_species,
            wall_band_meters=wall_band_meters,
            walkway_band_meters=walkway_band_meters,
        )

    missing = [name for name, values in bucket_species.items() if not values]
    if missing:
        raise VectorAreaBindingError(
            "Semantic vector Area bucket has no resolved species: " + ", ".join(missing)
            + ("; unsupported_roles=" + ",".join(sorted(set(unsupported_roles))) if unsupported_roles else "")
        )

    prefix = f"FM_Region_{source_node_name}_"
    bindings: list[dict[str, Any]] = []
    for helper_name in helper_names:
        helper = str(helper_name).strip()
        if not helper.startswith(prefix):
            raise VectorAreaBindingError(f"Helper is outside the managed source prefix: {helper}")
        if "_Wall_" in helper:
            bucket = "wall"
        elif "_Walkway_" in helper:
            bucket = "walkway"
        elif "_Interior_" in helper:
            bucket = "interior"
        else:
            raise VectorAreaBindingError(f"Helper has no recognized semantic region role: {helper}")
        bindings.append(
            {
                "helper_name": helper,
                "region_role": bucket,
                "species_ids": list(bucket_species[bucket]),
                "excluded_species": list(excluded_by_bucket.get(bucket) or []),
            }
        )

    if not bindings:
        raise VectorAreaBindingError("No vector helper bindings were produced.")
    return bindings


def execute_vector_area_species_binding(
    *,
    forest_name: str,
    source_node_name: str,
    helper_names: Sequence[str],
    plant_groups: Sequence[Mapping[str, Any]],
    service: "ForestPackControlService | None" = None,
    density_meters: float = 0.75,
    wall_band_meters: float = 1.2,
    walkway_band_meters: float = 0.6,
    preflight: bool = True,
) -> dict[str, Any]:
    bindings = build_vector_area_species_bindings(
        forest_name=forest_name,
        source_node_name=source_node_name,
        helper_names=helper_names,
        plant_groups=plant_groups,
        service=service,
        wall_band_meters=wall_band_meters,
        walkway_band_meters=walkway_band_meters,
    )
    result = bind_stage8_vector_region_areas(
        forest_name,
        source_node_name,
        bindings,
        density_meters=density_meters,
        preflight=preflight,
    )
    if result.get("distribution_map_used") is not False:
        raise VectorAreaBindingError("Stage 8 vector Area binding unexpectedly used a Distribution Map.")
    if result.get("reference_image_coordinates_used") is not False:
        raise VectorAreaBindingError("Stage 8 vector Area binding used reference-image scene coordinates.")
    return {"verified": True, "bindings": bindings, "runtime": result}
