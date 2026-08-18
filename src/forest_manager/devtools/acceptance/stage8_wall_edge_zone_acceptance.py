from __future__ import annotations

import argparse
import json

from forest_manager.forest_control.scene_state import SceneStateGateway
from forest_manager.forest_control.service import ForestPackControlService
from forest_manager.forest_control.spline_world_space import read_selected_spline_world_space
from forest_manager.forest_control.wall_edge_annotations import read_wall_edge_annotation
from forest_manager.forest_control.wall_edge_zone_plan import build_wall_edge_zone_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wall-band-m", type=float, required=True)
    parser.add_argument("--walkway-band-m", type=float, required=True)
    args = parser.parse_args()

    service = ForestPackControlService()
    geometry = read_selected_spline_world_space(samples_per_spline=64, preflight=True)
    manifest = SceneStateGateway(service).read_manifest(preflight=True)
    annotation = read_wall_edge_annotation(manifest, geometry.node_name)
    if annotation is None:
        raise RuntimeError(f"No persisted Wall Edge annotation for {geometry.node_name}.")

    plan = build_wall_edge_zone_plan(
        geometry,
        annotation,
        wall_band_meters=args.wall_band_m,
        walkway_band_meters=args.walkway_band_m,
    )
    checks = [
        {
            "name": "artist_wall_edge_consumed",
            "passed": plan["roles"]["wall_segments"] == list(annotation.wall_segments),
            "detail": plan["roles"],
        },
        {
            "name": "remaining_edges_are_walkway_open",
            "passed": plan["roles"]["walkway_open_segments"] == list(annotation.walkway_open_segments),
            "detail": plan["roles"],
        },
        {
            "name": "scene_units_preserved",
            "passed": float(plan["scene_units"].get("one_meter_system_units") or 0.0) > 0.0,
            "detail": plan["scene_units"],
        },
        {
            "name": "vector_only_no_distribution_map",
            "passed": plan["distribution_map_used"] is False and plan["reference_image_coordinates_used"] is False,
            "detail": {
                "distribution_map_used": plan["distribution_map_used"],
                "reference_image_coordinates_used": plan["reference_image_coordinates_used"],
                "forest_pack_mutated": plan["forest_pack_mutated"],
            },
        },
    ]
    payload = {
        "ok": all(item["passed"] for item in checks),
        "acceptance": "stage8_wall_edge_zone",
        "node_name": plan["node_name"],
        "checks": checks,
        "plan": plan,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
