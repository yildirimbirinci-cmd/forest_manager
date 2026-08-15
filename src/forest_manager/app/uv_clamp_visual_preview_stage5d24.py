from __future__ import annotations

import argparse
import json
import sys

from forest_manager.max_bridge.runtime_bridge import send_command
from forest_manager.app.species_preview_bootstrap import ensure_species_preview_ready


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
    if not data.get("real_world_scale"):
        return 13
    if float(data.get("real_world_width_meters", 0.0)) <= 0.0:
        return 14
    if float(data.get("real_world_height_meters", 0.0)) <= 0.0:
        return 15
    if not data.get("legacy_forest_disabled"):
        return 9
    if not data.get("only_foreground_layer_active"):
        return 10
    if abs(float(data.get("density_meters_x", 0.0)) - 75.0) > 0.001:
        return 11
    if abs(float(data.get("density_meters_y", 0.0)) - 75.0) > 0.001:
        return 12

    print("Stage 5D.24 UV clamp preview active.")
    print("Inspect the 3ds Max viewport, then use --rollback to restore the baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
