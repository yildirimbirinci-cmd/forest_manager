from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


EXPECTED_LAYER_NAMES = [
    "FM_Layer_01_foreground_mass",
    "FM_Layer_02_mid_accent",
    "FM_Layer_03_structural_shrub",
]


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("PREPARE_SPECIES_LAYER_FORESTS")
    except Exception as exc:
        print("Stage 5D.15 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.15 Safe Species Layer Split:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    layers = data.get("layers") or []

    if not data.get("verified") or not data.get("transactional"):
        return 4
    if not data.get("source_forest_preserved"):
        return 5
    if not data.get("prepared_layers_disabled"):
        return 6
    if len(layers) != 3:
        return 7

    names = [layer.get("forest_name") for layer in layers]
    if names != EXPECTED_LAYER_NAMES:
        return 8

    for layer in layers:
        if not layer.get("verified"):
            return 9
        if not layer.get("disabled"):
            return 10
        if int(layer.get("geometry_count", 0)) != 1:
            return 11
        if abs(float(layer.get("probability", 0.0)) - 100.0) > 0.001:
            return 12
        if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
            return 13
        if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
            return 14

    print("Stage 5D.15 safe species layer split passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
