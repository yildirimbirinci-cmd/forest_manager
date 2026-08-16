from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


CLUSTERS_DIVERSITY_MODE = 2


def main() -> int:
    try:
        ensure_current_bridge()
        mapping_response = send_command("GET_CLUSTER_PARAMETER_MAPPING")
        composition_response = send_command("GET_COMPOSITION_CONTEXT")
    except Exception as exc:
        print("Stage 5D.9 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    if not mapping_response.get("ok"):
        print(json.dumps(mapping_response, indent=2, ensure_ascii=False))
        return 3
    if not composition_response.get("ok"):
        print(json.dumps(composition_response, indent=2, ensure_ascii=False))
        return 4

    mapping = mapping_response.get("data") or {}
    composition = composition_response.get("data") or {}

    props = {
        item.get("name"): item.get("value")
        for item in (mapping.get("candidates") or [])
        if item.get("name")
    }

    required = ("clusize", "clurough", "clunoise", "cluedge", "divers")
    missing = [name for name in required if name not in props]
    if missing:
        print("Stage 5D.9 verification failed: missing properties:", ", ".join(missing))
        return 5

    density = composition.get("density") or {}
    geometry = composition.get("geometry") or {}

    plan = {
        "policy": "forestpack_clusters_native_mapping_v1",
        "read_only": True,
        "forest_name": composition.get("forest_name"),
        "current_diversity_mode": int(props["divers"]),
        "proposed_diversity_mode": CLUSTERS_DIVERSITY_MODE,
        "proposed_mode_name": "clusters",
        "cluster_parameters": {
            "size_system_units": float(props["clusize"]),
            "roughness_percent": float(props["clurough"]),
            "noise_percent": float(props["clunoise"]),
            "blurry_edge_percent": float(props["cluedge"]),
        },
        "protected_state": {
            "density_meters_x": float(density.get("meters_x") or 0.0),
            "density_meters_y": float(density.get("meters_y") or 0.0),
            "probabilities": geometry.get("probabilities") or [],
            "geometry_names": geometry.get("geometry_names") or [],
        },
        "next_apply_scope": {
            "change_only": ["divers: 0 -> 2"],
            "preserve": [
                "clusize",
                "clurough",
                "clunoise",
                "cluedge",
                "75.0 m density",
                "geometry probabilities",
                "native scale variation",
                "rotation disabled",
                "translation disabled",
            ],
        },
        "verified": True,
    }

    print("Forest Manager Stage 5D.9 Cluster Apply Plan Preview:")
    print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))
    print("Stage 5D.9 cluster apply plan preview passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
