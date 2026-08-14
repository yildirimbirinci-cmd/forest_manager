from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.client import MaxBridgeClient, MaxBridgeConnectionError
from forest_manager.max_bridge.protocol import BridgeProtocolError
from forest_manager.t2_bridge import T2AssetCatalog, T2AssetCatalogError


THIRD_QUERY = "Alnus x spaethii 'Spaeth' (Spaeth alder)"


def main() -> int:
    catalog = T2AssetCatalog()
    client = MaxBridgeClient()

    try:
        assets = catalog.search_max_assets(
            THIRD_QUERY,
            limit=20,
            require_existing_file=True,
        )
        if not assets:
            print("Stage 4G failed: third T2 asset was not found.")
            return 2

        asset = assets[0]
        print("Third T2 Asset:")
        print(json.dumps({
            "name": asset.name,
            "file_path": str(asset.file_path),
            "source": asset.source,
            "exists": asset.exists,
        }, indent=2, ensure_ascii=True))

        ping = client.ping()
        if not ping.ok:
            print("Bridge PING failed: " + ping.error)
            return 3

        print("Bridge:")
        print(json.dumps(ping.data, indent=2, ensure_ascii=True))

        append_result = client.append_t2_asset_geometry(
            str(asset.file_path),
            probability=25.0,
        )
        if not append_result.ok:
            print("Third asset append failed: " + append_result.error)
            return 4

        print("Third Asset Append:")
        print(json.dumps(append_result.data, indent=2, ensure_ascii=True))

        if int(append_result.data.get("geometry_count", 0)) != 3:
            print("Stage 4G failed: Forest Geometry count is not 3.")
            return 5

        probability_result = client.set_geometry_probabilities(
            [40.0, 35.0, 25.0]
        )
        if not probability_result.ok:
            print("Probability update failed: " + probability_result.error)
            return 6

        print("Probability Plan:")
        print(json.dumps(probability_result.data, indent=2, ensure_ascii=True))

        probabilities = [
            float(value)
            for value in probability_result.data.get("probabilities", [])
        ]
        expected = [40.0, 35.0, 25.0]

        if len(probabilities) != 3:
            print("Stage 4G failed: probability list length is not 3.")
            return 7

        for actual, wanted in zip(probabilities, expected):
            if abs(actual - wanted) > 0.05:
                print("Stage 4G failed: probability values are incorrect.")
                return 8

        if not probability_result.data.get("verified"):
            print("Stage 4G failed: probability normalization was not verified.")
            return 9

        print("Stage 4G multi-asset management acceptance passed.")
        print("Expected Forest probabilities: 40 / 35 / 25.")
        return 0

    except (T2AssetCatalogError, MaxBridgeConnectionError, BridgeProtocolError) as exc:
        print("Stage 4G error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
