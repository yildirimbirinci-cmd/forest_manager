from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_COMPOSITION_CONTEXT")
    except Exception as exc:
        print("Stage 5C.9 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5C.9 Composition Context:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    area = data.get("selection_area") or {}
    density = data.get("density") or {}
    geometry = data.get("geometry") or {}

    if not data.get("verified") or not data.get("read_only"):
        print("Stage 5C.9 verification failed: context is not verified/read-only.")
        return 4
    if float(area.get("area_square_meters") or 0.0) <= 0.0:
        print("Stage 5C.9 verification failed: invalid spline area.")
        return 5
    if float(density.get("meters_x") or 0.0) <= 0.0:
        print("Stage 5C.9 verification failed: invalid Forest density.")
        return 6
    if int(geometry.get("geometry_count") or 0) < 1:
        print("Stage 5C.9 verification failed: Forest geometry is empty.")
        return 7

    print("Stage 5C.9 composition context passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
