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

        result = client.normalize_reference_sources()
        if not result.ok:
            print("Reference normalization failed: " + result.error)
            return 3

        print("Reference Sources:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Stage 4G.2 failed: reference source state was not verified.")
            return 4

        if result.data.get("layer_name") != "FM_References":
            print("Stage 4G.2 failed: wrong reference layer.")
            return 5

        if bool(result.data.get("layer_visible")):
            print("Stage 4G.2 failed: FM_References layer is visible.")
            return 6

        if float(result.data.get("target_z_mm", 0)) != -1500.0:
            print("Stage 4G.2 failed: reference Z target is not -1500 mm.")
            return 7

        print("Stage 4G.2 reference-source organization acceptance passed.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4G.2 error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
