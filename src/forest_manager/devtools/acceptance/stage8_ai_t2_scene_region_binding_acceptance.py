from __future__ import annotations

import argparse
import json
import time

from forest_manager.forest_control.ai_scene_region_binding import (
    build_ai_scene_region_binding_plan,
)
from forest_manager.forest_control.ai_t2_scene_region_runtime import (
    resolve_ai_t2_runtime_groups,
)
from forest_manager.forest_control.scene_space_semantic_regions import (
    build_selected_boundary_semantic_region_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-image", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    started = time.perf_counter()

    resolution, groups, group_source = resolve_ai_t2_runtime_groups(
        args.reference_image
    )
    region_plan = build_selected_boundary_semantic_region_plan(
        samples_per_spline=64,
        preflight=True,
    )
    binding = build_ai_scene_region_binding_plan(
        plant_groups=groups,
        scene_region_plan=region_plan,
    )
    second = build_ai_scene_region_binding_plan(
        plant_groups=groups,
        scene_region_plan=region_plan,
    )

    runtime_group_ids = {str(item.get("group_id") or "") for item in groups}
    bound_group_ids = {str(item.get("group_id") or "") for item in binding["bindings"]}

    checks = [
        {
            "name": "ai_t2_resolution_verified",
            "passed": resolution.get("ok") is True,
            "detail": {
                "stage": resolution.get("stage") or resolution.get("acceptance"),
                "resolved_group_count": resolution.get("resolved_group_count"),
                "group_source": group_source,
            },
        },
        {
            "name": "runtime_groups_are_resolved_sources",
            "passed": len(groups) == binding["resolved_group_count"]
            and all(item.get("source_names") for item in groups),
            "detail": [
                {
                    "group_id": item.get("group_id"),
                    "semantic_role": item.get("semantic_role"),
                    "source_names": item.get("source_names"),
                }
                for item in groups
            ],
        },
        {
            "name": "all_runtime_resolved_groups_bound",
            "passed": runtime_group_ids == bound_group_ids
            and binding["all_resolved_groups_bound"] is True
            and binding["resolved_group_count"] == binding["bound_group_count"],
            "detail": {
                "runtime_group_ids": sorted(runtime_group_ids),
                "bound_group_ids": sorted(bound_group_ids),
            },
        },
        {
            "name": "real_line_scene_regions_used",
            "passed": binding["coordinate_source"] == "selected_3ds_max_boundary"
            and binding["node_name"] == region_plan["node_name"]
            and all(
                item["inside_site_polygon_required"] is True
                for item in binding["bindings"]
            ),
            "detail": {
                "node_name": binding["node_name"],
                "orientation_source": binding["orientation_source"],
                "site_front_confirmed": binding["site_front_confirmed"],
            },
        },
        {
            "name": "reference_image_pixels_not_projected",
            "passed": binding["reference_image_coordinates_used"] is False
            and region_plan["reference_image_coordinates_used"] is False,
            "detail": "reference_image_is_semantic_guidance_only",
        },
        {
            "name": "binding_is_deterministic",
            "passed": binding["binding_plan_id"] == second["binding_plan_id"]
            and binding["bindings"] == second["bindings"],
            "detail": binding["binding_plan_id"],
        },
        {
            "name": "forest_pack_not_mutated_by_binding_stage",
            "passed": binding["forest_pack_mutated"] is False
            and region_plan["forest_pack_mutated"] is False,
            "detail": "read_only_scene_region_binding",
        },
        {
            "name": "map_policy_parked",
            "passed": binding["map_policy"]
            == "parked_not_projected_from_reference_image",
            "detail": binding["map_policy"],
        },
    ]

    result = {
        "ok": all(bool(item["passed"]) for item in checks),
        "acceptance": "stage8_ai_t2_scene_region_binding",
        "reference_image": args.reference_image,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "node_name": binding["node_name"],
        "binding_plan_id": binding["binding_plan_id"],
        "resolved_group_count": binding["resolved_group_count"],
        "bound_group_count": binding["bound_group_count"],
        "group_source": group_source,
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
