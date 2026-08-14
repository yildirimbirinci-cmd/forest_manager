from __future__ import annotations

import argparse
import json
import sys

from forest_manager.asset_matching import T2SemanticAssetMatcher
from forest_manager.max_bridge.client import MaxBridgeClient
from forest_manager.placement.matched_asset_service import (
    MatchedAssetApplyError,
    MatchedAssetForestService,
)
from forest_manager.t2_bridge import T2AssetCatalog


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or apply real T2 matches from a local-vision observation "
            "to a managed Forest Pack object."
        )
    )
    parser.add_argument("--text", required=True)
    parser.add_argument("--max-terms", type=int, default=5)
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Modify 3ds Max. Select exactly one closed spline before using "
            "this flag. FM_Forest_001 is recreated."
        ),
    )
    args = parser.parse_args()

    service = MatchedAssetForestService(
        matcher=T2SemanticAssetMatcher(T2AssetCatalog()),
        client=MaxBridgeClient(),
    )

    try:
        if not args.apply:
            result = service.preview(args.text, max_terms=max(1, args.max_terms))
            print("Forest Manager Stage 5B Preview:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("Preview only. No 3ds Max / Forest Pack changes were made.")
            return 0 if result["selected_assets"] else 2

        result = service.apply(args.text, max_terms=max(1, args.max_terms))
        print("Forest Manager Stage 5B Forest Apply:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if not result.get("verified"):
            print("Stage 5B apply finished but verification failed.")
            return 3

        print("Stage 5B matched T2 -> Forest Pack acceptance passed.")
        return 0

    except Exception as exc:
        print("Stage 5B error: " + type(exc).__name__ + ": " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
