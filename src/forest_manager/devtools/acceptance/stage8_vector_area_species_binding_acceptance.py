from __future__ import annotations

import argparse
import json

from forest_manager.forest_control.ai_t2_scene_region_runtime import resolve_ai_t2_runtime_groups
from forest_manager.forest_control.scene_state import SceneStateGateway
from forest_manager.forest_control.service import ForestPackControlService
from forest_manager.forest_control.spline_world_space import read_selected_spline_world_space
from forest_manager.forest_control.vector_area_binding import execute_vector_area_species_binding
from forest_manager.forest_control.vector_region_helpers import sync_vector_region_helpers
from forest_manager.forest_control.wall_edge_annotations import read_wall_edge_annotation
from forest_manager.forest_control.wall_edge_zone_geometry import build_wall_edge_zone_geometry
from forest_manager.forest_control.wall_edge_zone_plan import build_wall_edge_zone_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-image", required=True)
    parser.add_argument("--wall-band-m", type=float, default=1.2)
    parser.add_argument("--walkway-band-m", type=float, default=0.6)
    parser.add_argument("--density-m", type=float, default=0.75)
    parser.add_argument("--min-generated-items", type=int, default=10)
    args = parser.parse_args()

    service = ForestPackControlService()
    geometry = read_selected_spline_world_space(samples_per_spline=64, preflight=True)
    scene_manifest = SceneStateGateway(service).read_manifest(preflight=True)
    annotation = read_wall_edge_annotation(scene_manifest, geometry.node_name)
    if annotation is None:
        raise RuntimeError(f"No persisted Wall Edge annotation for {geometry.node_name}.")

    zone_plan = build_wall_edge_zone_plan(
        geometry,
        annotation,
        wall_band_meters=args.wall_band_m,
        walkway_band_meters=args.walkway_band_m,
    )
    zones = build_wall_edge_zone_geometry(zone_plan)
    helpers = sync_vector_region_helpers(zones, preflight=False)

    resolution, groups, group_source = resolve_ai_t2_runtime_groups(args.reference_image)
    forest_name = str(scene_manifest.get("primary_forest") or "FM_Forest_001")
    first = execute_vector_area_species_binding(
        forest_name=forest_name,
        source_node_name=geometry.node_name,
        helper_names=helpers["after_helpers"],
        plant_groups=groups,
        service=service,
        density_meters=args.density_m,
        wall_band_meters=args.wall_band_m,
        walkway_band_meters=args.walkway_band_m,
        preflight=False,
    )
    second = execute_vector_area_species_binding(
        forest_name=forest_name,
        source_node_name=geometry.node_name,
        helper_names=helpers["after_helpers"],
        plant_groups=groups,
        service=service,
        density_meters=args.density_m,
        wall_band_meters=args.wall_band_m,
        walkway_band_meters=args.walkway_band_m,
        preflight=False,
    )

    runtime = second["runtime"]
    expected_count = len(helpers["after_helpers"])
    semantic_roles = {item["region_role"] for item in second["bindings"]}
    checks = [
        {
            "name": "ai_t2_groups_resolved",
            "passed": resolution.get("ok") is True and bool(groups),
            "detail": {"group_source": group_source, "group_count": len(groups)},
        },
        {
            "name": "all_vector_helpers_bound_as_areas",
            "passed": int(runtime.get("managed_area_count") or 0) == expected_count,
            "detail": runtime.get("areas"),
        },
        {
            "name": "wall_walkway_interior_species_bound",
            "passed": semantic_roles == {"wall", "walkway", "interior"}
            and all(item.get("species_ids") for item in second["bindings"]),
            "detail": second["bindings"],
        },
        {
            "name": "source_whole_area_disabled",
            "passed": int(runtime.get("source_area_disabled_count") or 0) >= 1,
            "detail": runtime.get("source_area_disabled_count"),
        },
        {
            "name": "second_execution_idempotent",
            "passed": int(runtime.get("managed_area_count") or 0) == expected_count
            and len(runtime.get("areas") or []) == expected_count,
            "detail": {
                "first_removed_previous": first["runtime"].get("removed_previous_managed_areas"),
                "second_removed_previous": runtime.get("removed_previous_managed_areas"),
            },
        },
        {
            "name": "oversized_sources_excluded_from_narrow_regions",
            "passed": all(
                all(float(item.get("footprint_meters") or 0.0) > float(item.get("fit_limit_meters") or 0.0)
                    for item in (binding.get("excluded_species") or []))
                for binding in second["bindings"]
            ),
            "detail": [
                {
                    "helper_name": binding.get("helper_name"),
                    "excluded_species": binding.get("excluded_species") or [],
                }
                for binding in second["bindings"]
                if binding.get("excluded_species")
            ],
        },
        {
            "name": "generated_items_visually_meaningful",
            "passed": int(runtime.get("generated_items") or 0) >= args.min_generated_items,
            "detail": {"generated_items": runtime.get("generated_items"), "minimum": args.min_generated_items},
        },
        {
            "name": "physical_spacing_exactly_applied",
            "passed": abs(float(runtime.get("physical_spacing_meters") or runtime.get("density_meters") or 0.0) - args.density_m) < 1e-9
            and float(runtime.get("density_units_x_system") or 0.0) > 0.0
            and float(runtime.get("density_units_y_system") or 0.0) > 0.0,
            "detail": {
                "physical_spacing_meters": runtime.get("physical_spacing_meters") or runtime.get("density_meters"),
                "distribution_pixels_x": runtime.get("distribution_pixels_x"),
                "distribution_pixels_y": runtime.get("distribution_pixels_y"),
                "density_units_x_system": runtime.get("density_units_x_system"),
                "density_units_y_system": runtime.get("density_units_y_system"),
            },
        },
        {
            "name": "no_distribution_map_or_reference_projection",
            "passed": runtime.get("distribution_map_used") is False
            and runtime.get("reference_image_coordinates_used") is False,
            "detail": {
                "distribution_map_used": runtime.get("distribution_map_used"),
                "reference_image_coordinates_used": runtime.get("reference_image_coordinates_used"),
            },
        },
    ]
    payload = {
        "ok": all(item["passed"] for item in checks),
        "acceptance": "stage8_vector_area_species_binding",
        "forest_name": forest_name,
        "node_name": geometry.node_name,
        "checks": checks,
        "binding": second,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
