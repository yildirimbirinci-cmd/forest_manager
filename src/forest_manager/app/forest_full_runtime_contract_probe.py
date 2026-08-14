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
        result = client.get_forest_full_runtime_contract()
        if not result.ok:
            print("Runtime contract query failed: " + result.error)
            return 3
        print("Forest Full Runtime Contract:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))
        print("Stage 3G full runtime contract probe passed.")
        return 0
    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
