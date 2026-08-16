from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


IMPORTANT_FOREST = (
    "distmapchan", "uvalign", "uvscalex", "uvscaley", "uvmultscalex",
    "uvmultscaley", "distmode", "densityMap",
)
IMPORTANT_BITMAP_TERMS = (
    "coord", "offset", "scale", "tile", "angle", "blur", "crop", "uvw", "filename",
)


def _compact(items, exact=(), terms=()):
    result = []
    exact_lower = {name.lower() for name in exact}
    for item in items or []:
        name = str(item.get("name") or "")
        lower = name.lower()
        if lower in exact_lower or any(term in lower for term in terms):
            result.append(item)
    return result


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_SPECIES_MASK_SPATIAL_ALIGNMENT_CONTRACT")
    except Exception as exc:
        print("Stage 5D.21 error:", type(exc).__name__ + ": " + str(exc))
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
        compact_layers.append(
            {
                "forest_name": layer.get("forest_name"),
                "disabled": layer.get("disabled"),
                "map_path": layer.get("map_path"),
                "forest_alignment_properties": _compact(
                    layer.get("forest_alignment_properties"),
                    exact=IMPORTANT_FOREST,
                    terms=("offset", "tile", "align", "mapchan"),
                ),
                "bitmap_alignment_properties": _compact(
                    layer.get("bitmap_alignment_properties"),
                    terms=IMPORTANT_BITMAP_TERMS,
                ),
            }
        )

    compact = {
        "command": response.get("command"),
        "read_only": data.get("read_only"),
        "prepared_layers_disabled": data.get("prepared_layers_disabled"),
        "spline": data.get("spline"),
        "layers": compact_layers,
    }

    print("Forest Manager Stage 5D.21 Species Mask Spatial Alignment Contract Probe:")
    print(json.dumps(compact, indent=2, ensure_ascii=False))

    if not data.get("read_only") or not data.get("verified"):
        return 5
    if not data.get("prepared_layers_disabled"):
        return 6
    if any(not layer.get("disabled") for layer in layers):
        return 7

    print("Stage 5D.21 species mask spatial alignment contract probe passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
