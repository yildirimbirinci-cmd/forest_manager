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

        contract = client.get_forest_geometry_contract()
        if not contract.ok:
            print("Geometry contract query failed: " + contract.error)
            return 3

        print("Forest Geometry Contract:")
        print(json.dumps(contract.data, indent=2, ensure_ascii=True))

        candidates = contract.data.get("geometry_candidates", [])
        if not candidates:
            print("No candidate Geometry List properties were discovered.")
            return 4

        print("Stage 3A contract probe passed.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
