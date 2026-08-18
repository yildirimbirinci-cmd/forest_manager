from __future__ import annotations

import json
import time

from forest_manager.forest_control.scene_space_distribution import (
    build_scene_space_boundary_foundation,
)


def main() -> int:
    started = time.perf_counter()
    result = build_scene_space_boundary_foundation(preflight=True)
    boundary = result["boundary"]

    checks = [
        {
            "name": "selected_scene_boundary_verified",
            "passed": bool(result.get("verified")),
            "detail": boundary.get("node_name"),
        },
        {
            "name": "closed_spline_boundary",
            "passed": bool(boundary.get("all_splines_closed")) and int(boundary.get("spline_count") or 0) > 0,
            "detail": {
                "spline_count": boundary.get("spline_count"),
                "node_class": boundary.get("node_class"),
            },
        },
        {
            "name": "scene_space_dimensions_positive",
            "passed": float(boundary.get("width_system_units") or 0.0) > 0.0
            and float(boundary.get("depth_system_units") or 0.0) > 0.0,
            "detail": {
                "width_system_units": boundary.get("width_system_units"),
                "depth_system_units": boundary.get("depth_system_units"),
                "width_meters": boundary.get("width_meters"),
                "depth_meters": boundary.get("depth_meters"),
            },
        },
        {
            "name": "scene_unit_context_preserved",
            "passed": float((boundary.get("scene_units") or {}).get("one_meter_system_units") or 0.0) > 0.0,
            "detail": boundary.get("scene_units"),
        },
        {
            "name": "reference_image_not_projected",
            "passed": boundary.get("reference_image_projection") is False
            and result.get("distribution_policy") == "scene_geometry_only",
            "detail": result.get("reference_image_role"),
        },
        {
            "name": "exact_polygon_remap_blocked_until_vertices",
            "passed": result.get("exact_polygon_remap_ready") is False
            and result.get("next_requirement") == "bridge_world_space_spline_vertex_sampling",
            "detail": "Bounding-box measurements are foundation evidence only; they are not a scene-space mask.",
        },
        {
            "name": "read_only_acceptance",
            "passed": result.get("scene_mutated") is False,
            "detail": "GET_SELECTION_MEASUREMENTS",
        },
        {
            "name": "map_policy_parked",
            "passed": result.get("map_policy") == "parked_not_projected_from_reference_image",
            "detail": result.get("map_policy"),
        },
    ]

    payload = {
        "ok": all(bool(item["passed"]) for item in checks),
        "acceptance": "stage8_scene_space_boundary_foundation",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
        "boundary": boundary,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
