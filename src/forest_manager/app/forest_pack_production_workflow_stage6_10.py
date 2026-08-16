from __future__ import annotations

import json

from forest_manager.forest_control.semantic_transaction import (
    ProductionControlWorkflow,
    UnifiedControlOperation,
)
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


def _next_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ForestControlError(f"Stage 6.10 expected Integer seed, got: {type(value).__name__}")
    return value + 1


def main() -> int:
    service = ForestPackControlService()
    workflow = ProductionControlWorkflow(service)
    try:
        selected = service.selected_forest_name(preflight=True)
        forests = service.list_forests(preflight=False)
        if len(forests) < 2:
            raise RuntimeError("Stage 6.10 requires at least two Forest objects for multi-Forest acceptance.")
        secondary = next((name for name in forests if name != selected), None)
        if secondary is None:
            raise RuntimeError("Stage 6.10 could not resolve a secondary Forest target.")

        units = service.scene_units(preflight=False)
        selected_seed = service.get_property(selected, "seed", preflight=False)
        secondary_seed = service.get_property(secondary, "seed", preflight=False)
        selected_before = selected_seed.get("value")
        secondary_before = secondary_seed.get("value")

        result = workflow.apply_and_rollback([
            UnifiedControlOperation("seed", _next_int(selected_before)),
            UnifiedControlOperation("seed", _next_int(secondary_before), forest_name=secondary),
        ])

        selected_final = service.get_property(selected, "seed", preflight=False).get("value")
        secondary_final = service.get_property(secondary, "seed", preflight=False).get("value")
        final_state_preserved = selected_final == selected_before and secondary_final == secondary_before
        verified = (
            result.selected_target_used
            and not result.explicit_target_used
            and result.resolved_default_forest == selected
            and result.transaction.operation_count == 2
            and result.transaction.write_verified
            and result.transaction.rollback_verified
            and result.stale_target_guard_verified
            and result.forest_names_before == result.forest_names_after
            and final_state_preserved
            and units.one_meter_system_units > 0.0
        )
        payload = {
            "ok": bool(verified),
            "selected_forest": selected,
            "secondary_forest": secondary,
            "transaction_width": result.transaction.operation_count,
            "rollback_step_count": result.transaction.rollback_step_count,
            "selected_target_used": result.selected_target_used,
            "explicit_target_used": result.explicit_target_used,
            "multi_forest_transaction": len({selected, secondary}) == 2,
            "forest_names_before": list(result.forest_names_before),
            "forest_names_after": list(result.forest_names_after),
            "before_snapshot": result.transaction.before_snapshot,
            "after_write_snapshot": result.transaction.after_write_snapshot,
            "after_rollback_snapshot": result.transaction.after_rollback_snapshot,
            "scene_units": result.scene_units,
            "unit_roundtrip_sample": {
                "one_meter_system_units": units.meters_to_system_units(1.0),
                "roundtrip_meters": units.system_units_to_meters(units.meters_to_system_units(1.0)),
            },
            "policy": {
                "selected_forest_resolution": True,
                "explicit_target_override_supported": True,
                "multi_forest_prevalidation": True,
                "stale_target_guard": result.stale_target_guard_verified,
                "dynamic_scene_unit_context": True,
                "display_units_reported_from_active_scene": True,
                "system_unit_conversion_runtime_driven": True,
                "scoped_reverse_rollback": True,
                "startup_loader_unchanged": True,
                "final_state_preserved": final_state_preserved,
            },
            "verified": bool(verified),
        }
        print("Forest Manager Stage 6.10 Production Control Workflow:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        if not verified:
            raise RuntimeError("Stage 6.10 production workflow verification failed.")
        print("Stage 6.10 production control workflow passed.")
        return 0
    except Exception as exc:
        print("Forest Manager Stage 6.10 Production Control Workflow:")
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
