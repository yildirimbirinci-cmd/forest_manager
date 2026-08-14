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

        result = client.normalize_geometry_item()
        if not result.ok:
            print("Geometry normalization failed: " + result.error)
            return 3

        print("Geometry Normalization:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Stage 3H verification failed.")
            return 4

        print("Stage 3H geometry normalization passed.")
        count = result.data.get("generated_items_after", -1)
        if isinstance(count, int) and count == 0:
            print("Forest reports zero generated items.")
        elif isinstance(count, int) and count > 0:
            print("Forest reports generated items: " + str(count))
        else:
            print("Generated item count is not exposed in this mode.")

        print("Check the viewport for scatter inside the spline.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
