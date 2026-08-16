from __future__ import annotations

import argparse
import json
import sys

from forest_manager.max_bridge.runtime_bridge import send_command
from forest_manager.devtools.legacy.species_preview_bootstrap import ensure_species_preview_ready


LAYER_LABELS = {
    1: "foreground_mass / Lavandula",
    2: "mid_accent / Butomus",
    3: "structural_shrub / Berberis",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    try:
        if not args.rollback:
            ensure_species_preview_ready()
        if args.rollback:
            response = send_command("ROLLBACK_SPECIES_LAYER_PREVIEW")
        else:
            response = send_command(f"ACTIVATE_SINGLE_SPECIES_LAYER|{args.layer}")
    except Exception as exc:
        print("Stage 5D.23 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.23 Controlled Single-Layer Visual Preview:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    if not data.get("verified"):
        return 4

    if args.rollback:
        if not data.get("legacy_forest_active"):
            return 5
        if not data.get("all_species_layers_disabled"):
            return 6
        print("Stage 5D.23 rollback passed. Legacy combined Forest is active again.")
        return 0

    layers = data.get("layers") or []
    if len(layers) != 3:
        return 7
    if not data.get("legacy_forest_disabled"):
        return 8
    if not data.get("density_units_preserved"):
        return 9
    if not data.get("viewport_refresh"):
        return 16
    if data.get("real_world_scale") is not False:
        return 20
    if data.get("uv_mapping") != "normalized_area_0_1":
        return 21
    if not data.get("area_node"):
        return 17
    if not data.get("source_node"):
        return 18
    if int(data.get("generated_items", 0)) <= 0:
        return 19

    active = [layer for layer in layers if layer.get("active")]
    if len(active) != 1:
        return 10
    if active[0].get("forest_name") != layers[args.layer - 1].get("forest_name"):
        return 11

    for layer in layers:
        if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
            return 12
        if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
            return 13
        if not layer.get("densityMap"):
            return 14
        if int(layer.get("distmode", -1)) != 0:
            return 15

    print("Stage 5D.23 visual preview active:", LAYER_LABELS[args.layer])
    print("Inspect the 3ds Max viewport. Use --rollback to restore FM_Forest_001.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
