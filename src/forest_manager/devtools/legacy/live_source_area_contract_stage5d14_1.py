from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_LIVE_SOURCE_AREA_CONTRACT")
    except Exception as exc:
        print("Stage 5D.14.1 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.14.1 Live Source/Area Contract Probe:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    if not data.get("read_only") or not data.get("verified"):
        return 4

    print("Stage 5D.14.1 live source/area contract probe passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
