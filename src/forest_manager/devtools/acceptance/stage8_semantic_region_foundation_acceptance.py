from __future__ import annotations

import argparse
import json
import time

from forest_manager.forest_control.scene_space_semantic_regions import (
    build_selected_boundary_semantic_region_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front-x", type=float, default=None)
    parser.add_argument("--front-y", type=float, default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if (args.front_x is None) != (args.front_y is None):
        raise SystemExit("--front-x and --front-y must be provided together.")

    front_hint = None
    if args.front_x is not None:
        front_hint = (args.front_x, args.front_y)

    started = time.perf_counter()
    result = build_selected_boundary_semantic_region_plan(
        samples_per_spline=64,
        front_hint_world_xy=front_hint,
        preflight=True,
    )
    polygon = result["site_polygon"]
    regions = result["regions"]

    checks = [
        {
            "name": "real_scene_polygon_verified",
            "passed": polygon["source"] == "selected_3ds_max_spline_world_samples"
            and polygon["sample_count"] >= 8
            and polygon["winding"] == "ccw",
            "detail": {
                "node_name": result["node_name"],
                "sample_count": polygon["sample_count"],
            },
        },
        {
            "name": "polygon_area_positive",
            "passed": float(polygon["area_system_units2"]) > 0.0,
            "detail": {
                "area_system_units2": polygon["area_system_units2"],
                "area_m2": polygon["area_m2"],
            },
        },
        {
            "name": "three_semantic_depth_regions",
            "passed": [item["semantic_role"] for item in regions]
            == ["foreground", "midground", "background"],
            "detail": [
                {
                    "semantic_role": item["semantic_role"],
                    "normalized_depth_interval": item["normalized_depth_interval"],
                }
                for item in regions
            ],
        },
        {
            "name": "regions_remain_constrained_to_site_polygon",
            "passed": all(item["inside_site_polygon_required"] for item in regions),
            "detail": "polygon intersection + depth projection interval",
        },
        {
            "name": "orientation_is_explicitly_provenanced",
            "passed": result["orientation_source"]
            in {"explicit_front_hint", "deterministic_minor_geometry_axis"},
            "detail": {
                "orientation_source": result["orientation_source"],
                "site_front_confirmed": result["site_front_confirmed"],
                "depth_axis_world_xy": result["semantic_depth_axis_world_xy"],
            },
        },
        {
            "name": "reference_image_pixels_not_used",
            "passed": result["reference_image_coordinates_used"] is False
            and all(item["reference_image_coordinates_used"] is False for item in regions),
            "detail": result["reference_image_role"],
        },
        {
            "name": "forest_pack_not_mutated",
            "passed": result["forest_pack_mutated"] is False,
            "detail": "read_only_semantic_plan",
        },
        {
            "name": "map_policy_parked",
            "passed": result["map_policy"] == "parked_not_projected_from_reference_image",
            "detail": result["map_policy"],
        },
    ]

    payload = {
        "ok": all(item["passed"] for item in checks),
        "acceptance": "stage8_semantic_region_foundation",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "node_name": result["node_name"],
        "orientation_source": result["orientation_source"],
        "site_front_confirmed": result["site_front_confirmed"],
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
