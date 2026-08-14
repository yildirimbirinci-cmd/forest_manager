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

        result = client.configure_asset_aware_density()
        if not result.ok:
            print("Asset-aware density failed: " + result.error)
            return 3

        print("Asset-Aware Density:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Stage 4D failed: density state not verified.")
            return 4

        source_x = float(result.data.get("source_footprint_x", 0))
        source_y = float(result.data.get("source_footprint_y", 0))
        units_x = float(result.data.get("units_x", 0))
        units_y = float(result.data.get("units_y", 0))

        if source_x <= 0 or source_y <= 0:
            print("Stage 4D failed: invalid source footprint.")
            return 5

        if units_x <= 0 or units_y <= 0:
            print("Stage 4D failed: invalid distribution units.")
            return 6

        print("Stage 4D asset-aware density acceptance passed.")
        print("Check the viewport for realistic T2 asset spacing.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4D error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
