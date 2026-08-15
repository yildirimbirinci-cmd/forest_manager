from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_CLUSTER_PARAMETER_MAPPING")
    except Exception as exc:
        print("Stage 5D.8 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.8 Cluster Parameter Mapping:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    if not data.get("read_only") or not data.get("verified"):
        print("Stage 5D.8 verification failed.")
        return 4

    candidates = data.get("candidates") or []
    if not candidates:
        print("Stage 5D.8 verification failed: no candidate properties found.")
        return 5

    print("Stage 5D.8 cluster parameter mapping passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
