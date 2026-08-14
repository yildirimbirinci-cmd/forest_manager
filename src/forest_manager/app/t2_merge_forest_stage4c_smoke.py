from __future__ import annotations

import argparse
import json
import sys

from forest_manager.max_bridge.client import MaxBridgeClient, MaxBridgeConnectionError
from forest_manager.max_bridge.protocol import BridgeProtocolError
from forest_manager.t2_bridge import T2AssetCatalog, T2AssetCatalogError


def _asset_json(asset):
    return {
        "name": asset.name,
        "file_path": str(asset.file_path),
        "category": asset.category,
        "source": asset.source,
        "exists": asset.exists,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge one real T2 .max asset and bind it to Forest Pack."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Acer campestre (Field maple)",
        help="T2 asset search text.",
    )
    args = parser.parse_args()

    catalog = T2AssetCatalog()
    client = MaxBridgeClient()

    try:
        assets = catalog.search_max_assets(
            args.query,
            limit=20,
            require_existing_file=True,
        )
        if not assets:
            print("Stage 4C failed: no T2 .max asset matched: " + args.query)
            return 2

        asset = assets[0]
        print("T2 Asset:")
        print(json.dumps(_asset_json(asset), indent=2, ensure_ascii=True))

        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 3

        print("Bridge:")
        print(json.dumps(ping.data, indent=2, ensure_ascii=True))

        result = client.merge_t2_asset_and_bind(str(asset.file_path))
        if not result.ok:
            print("T2 merge/bind failed: " + result.error)
            return 4

        print("T2 Merge + Forest Bind:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))

        if not result.data.get("verified"):
            print("Stage 4C failed: Forest source verification failed.")
            return 5

        if int(result.data.get("merged_node_count", 0)) < 1:
            print("Stage 4C failed: merge produced no new nodes.")
            return 6

        if int(result.data.get("geometry_mode", -1)) != 2:
            print("Stage 4C failed: Forest Geometry is not Custom Object mode.")
            return 7

        print("Stage 4C T2 merge-to-Forest acceptance passed.")
        print("Check the viewport: the Forest scatter should now use the merged T2 asset.")
        return 0

    except (T2AssetCatalogError, MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4C error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
