from __future__ import annotations

import json
import re
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return cleaned[:32] or "Species"


def _role_for(name: str) -> str:
    lower = name.lower()
    if "lavand" in lower:
        return "foreground_mass"
    if "butom" in lower or "flower" in lower:
        return "mid_accent"
    if "berber" in lower or "bush" in lower or "shrub" in lower:
        return "structural_shrub"
    return "species_layer"


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_SPECIES_LAYER_CONTEXT")
    except Exception as exc:
        print("Stage 5D.14 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.14 Species Layer Architecture Preview:")

    if not response.get("ok"):
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 3

    data = response.get("data") or {}
    names = list(data.get("geometry_names") or [])
    sources = list(data.get("source_names") or [])
    probabilities = list(data.get("probabilities") or [])

    if len(names) != 3 or len(probabilities) != 3:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        print("Stage 5D.14 requires the verified three-species baseline.")
        return 4

    layers = []
    for index, name in enumerate(names):
        source = sources[index] if index < len(sources) else None
        probability = probabilities[index]
        role = _role_for(name)
        layers.append(
            {
                "layer_index": index + 1,
                "species_name": name,
                "source_name": source,
                "current_probability": probability,
                "role": role,
                "proposed_forest_name": f"FM_Layer_{index + 1:02d}_{_slug(role)}",
                "geometry_policy": "one source species per Forest layer",
                "area_policy": "reuse the same verified spline-area references",
                "distribution_policy": "independent per-species distribution and cluster controls",
            }
        )

    plan = {
        "policy": "multi_forest_species_layers_v1",
        "mode": "preview",
        "read_only": True,
        "source_forest": data.get("forest_name"),
        "why_split": (
            "Forest Pack diversity/cluster parameters are global to one Forest object. "
            "Independent species spatial behavior therefore requires independent Forest layers."
        ),
        "current_state": {
            "geometry_count": data.get("geometry_count"),
            "geometry_names": names,
            "source_names": sources,
            "probabilities": probabilities,
            "area_count": data.get("area_count"),
            "area_names": data.get("area_names") or [],
            "density_meters_x": data.get("density_meters_x"),
            "density_meters_y": data.get("density_meters_y"),
            "cluster_size_meters": data.get("cluster_size_meters"),
            "clurough": data.get("clurough"),
            "cluedge": data.get("cluedge"),
            "clunoise": data.get("clunoise"),
        },
        "proposed_layers": layers,
        "migration_strategy": [
            "keep FM_Forest_001 unchanged as rollback source during migration",
            "create one managed Forest layer per species",
            "reuse existing managed source nodes from FM_References; do not merge duplicates",
            "reuse the same verified spline area references",
            "give each layer exactly one enabled geometry source",
            "preserve active-scene unit conversion for all physical values",
            "verify all layer state before disabling the legacy combined Forest",
            "never delete the user spline or unrelated scene objects",
        ],
        "protected": {
            "density_baseline_meters": 75.0,
            "current_source_assets": True,
            "current_probability_semantics": True,
            "native_scale_variation": True,
            "user_spline": True,
            "unrelated_scene_objects": True,
        },
        "next_stage": {
            "name": "Stage 5D.15 Safe Layer Split Runtime",
            "scope": (
                "create the three managed Forest layers transactionally, verify sources/areas/state, "
                "and leave FM_Forest_001 available for rollback until viewport acceptance"
            ),
        },
        "verified": True,
    }

    print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))
    print("Stage 5D.14 species layer architecture preview passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
