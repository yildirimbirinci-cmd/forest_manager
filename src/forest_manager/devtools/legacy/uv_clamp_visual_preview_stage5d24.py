from __future__ import annotations

import argparse
import json
import sys

from forest_manager.max_bridge.runtime_bridge import send_command
from forest_manager.devtools.legacy.species_preview_bootstrap import ensure_species_preview_ready


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    try:
        if not args.rollback:
            ensure_species_preview_ready()
        command = (
            "ROLLBACK_SPECIES_UV_CLAMP_PREVIEW"
            if args.rollback
            else "APPLY_SPECIES_UV_CLAMP_PREVIEW"
        )
        response = send_command(command)
    except Exception as exc:
        print("Stage 5D.24 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.24 Controlled UV Clamp Preview:")
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
        if not data.get("u_tile") or not data.get("v_tile"):
            return 7
        print("Stage 5D.24 rollback passed.")
        return 0

    if data.get("u_tile") or data.get("v_tile"):
        return 8
    if not data.get("legacy_forest_disabled"):
        return 9
    if not data.get("only_foreground_layer_active"):
        return 10
    if not data.get("viewport_refresh"):
        return 16
    if data.get("real_world_scale") is not False:
        return 20
    if data.get("uv_mapping") != "normalized_area_0_1":
        return 21
    if abs(float(data.get("u_tiling", 0.0)) - 1.0) > 0.0001:
        return 22
    if abs(float(data.get("v_tiling", 0.0)) - 1.0) > 0.0001:
        return 23
    if not data.get("area_node"):
        return 17
    if not data.get("source_node"):
        return 18
    if int(data.get("generated_items", 0)) <= 0:
        return 19
    if abs(float(data.get("density_meters_x", 0.0)) - 75.0) > 0.001:
        return 11
    if abs(float(data.get("density_meters_y", 0.0)) - 75.0) > 0.001:
        return 12

    print("Stage 5D.24 UV clamp preview active.")
    print("Inspect the 3ds Max viewport, then use --rollback to restore the baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
