from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("APPLY_NATIVE_SCALE_VARIATION")
    except Exception as exc:
        print("Stage 5D.4 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.4 Apply Native Scale Variation:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    if not data.get("verified"):
        print("Stage 5D.4 verification failed.")
        return 4

    if data.get("applyscale") is not True:
        print("Stage 5D.4 verification failed: scale was not enabled.")
        return 5

    if data.get("applyrotation") is not False or data.get("applytranslation") is not False:
        print("Stage 5D.4 verification failed: protected transform states changed.")
        return 6

    if abs(float(data.get("density_meters_x") or 0.0) - 75.0) > 0.001:
        print("Stage 5D.4 verification failed: density X changed.")
        return 7
    if abs(float(data.get("density_meters_y") or 0.0) - 75.0) > 0.001:
        print("Stage 5D.4 verification failed: density Y changed.")
        return 8

    print("Stage 5D.4 native scale variation apply passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
