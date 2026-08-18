from __future__ import annotations

import argparse
import json

from forest_manager.forest_control.scene_state import SceneStateGateway
from forest_manager.forest_control.service import ForestPackControlService
from forest_manager.forest_control.spline_world_space import read_selected_spline_world_space
from forest_manager.forest_control.vector_region_helpers import sync_vector_region_helpers
from forest_manager.forest_control.wall_edge_annotations import read_wall_edge_annotation
from forest_manager.forest_control.wall_edge_zone_geometry import build_wall_edge_zone_geometry
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
    zones = build_wall_edge_zone_geometry(plan)
    first = sync_vector_region_helpers(zones, preflight=True)
    second = sync_vector_region_helpers(zones, preflight=False)
    checks = [
        {"name": "helper_splines_created", "passed": len(first["after_helpers"]) >= 3, "detail": first["after_helpers"]},
        {"name": "second_sync_idempotent", "passed": second["after_helpers"] == first["after_helpers"], "detail": second},
        {"name": "managed_names_only", "passed": all(name.startswith(f"FM_Region_{geometry.node_name}_") for name in second["after_helpers"]), "detail": second["after_helpers"]},
        {"name": "helper_layer_hidden_and_verified", "passed": second.get("helper_layer", {}).get("layer_name") == "FM_HELPERS" and second.get("helper_layer", {}).get("hidden") is True and second.get("helper_layer", {}).get("verified") is True, "detail": second.get("helper_layer")},
        {"name": "forest_pack_not_mutated", "passed": second["forest_pack_mutated"] is False, "detail": {"forest_pack_mutated": second["forest_pack_mutated"], "distribution_map_used": second["distribution_map_used"]}},
    ]
    payload = {"ok": all(c["passed"] for c in checks), "acceptance": "stage8_vector_region_helpers", "node_name": geometry.node_name, "checks": checks, "sync": second}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
