from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("APPLY_CLUSTER_DIVERSITY_MODE")
    except Exception as exc:
        print("Stage 5D.10 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.10 Apply Cluster Diversity Mode:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 3

    data = response.get("data") or {}
    if not data.get("verified"):
        print("Stage 5D.10 verification failed.")
        return 4
    if int(data.get("divers", -1)) != 2:
        print("Stage 5D.10 verification failed: divers != 2.")
        return 5

    print("Stage 5D.10 cluster diversity apply passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
