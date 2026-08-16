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

        info = client.get_forestpack_info()
        if not info.ok or not info.data.get("available"):
            print("Forest Pack detection failed: " + info.error)
            return 3

        print("Forest Pack:")
        print(json.dumps(info.data, indent=2, ensure_ascii=True))

        selection = client.get_selection()
        if not selection.ok:
            print("Selection query failed: " + selection.error)
            return 4

        print("Selected source:")
        print(json.dumps(selection.data, indent=2, ensure_ascii=True))

        if selection.data.get("is_shape"):
            print("Stage 3 requires a geometry source object, not a spline.")
            return 5

        if str(selection.data.get("class", "")).lower() == "forest_pro":
            print("Stage 3 requires a source geometry object, not the Forest object.")
            return 5

        result = client.add_selected_geometry_to_forest()
        if not result.ok:
            print("Geometry add failed: " + result.error)
            return 6

        print("Forest Geometry:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Geometry verification failed.")
            return 7

        if result.data.get("geometry_count", 0) < 1:
            print("Geometry verification failed: empty list.")
            return 8

        print("Stage 3 geometry-list acceptance passed.")
        print("Now visually verify that the selected source is listed in Forest Pack Geometry.")
        print("If no scatter appears, keep the scene open and report that separately.")
        return 0

    except (MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Bridge error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
