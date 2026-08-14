from __future__ import annotations

import argparse
import json
import sys

from forest_manager.asset_matching import T2SemanticAssetMatcher


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match local-vision observations to real T2 .max assets."
    )
    parser.add_argument(
        "--text",
        required=True,
        help="Semantic observation text, including partial PLANTS output.",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=5,
    )
    args = parser.parse_args()

    try:
        from forest_manager.t2_bridge import T2AssetCatalog
    except Exception as exc:
        print(
            "Stage 5A could not load the project's T2 bridge:",
            type(exc).__name__ + ": " + str(exc),
        )
        return 10

    try:
        report = T2SemanticAssetMatcher(T2AssetCatalog()).match_text(
            args.text,
            max_matches=max(1, int(args.max_matches)),
        )
    except Exception as exc:
        print(
            "Stage 5A T2 matching error:",
            type(exc).__name__ + ": " + str(exc),
        )
        return 11

    print("Forest Manager Stage 5A T2 Asset Match:")
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    if not report.matches:
        print(
            "Stage 5A: no compatible T2 .max asset was found for the "
            "observed vegetation."
        )
        return 2

    print("Stage 5A T2 asset matching passed.")
    print("No 3ds Max / Forest Pack changes were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
