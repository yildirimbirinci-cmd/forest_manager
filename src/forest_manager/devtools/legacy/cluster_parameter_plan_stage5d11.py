from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


TARGET_ROUGHNESS_PERCENT = 35.0
TARGET_BLURRY_EDGE_PERCENT = 25.0
TARGET_NOISE_PERCENT = 10.0


def _candidate_map(response: dict) -> dict[str, object]:
    data = response.get("data") or {}
    return {
        item.get("name"): item.get("value")
        for item in (data.get("candidates") or [])
        if item.get("name")
    }


def main() -> int:
    try:
        ensure_current_bridge()
        mapping_response = send_command("GET_CLUSTER_PARAMETER_MAPPING")
        units_response = send_command("GET_SCENE_UNITS")
        composition_response = send_command("GET_COMPOSITION_CONTEXT")
    except Exception as exc:
        print("Stage 5D.11 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    for response in (mapping_response, units_response, composition_response):
        if not response.get("ok"):
            print(json.dumps(response, indent=2, ensure_ascii=False))
            return 3

    props = _candidate_map(mapping_response)
    required = ("divers", "clusize", "clurough", "clunoise", "cluedge")
    missing = [name for name in required if name not in props]
    if missing:
        print("Stage 5D.11 verification failed: missing properties:", ", ".join(missing))
        return 4

    units = units_response.get("data") or {}
    composition = composition_response.get("data") or {}
    density = composition.get("density") or {}
    geometry = composition.get("geometry") or {}

    one_meter = float(units.get("one_meter_system_units") or 0.0)
    if one_meter <= 0.0:
        print("Stage 5D.11 verification failed: invalid scene unit conversion.")
        return 5

    current_size_system = float(props["clusize"])
    current_size_meters = current_size_system / one_meter

    plan = {
        "policy": "natural_cluster_profile_v1",
        "read_only": True,
        "forest_name": composition.get("forest_name"),
        "diversity_mode": int(props["divers"]),
        "diversity_mode_name": "clusters" if int(props["divers"]) == 2 else "unexpected",
        "scene_units": {
            "display_type": units.get("display_type"),
            "display_unit": units.get("display_unit"),
            "system_type": units.get("system_type"),
            "system_scale": units.get("system_scale"),
            "one_meter_system_units": one_meter,
        },
        "current_cluster_parameters": {
            "size_system_units": current_size_system,
            "size_meters": current_size_meters,
            "roughness_percent": float(props["clurough"]),
            "blurry_edge_percent": float(props["cluedge"]),
            "noise_percent": float(props["clunoise"]),
        },
        "proposed_cluster_parameters": {
            "size_system_units": current_size_system,
            "size_meters": current_size_meters,
            "roughness_percent": TARGET_ROUGHNESS_PERCENT,
            "blurry_edge_percent": TARGET_BLURRY_EDGE_PERCENT,
            "noise_percent": TARGET_NOISE_PERCENT,
        },
        "reasoning": {
            "size": "Preserve the verified current cluster size for the first visual comparison.",
            "roughness": "Introduce moderate boundary irregularity without creating highly fragmented clusters.",
            "blurry_edge": "Soften cluster transitions while keeping masses visually readable.",
            "noise": "Add a small amount of out-of-cluster variation without dissolving the cluster structure.",
        },
        "protected_state": {
            "density_meters_x": float(density.get("meters_x") or 0.0),
            "density_meters_y": float(density.get("meters_y") or 0.0),
            "probabilities": geometry.get("probabilities") or [],
            "geometry_names": geometry.get("geometry_names") or [],
            "scale_variation": "preserve",
            "rotation": "preserve disabled",
            "translation": "preserve disabled",
        },
        "next_apply_scope": {
            "change_only": [
                "clurough: current -> 35.0",
                "cluedge: current -> 25.0",
                "clunoise: current -> 10.0",
            ],
            "preserve": [
                "divers = 2",
                "clusize current value",
                "75.0 m density",
                "geometry probabilities",
                "native scale variation",
                "rotation disabled",
                "translation disabled",
            ],
        },
        "verified": True,
    }

    print("Forest Manager Stage 5D.11 Cluster Parameter Plan Preview:")
    print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))
    print("Stage 5D.11 cluster parameter plan preview passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
