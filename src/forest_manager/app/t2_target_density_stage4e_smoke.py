from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.client import MaxBridgeClient, MaxBridgeConnectionError
from forest_manager.max_bridge.protocol import BridgeProtocolError


TARGET = 45000
LOW = 35000
HIGH = 55000


def main() -> int:
    client = MaxBridgeClient()
    try:
        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 2

        print("Bridge:")
        print(json.dumps(ping.data, indent=2, ensure_ascii=True))

        result = client.configure_target_item_density()
        if not result.ok:
            print("Target density failed: " + result.error)
            return 3

        print("Target Item Density:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Stage 4E failed: density state not verified.")
            return 4

        count = int(result.data.get("generated_items_after", -1))
        if count < 0:
            print("Stage 4E failed: Forest did not expose generated item count.")
            return 5

        print("Generated item count: " + str(count))
        if LOW <= count <= HIGH:
            print("Stage 4E 45K stress-density acceptance passed.")
        else:
            print(
                "Stage 4E first-pass completed; count is outside the "
                "35K-55K calibration window."
            )

        print("Check viewport responsiveness and proxy scatter.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4E error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
