from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.client import MaxBridgeClient, MaxBridgeConnectionError
from forest_manager.max_bridge.protocol import BridgeProtocolError


def main() -> int:
    client = MaxBridgeClient()
    try:
        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 2

        print("Bridge:")
        print(json.dumps(ping.data, indent=2, ensure_ascii=True))

        result = client.normalize_forest_build_state()
        if not result.ok:
            print("Build-state normalization failed: " + result.error)
            return 3

        print("Forest Build State:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if result.data.get("disabled"):
            print("Acceptance failed: Forest is disabled.")
            return 4

        if not result.data.get("verified"):
            print("Acceptance failed: build state not verified.")
            return 5

        print("Stage 3F build-state acceptance passed.")
        print("Check the viewport for scatter inside the spline.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
