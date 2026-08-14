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

        result = client.configure_fixed_distribution_units()
        if not result.ok:
            print("Fixed distribution failed: " + result.error)
            return 3

        print("Fixed Distribution Units:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Stage 4E.3 failed: distribution state not verified.")
            return 4

        if abs(float(result.data.get("units_x", 0)) - 45000.0) > 0.001:
            print("Stage 4E.3 failed: units_x is not 45000.0 scene units.")
            return 5

        if abs(float(result.data.get("units_y", 0)) - 45000.0) > 0.001:
            print("Stage 4E.3 failed: units_y is not 45000.0 scene units.")
            return 6

        if int(result.data.get("maxdensity", -1)) != 10:
            print("Stage 4E.3 failed: Max Density is not 10 million.")
            return 7

        print("Stage 4E.3 safe-density baseline acceptance passed.")
        print("Check Forest Pack UI and confirm X/Y Units show 450000.0 mm.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4E.3 error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
