from __future__ import annotations

import json
import sys

from forest_manager.reference_analysis.local_semantic_parser import (
    LocalSemanticParseError,
    parse_local_semantic_output,
)


SAMPLE = """STYLE: naturalistic woodland
DENSITY: medium
DIVERSITY: medium
CANOPY_BIAS: mixed medium and tall
NOTES: layered planting; irregular grouping
PLANTS: deciduous tree|40; alder|35; field maple|25
CONFIDENCE: 0.78
"""


def main() -> int:
    try:
        payload = parse_local_semantic_output(SAMPLE)
    except LocalSemanticParseError as exc:
        print("Stage 4O.6 parser failed:", str(exc))
        return 1

    print("Forest Manager Semantic Parser:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))

    if len(payload.get("plant_candidates", [])) != 3:
        print("Stage 4O.6 parser verification failed.")
        return 2

    print("Stage 4O.6 semantic parser passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
