from __future__ import annotations

import argparse
import json
import sys

from forest_manager.placement import (
    CompositionPlan,
    CompositionPlanError,
    CompositionPlanService,
)
from forest_manager.max_bridge.client import MaxBridgeConnectionError
from forest_manager.max_bridge.protocol import BridgeProtocolError
from forest_manager.t2_bridge import T2AssetCatalogError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply a reusable Forest Manager composition plan."
    )
    parser.add_argument(
        "plan",
        nargs="?",
        default="config/composition_plan_stage4h.json",
    )
    args = parser.parse_args()

    try:
        plan = CompositionPlan.from_json_file(args.plan)
        service = CompositionPlanService()
        result = service.apply(plan)

        print("Composition Plan:")
        print(json.dumps(result, indent=2, ensure_ascii=True))

        if not result.get("verified"):
            print("Stage 4H failed: composition plan was not fully verified.")
            return 2

        if abs(float(result.get("probability_total", 0)) - 100.0) > 0.05:
            print("Stage 4H failed: probability total is not 100.")
            return 3

        if bool(result.get("reference_layer_visible")):
            print("Stage 4H failed: reference layer is visible.")
            return 4

        print("Stage 4H composition-plan acceptance passed.")
        return 0

    except (
        CompositionPlanError,
        T2AssetCatalogError,
        MaxBridgeConnectionError,
        BridgeProtocolError,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        print("Stage 4H error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
