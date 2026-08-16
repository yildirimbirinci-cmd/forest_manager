from __future__ import annotations

import json
import sys


from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_SCENE_UNITS")
    except Exception as exc:
        print("Stage 5C.4 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5C.4 Active Scene Units:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3
    data = response.get("data") or {}
    required = (
        "display_type",
        "display_unit",
        "system_type",
        "system_scale",
        "one_meter_system_units",
        "sample_one_meter_display",
    )
    if not all(key in data for key in required):
        print("Stage 5C.4 verification failed: incomplete unit context.")
        return 4
    if float(data.get("one_meter_system_units") or 0.0) <= 0.0:
        print("Stage 5C.4 verification failed: invalid meter conversion.")
        return 5
    if not data.get("verified"):
        print("Stage 5C.4 verification failed.")
        return 6

    print("Stage 5C.4 active scene unit detection passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
