from __future__ import annotations

import json
import sys

from forest_manager.composition.layered_composition_plan import build_layered_composition_plan
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def _transform_property_map(payload: dict) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in payload.get("transform_properties") or []:
        name = str(item.get("name") or "").lower()
        if name:
            result[name] = item.get("value")
    return result


def main() -> int:
    try:
        ensure_current_bridge()
        context_response = send_command("GET_COMPOSITION_CONTEXT")
        transform_response = send_command("GET_TRANSFORM_CAPABILITIES")
        if not context_response.get("ok"):
            raise RuntimeError("Composition context failed: " + json.dumps(context_response, ensure_ascii=False))
        if not transform_response.get("ok"):
            raise RuntimeError("Transform capability probe failed: " + json.dumps(transform_response, ensure_ascii=False))

        context = context_response.get("data") or {}
        transform = _transform_property_map(transform_response.get("data") or {})
        plan = build_layered_composition_plan(context, transform)

        if not plan.get("read_only") or not plan.get("verified"):
            raise RuntimeError("Layered composition preview did not verify as read-only.")
        if abs(float(plan.get("density_meters_x") or 0.0) - 75.0) > 0.001:
            raise RuntimeError("Density X is not the verified 75.0 m baseline.")
        if abs(float(plan.get("density_meters_y") or 0.0) - 75.0) > 0.001:
            raise RuntimeError("Density Y is not the verified 75.0 m baseline.")
        if abs(float(plan.get("probability_total") or 0.0) - 100.0) > 0.01:
            raise RuntimeError("Geometry probability total is not 100 percent.")

        print("Forest Manager Stage 5D.5 Layered Plant Composition Preview:")
        print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))
        print("Stage 5D.5 layered composition preview passed.")
        return 0
    except Exception as exc:
        print("Stage 5D.5 error:", type(exc).__name__ + ": " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
