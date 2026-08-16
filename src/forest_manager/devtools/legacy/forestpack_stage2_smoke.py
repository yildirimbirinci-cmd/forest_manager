from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.client import (
    MaxBridgeClient,
    MaxBridgeConnectionError,
)
from forest_manager.max_bridge.protocol import BridgeProtocolError


def _print_payload(title: str, payload: dict) -> None:
    print(title)
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def main() -> int:
    client = MaxBridgeClient()

    try:
        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 2
        _print_payload("Bridge:", ping.data)

        info = client.get_forestpack_info()
        if not info.ok:
            print("Forest Pack detection failed: " + info.error)
            return 3
        _print_payload("Forest Pack:", info.data)

        selection = client.get_selection()
        if not selection.ok:
            print("Selection query failed: " + selection.error)
            return 4
        _print_payload("Selection:", selection.data)

        if not selection.data.get("is_spline"):
            print("Stage 2 requires exactly one spline selection.")
            return 5
        if not selection.data.get("all_closed"):
            print("Stage 2 requires a closed spline.")
            return 6

        created = client.create_forest_from_selection()
        if not created.ok:
            print("Forest creation failed: " + created.error)
            return 7
        _print_payload("Created Forest:", created.data)

        if created.data.get("area_node") != selection.data.get("name"):
            print("Verification failed: created Forest does not reference the selected spline.")
            return 8
        if created.data.get("area_count", 0) < 1:
            print("Verification failed: created Forest has no spline area.")
            return 9

        print("Stage 2 acceptance passed.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
