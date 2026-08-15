from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT")
    except Exception as exc:
        print("Stage 5D.16 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.16 Per-Layer Density/Distribution Contract Probe:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    layers = data.get("layers") or []
    if not data.get("read_only") or not data.get("verified") or len(layers) != 3:
        return 4

    for layer in layers:
        if not layer.get("read_only") or not layer.get("verified"):
            return 5
        if not layer.get("disabled"):
            return 6
        if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
            return 7
        if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
            return 8

    print("Stage 5D.16 per-layer density/distribution contract probe passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
