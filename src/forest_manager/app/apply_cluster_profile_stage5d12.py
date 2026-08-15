from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("APPLY_NATURAL_CLUSTER_PROFILE")
    except Exception as exc:
        print("Stage 5D.12 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.12 Apply Natural Cluster Profile:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    expected = {
        "divers": 2,
        "clurough": 35.0,
        "cluedge": 25.0,
        "clunoise": 10.0,
    }
    for key, value in expected.items():
        if abs(float(data.get(key, -999.0)) - float(value)) > 0.001:
            print("Stage 5D.12 verification failed:", key)
            return 4

    if not data.get("verified"):
        print("Stage 5D.12 verification failed.")
        return 5

    print("Stage 5D.12 natural cluster profile apply passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
