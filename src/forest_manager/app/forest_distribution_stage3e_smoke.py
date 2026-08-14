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

        result = client.configure_adaptive_distribution()
        if not result.ok:
            print("Adaptive distribution failed: " + result.error)
            return 3

        print("Adaptive Distribution:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Adaptive distribution verification failed.")
            return 4

        if result.data.get("units_x", 0) <= 0 or result.data.get("units_y", 0) <= 0:
            print("Adaptive distribution verification failed: invalid units.")
            return 5

        print("Stage 3E adaptive distribution acceptance passed.")
        print("Now verify that scatter is visible inside the Forest spline area.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
