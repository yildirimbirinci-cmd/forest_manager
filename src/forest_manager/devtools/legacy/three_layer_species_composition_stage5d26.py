from __future__ import annotations

import json
import sys

from forest_manager.devtools.legacy.species_preview_bootstrap import ensure_species_preview_ready
from forest_manager.max_bridge.runtime_bridge import send_command


def main() -> int:
    try:
        ensure_species_preview_ready()
        response = send_command("ACTIVATE_ALL_SPECIES_LAYERS")
    except Exception as exc:
        print("Stage 5D.26 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.26 Three-Layer Species Composition:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    if not data.get("verified"):
        return 4
    if data.get("mode") != "three_layer_species_composition":
        return 5
    if not data.get("legacy_forest_disabled"):
        return 6
    if not data.get("all_species_layers_active"):
        return 7
    if data.get("uv_mapping") != "normalized_area_0_1":
        return 8
    if data.get("real_world_scale") is not False:
        return 9
    if abs(float(data.get("density_meters_x", 0.0)) - 75.0) > 0.001:
        return 10
    if abs(float(data.get("density_meters_y", 0.0)) - 75.0) > 0.001:
        return 11
    if int(data.get("layer_count", 0)) != 3:
        return 12
    if int(data.get("total_generated_items", 0)) <= 0:
        return 13
    if not data.get("viewport_refresh"):
        return 14

    layers = data.get("layers") or []
    if len(layers) != 3:
        return 15
    for index, layer in enumerate(layers, start=1):
        if int(layer.get("index", 0)) != index:
            return 16
        if not layer.get("active") or not layer.get("verified"):
            return 17
        if not layer.get("area_node") or not layer.get("source_name"):
            return 18
        if int(layer.get("generated_items", 0)) <= 0:
            return 19
        if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
            return 20
        if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
            return 21

    print("Stage 5D.26 three-layer species composition is active and runtime-verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
