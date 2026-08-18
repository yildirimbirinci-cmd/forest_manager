from __future__ import annotations

import argparse
import json
import time

from forest_manager.forest_control.ai_scene_region_binding import (
    build_ai_scene_region_binding_plan,
)
from forest_manager.forest_control.scene_space_semantic_regions import (
    build_selected_boundary_semantic_region_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups-json", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    started = time.perf_counter()

    with open(args.groups_json, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        groups = (
            payload.get("plant_groups")
            or payload.get("groups")
            or payload.get("resolved_groups")
            or payload.get("manifest_groups")
        )
    else:
        groups = payload

    if not isinstance(groups, list):
        raise SystemExit("groups JSON must contain a list of plant groups.")

    region_plan = build_selected_boundary_semantic_region_plan(
        samples_per_spline=64,
        preflight=True,
    )
    binding_plan = build_ai_scene_region_binding_plan(
        plant_groups=groups,
        scene_region_plan=region_plan,
    )

    second = build_ai_scene_region_binding_plan(
        plant_groups=groups,
        scene_region_plan=region_plan,
    )

    checks = [
        {
            "name": "all_resolved_groups_bound",
            "passed": binding_plan["all_resolved_groups_bound"]
            and binding_plan["bound_group_count"] > 0,
            "detail": {
                "resolved_group_count": binding_plan["resolved_group_count"],
                "bound_group_count": binding_plan["bound_group_count"],
            },
        },
        {
            "name": "unresolved_groups_excluded",
            "passed": binding_plan["unresolved_groups_excluded"] is True,
            "detail": "groups_without_resolved_source_names_are_not_execution_ready",
        },
        {
            "name": "bindings_use_real_scene_regions",
            "passed": all(
                item["coordinate_source"] == "selected_3ds_max_boundary"
                and item["inside_site_polygon_required"] is True
                for item in binding_plan["bindings"]
            ),
            "detail": [
                {
                    "group_id": item["group_id"],
                    "semantic_role": item["semantic_role"],
                    "scene_region_role": item["scene_region_role"],
                    "source_names": item["source_names"],
                }
                for item in binding_plan["bindings"]
            ],
        },
        {
            "name": "reference_image_pixels_not_used",
            "passed": binding_plan["reference_image_coordinates_used"] is False
            and all(
                item["reference_image_coordinates_used"] is False
                for item in binding_plan["bindings"]
            ),
            "detail": binding_plan["reference_image_role"],
        },
        {
            "name": "binding_is_deterministic",
            "passed": binding_plan["binding_plan_id"] == second["binding_plan_id"]
            and binding_plan["bindings"] == second["bindings"],
            "detail": binding_plan["binding_plan_id"],
        },
        {
            "name": "forest_pack_not_mutated",
            "passed": binding_plan["forest_pack_mutated"] is False,
            "detail": "read_only_binding_plan",
        },
        {
            "name": "map_policy_parked",
            "passed": binding_plan["map_policy"]
            == "parked_not_projected_from_reference_image",
            "detail": binding_plan["map_policy"],
        },
    ]

    result = {
        "ok": all(item["passed"] for item in checks),
        "acceptance": "stage8_ai_scene_region_binding",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "node_name": binding_plan["node_name"],
        "binding_plan_id": binding_plan["binding_plan_id"],
        "orientation_source": binding_plan["orientation_source"],
        "site_front_confirmed": binding_plan["site_front_confirmed"],
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
