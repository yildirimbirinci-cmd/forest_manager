from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_TRANSFORM_CAPABILITIES")
    except Exception as exc:
        print("Stage 5D.2 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.2 Forest Transform Capability Probe:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3
    data = response.get("data") or {}
    if not data.get("verified") or not data.get("read_only"):
        print("Stage 5D.2 verification failed.")
        return 4
    if int(data.get("transform_property_count") or 0) <= 0:
        print("Stage 5D.2 verification failed: no transform properties detected.")
        return 5

    print("Stage 5D.2 transform capability probe passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
