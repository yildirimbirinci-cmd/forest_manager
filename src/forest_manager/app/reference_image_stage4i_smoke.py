from __future__ import annotations

import argparse
import json
import sys

from forest_manager.reference_analysis import ReferenceImageAnalyzer, ReferenceImageError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a reference image for Forest Manager."
    )
    parser.add_argument("image", help="Path to a PNG/JPG/JPEG reference image.")
    args = parser.parse_args()

    try:
        result = ReferenceImageAnalyzer().analyze(args.image)
        print("Reference Analysis:")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))

        if result.image.width <= 0 or result.image.height <= 0:
            print("Stage 4I failed: invalid image dimensions.")
            return 2

        print("Stage 4I reference-image pipeline acceptance passed.")
        print("Semantic AI selection remains intentionally disabled in this stage.")
        return 0

    except (ReferenceImageError, OSError, ValueError) as exc:
        print("Stage 4I error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
