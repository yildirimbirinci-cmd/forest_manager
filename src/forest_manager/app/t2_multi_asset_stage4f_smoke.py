from __future__ import annotations

import argparse
import json
import sys

from forest_manager.max_bridge.client import MaxBridgeClient, MaxBridgeConnectionError
from forest_manager.max_bridge.protocol import BridgeProtocolError
from forest_manager.t2_bridge import T2AssetCatalog, T2AssetCatalogError


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a second real T2 vegetation asset to Forest Pack.")
    parser.add_argument("query", nargs="?", default="Alnus glutinosa (Black alder)")
    args = parser.parse_args()
    catalog = T2AssetCatalog()
    client = MaxBridgeClient()
    try:
        assets = catalog.search_max_assets(args.query, limit=20, require_existing_file=True)
        if not assets:
            print("Stage 4F failed: no T2 .max asset matched: " + args.query)
            return 2
        asset = assets[0]
        print("Second T2 Asset:")
        print(json.dumps({"name": asset.name, "file_path": str(asset.file_path), "category": asset.category, "source": asset.source, "exists": asset.exists}, indent=2, ensure_ascii=True))
        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 3
        print("Bridge:")
        print(json.dumps(ping.data, indent=2, ensure_ascii=True))
        result = client.append_t2_asset_geometry(str(asset.file_path), probability=50.0)
        if not result.ok:
            print("Multi-asset append failed: " + result.error)
            return 4
        print("Multi-Asset Forest Geometry:")
        print(json.dumps(result.data, indent=2, ensure_ascii=True))
        if not result.data.get("verified"):
            print("Stage 4F failed: Geometry List verification failed.")
            return 5
        if int(result.data.get("geometry_count", 0)) < 2:
            print("Stage 4F failed: Forest has fewer than two Geometry items.")
            return 6
        probabilities = result.data.get("probabilities") or []
        if len(probabilities) < 2 or abs(float(probabilities[0])-50.0)>0.01 or abs(float(probabilities[1])-50.0)>0.01:
            print("Stage 4F failed: expected 50/50 probabilities.")
            return 7
        print("Stage 4F multi-asset probability acceptance passed.")
        return 0
    except (T2AssetCatalogError, MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4F error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
