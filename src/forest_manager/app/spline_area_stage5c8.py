from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_SELECTION_SPLINE_AREA")
    except Exception as exc:
        print("Stage 5C.8 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5C.8 Unit-Aware Spline Area:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    required = (
        "node_name",
        "spline_count",
        "all_splines_closed",
        "area_system_units_squared",
        "area_square_meters",
        "area_display_value",
        "area_display_unit",
        "scene_units",
        "verified",
    )
    if not all(key in data for key in required):
        print("Stage 5C.8 verification failed: incomplete area context.")
        return 4
    if not data.get("verified"):
        return 5
    if float(data.get("area_square_meters") or 0.0) <= 0.0:
        print("Stage 5C.8 verification failed: non-positive spline area.")
        return 6

    print("Stage 5C.8 unit-aware spline area passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
