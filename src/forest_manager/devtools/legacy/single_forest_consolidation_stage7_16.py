from __future__ import annotations

import argparse
import json

from forest_manager.forest_control.plant_group_migration import (
    apply_legacy_plant_group_consolidation,
    build_legacy_plant_group_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 7.16 single-Forest consolidation")
    parser.add_argument("--apply", action="store_true", help="Apply the verified destructive migration.")
    parser.add_argument(
        "--accept-spacing-semantic-only",
        action="store_true",
        help="Accept that legacy per-Forest spacing is preserved as semantic group data, not simultaneous Forest-object spacing.",
    )
    args = parser.parse_args()
    if not args.apply:
        plan = build_legacy_plant_group_plan()
        print(json.dumps(plan.manifest(), indent=2, ensure_ascii=False))
        return 0
    result = apply_legacy_plant_group_consolidation(
        allow_spacing_semantic_only=args.accept_spacing_semantic_only,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
