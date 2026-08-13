from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.client import (
    MaxBridgeClient,
    MaxBridgeConnectionError,
)
from forest_manager.max_bridge.protocol import BridgeProtocolError


def main() -> int:
    client = MaxBridgeClient()

    try:
        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 2

        print("Bridge connected.")
        print(json.dumps(ping.data, indent=2, ensure_ascii=True))

        selection = client.get_selection()
        if not selection.ok:
            print("Selection query failed: " + selection.error)
            return 3

        print("Selection:")
        print(json.dumps(selection.data, indent=2, ensure_ascii=True))
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
