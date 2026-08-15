from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


IMPORTANT = {
    "U_Offset",
    "V_Offset",
    "U_Tiling",
    "V_Tiling",
    "U_Tile",
    "V_Tile",
    "U_Mirror",
    "V_Mirror",
    "mapChannel",
    "UVW_Type",
    "Blur",
    "Blur_Offset",
    "RealWorld_Scale",
    "useRealWorldScale",
}


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_SPECIES_MASK_DEEP_UVGEN_CONTRACT")
    except Exception as exc:
        print("Stage 5D.22 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    if not response.get("ok"):
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 3

    data = response.get("data") or {}
    layers = data.get("layers") or []
    if len(layers) != 3:
        return 4

    compact_layers = []
    for layer in layers:
        props = layer.get("coords_properties") or []
        important = [
            item for item in props
            if str(item.get("name") or "") in IMPORTANT
            or any(
                term in str(item.get("name") or "").lower()
                for term in ("offset", "tiling", "tile", "mirror", "channel", "uvw", "real", "blur")
            )
        ]
        compact_layers.append(
            {
                "forest_name": layer.get("forest_name"),
                "disabled": layer.get("disabled"),
                "density_meters_x": layer.get("density_meters_x"),
                "density_meters_y": layer.get("density_meters_y"),
                "forest_offset_meters_x": layer.get("forest_offset_meters_x"),
                "forest_offset_meters_y": layer.get("forest_offset_meters_y"),
                "coords_class": layer.get("coords_class"),
                "important_uvgen_properties": important,
            }
        )

    compact = {
        "command": response.get("command"),
        "read_only": data.get("read_only"),
        "prepared_layers_disabled": data.get("prepared_layers_disabled"),
        "spline": data.get("spline"),
        "layers": compact_layers,
    }

    print("Forest Manager Stage 5D.22 Deep UVGen Alignment Contract Probe:")
    print(json.dumps(compact, indent=2, ensure_ascii=False))

    if not data.get("read_only") or not data.get("verified"):
        return 5
    if not data.get("prepared_layers_disabled"):
        return 6
    if any(not layer.get("disabled") for layer in layers):
        return 7

    print("Stage 5D.22 deep UVGen alignment contract probe passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
