from __future__ import annotations

import argparse
import json
import sys

from forest_manager.reference_analysis import (
    LocalReferenceCompositionService,
    ReferenceImageError,
    SemanticPlanError,
    SemanticVisionError,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Forest Manager local-only reference-image analysis."
    )
    parser.add_argument("image", help="Reference PNG/JPG/JPEG image.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the locally generated composition plan to T2 + Forest Pack.",
    )
    args = parser.parse_args()

    try:
        service = LocalReferenceCompositionService.create_default()
        result = (
            service.analyze_and_apply(args.image)
            if args.apply
            else service.analyze_only(args.image)
        )
        result.pop("_plan", None)

        print("Local Vision Result:")
        print(json.dumps(result, indent=2, ensure_ascii=True))
        print("Stage 4K Local Vision acceptance passed.")
        if not args.apply:
            print("Analysis-only mode: no 3ds Max scene changes were requested.")
        return 0

    except (
        ReferenceImageError,
        SemanticPlanError,
        SemanticVisionError,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        print("Stage 4K Local Vision error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
