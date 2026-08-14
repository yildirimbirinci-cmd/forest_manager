from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_SELECTION_MEASUREMENTS")
    except Exception as exc:
        print("Stage 5C.7 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5C.7 Unit-Aware Selection Measurements:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3
    data = response.get("data") or {}
    required = (
        "node_name", "width_system_units", "depth_system_units",
        "width_display", "depth_display", "scene_units", "verified",
    )
    if not all(key in data for key in required):
        print("Stage 5C.7 verification failed: incomplete measurement context.")
        return 4
    if not data.get("verified"):
        return 5

    print("Stage 5C.7 unit-aware selection measurement passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
