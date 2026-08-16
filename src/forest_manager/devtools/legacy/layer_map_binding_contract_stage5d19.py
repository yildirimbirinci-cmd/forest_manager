from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


IMPORTANT_NAMES = {
    "mapname",
    "densityMap",
    "distmode",
    "distmap",
    "distmapchan",
    "distmapchannel",
    "mapchannel",
    "uvchannel",
    "uvmode",
    "uvmultscalex",
    "uvmultscaley",
    "maxdensity",
}


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_LAYER_MAP_BINDING_CONTRACT")
    except Exception as exc:
        print("Stage 5D.19 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    if not response.get("ok"):
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 3

    data = response.get("data") or {}
    layers = data.get("layers") or []
    if len(layers) != 3:
        print("Stage 5D.19 requires three prepared species layers.")
        return 4

    compact_layers = []
    for layer in layers:
        props = layer.get("candidate_properties") or []
        important = []
        for item in props:
            name = str(item.get("name") or "")
            lower = name.lower()
            if (
                name in IMPORTANT_NAMES
                or "densitymap" in lower
                or "distmap" in lower
                or "mapname" in lower
                or "bitmap" in lower
                or "uv" in lower
                or "channel" in lower
            ):
                important.append(item)

        compact_layers.append(
            {
                "forest_name": layer.get("forest_name"),
                "disabled": layer.get("disabled"),
                "density_meters_x": layer.get("density_meters_x"),
                "density_meters_y": layer.get("density_meters_y"),
                "important_properties": important,
            }
        )

    compact = {
        "command": response.get("command"),
        "read_only": data.get("read_only"),
        "prepared_layers_disabled": data.get("prepared_layers_disabled"),
        "layers": compact_layers,
    }

    print("Forest Manager Stage 5D.19 Forest Pack Map Binding Contract Probe:")
    print(json.dumps(compact, indent=2, ensure_ascii=False))

    if not data.get("read_only") or not data.get("verified"):
        return 5

    for layer in layers:
        if not layer.get("disabled"):
            return 6
        if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
            return 7
        if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
            return 8

    print("Stage 5D.19 Forest Pack map binding contract probe passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
