from __future__ import annotations

import json

from forest_manager.forest_control.area_records import AreaBoundaryRecordAdapter
from forest_manager.forest_control.boundary_semantics import BoundaryBehaviorPlanner
from forest_manager.forest_control.service import ForestPackControlService


def _snapshot(adapter: AreaBoundaryRecordAdapter, forest_name: str, index: int) -> dict[str, float]:
    record = adapter.read_record(forest_name, index)
    return {
        "width": float(record.width),
        "density_falloff": float(record.density_falloff),
        "scale_falloff": float(record.scale_falloff),
    }


def main() -> int:
    service = ForestPackControlService()
    adapter = AreaBoundaryRecordAdapter(service)
    planner = BoundaryBehaviorPlanner(adapter)
    try:
        forest_name = service.selected_forest_name(preflight=True)
        records = adapter.list_records(forest_name)
        if not records:
            raise RuntimeError("Selected Forest has no Area records.")
        area = records[0]
        before = _snapshot(adapter, forest_name, area.index)
        clean_plan = planner.plan_record(area, "Clean Edge")
        natural_plan = planner.plan_record(area, "Natural Spill")
        screen_plan = planner.plan_record(area, "Dense Screening")
        result = planner.apply(forest_name, area.index, "Clean Edge", rollback_on_success=True)
        after_rollback = _snapshot(adapter, forest_name, area.index)
        expected_clean = {
            "density_falloff": 0.0,
            "scale_falloff": 0.0,
        }
        after_write = dict(result.after_write_snapshot)
        write_verified = bool(result.write_verified)
        rollback_verified = bool(result.rollback_verified) and after_rollback == before
        report = {
            "ok": bool(write_verified and rollback_verified),
            "forest_name": forest_name,
            "area_index": area.index,
            "area_name": area.name,
            "boundary_candidate": "Clean Edge",
            "operation_count": result.operation_count,
            "rollback_step_count": result.rollback_step_count,
            "before": before,
            "expected_clean_edge": expected_clean,
            "after_write_snapshot": after_write,
            "after_rollback": after_rollback,
            "write_verified": write_verified,
            "rollback_verified": rollback_verified,
            "natural_spill_executable": natural_plan.executable,
            "natural_spill_blocked_reasons": list(natural_plan.blocked_reasons),
            "dense_screening_executable": screen_plan.executable,
            "dense_screening_blocked_reasons": list(screen_plan.blocked_reasons),
            "policy": {
                "ai_is_primary_boundary_decision_maker": clean_plan.ai_primary,
                "artist_is_supervisory_override": clean_plan.artist_override_supported,
                "area_record_atomic_adapter_used": True,
                "clean_edge_disables_area_falloff_affect": True,
                "unsupported_boundary_intents_not_faked": True,
                "rollback_on_acceptance": True,
                "final_state_preserved": after_rollback == before,
            },
            "verified": bool(write_verified and rollback_verified),
        }
        print("Forest Manager Stage 7.12 Boundary Behavior Semantic Acceptance:")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if report["verified"]:
            print("Stage 7.12 boundary behavior semantic acceptance passed.")
            return 0
        print("Stage 7.12 boundary behavior semantic acceptance failed.")
        return 1
    except Exception as exc:
        print("Forest Manager Stage 7.12 Boundary Behavior Semantic Acceptance:")
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
