from __future__ import annotations

import json

from forest_manager.forest_control.semantic_transaction import (
    UnifiedControlOperation,
    UnifiedControlTransactionManager,
)
from forest_manager.forest_control.service import ForestPackControlService


def _next_channel(value: float) -> float:
    return value + 1.0 if value <= 253.0 else value - 1.0


def main() -> int:
    service = ForestPackControlService()
    manager = UnifiedControlTransactionManager(service)
    forest = "FM_Forest_001"
    try:
        seed = service.get_property(forest, "seed")
        color = service.get_property(forest, "tintcolor1", preflight=False)
        scale = service.get_array_element(forest, "ScaleList", 0, preflight=False)
        proxy0 = service.get_array_element(forest, "cobjlist", 0, preflight=False)
        proxy1 = service.get_array_element(forest, "cobjlist", 1, preflight=False)

        before_color = list(color["value"])
        target_color = list(before_color)
        target_color[0] = _next_channel(float(target_color[0]))
        operations = [
            UnifiedControlOperation("seed", int(seed["value"]) + 1),
            UnifiedControlOperation("tintcolor1", target_color),
            UnifiedControlOperation("ScaleList", float(scale["value"]) + 1.0, index=0),
            UnifiedControlOperation("cobjlist", proxy1["value"], index=0),
        ]
        result = manager.apply_and_rollback(operations, default_forest_name=forest)
        payload = {
            "ok": True,
            "forest_name": forest,
            "transaction_width": len(operations),
            "operation_count": result.operation_count,
            "blocked_operation_count": result.blocked_operation_count,
            "rollback_step_count": result.rollback_step_count,
            "write_verified": result.write_verified,
            "rollback_verified": result.rollback_verified,
            "rolled_back_on_success": result.rolled_back_on_success,
            "before_snapshot": result.before_snapshot,
            "after_write_snapshot": result.after_write_snapshot,
            "after_rollback_snapshot": result.after_rollback_snapshot,
            "operation_modes": [row["write_mode"] for row in result.operations],
            "policy": {
                "mixed_write_types": ["scalar", "color", "array_scalar", "array_cproxy_ref"],
                "prevalidation_before_write": True,
                "duplicate_target_guard": True,
                "scoped_rollback_marker": True,
                "reverse_deterministic_rollback": True,
                "partial_failure_auto_rollback": True,
                "explicit_or_default_forest_target": True,
                "final_state_preserved": result.after_rollback_snapshot == result.before_snapshot,
            },
            "verified": bool(
                result.operation_count == 4
                and result.rollback_step_count == 4
                and result.write_verified
                and result.rollback_verified
                and result.after_rollback_snapshot == result.before_snapshot
            ),
        }
    except Exception as exc:
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
    print("Forest Manager Stage 6.9 Unified Production Transaction:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    if payload.get("verified"):
        print("Stage 6.9 unified production transaction passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
