from __future__ import annotations

import json

from forest_manager.ui.controller import ForestManagerUIController
from forest_manager.ui.semantic_calibration import SemanticCalibrationPlanner


def main() -> int:
    controller = ForestManagerUIController()
    state = controller.refresh_scene(prefer_max_selection=True)
    if not state.bridge_online or not state.selected_forest:
        raise RuntimeError(state.error or "No selected Forest available.")

    planner = SemanticCalibrationPlanner(controller)
    natural = planner.plan("naturalness", "Natural")
    variation = planner.plan("variation", "High")
    if not natural.executable:
        raise RuntimeError("Naturalness candidate is not executable: " + ", ".join(natural.blocked_reasons))

    result = controller.transaction_manager.execute(
        natural.operations,
        default_forest_name=state.selected_forest,
        rollback_on_success=True,
    )
    report = {
        "ok": True,
        "forest_name": state.selected_forest,
        "naturalness_candidate": natural.choice,
        "naturalness_operation_count": len(natural.operations),
        "naturalness_properties": [op.property_name for op in natural.operations],
        "before_snapshot": result.before_snapshot,
        "after_write_snapshot": result.after_write_snapshot,
        "after_rollback_snapshot": result.after_rollback_snapshot,
        "write_verified": result.write_verified,
        "rollback_verified": result.rollback_verified,
        "rollback_step_count": result.rollback_step_count,
        "variation_executable": variation.executable,
        "variation_blocked_reasons": list(variation.blocked_reasons),
        "policy": {
            "candidate_profile_not_final_visual_preset": True,
            "naturalness_multi_parameter_atomic_transaction": True,
            "read_only_properties_excluded": True,
            "rollback_on_success": True,
            "variation_not_faked_when_activation_flags_unavailable": True,
            "final_state_preserved": result.rollback_verified,
        },
        "verified": bool(result.write_verified and result.rollback_verified),
    }
    print("Forest Manager Stage 7.5 Semantic Candidate Calibration Acceptance:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["verified"]:
        return 1
    print("Stage 7.5 semantic candidate calibration acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
