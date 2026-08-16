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
    cluster = planner.plan("cluster_character", "Small Groups")
    solitary = planner.plan("cluster_character", "Solitary")
    if not cluster.executable:
        raise RuntimeError("Cluster Character candidate is not executable: " + ", ".join(cluster.blocked_reasons))

    result = controller.transaction_manager.execute(
        cluster.operations,
        default_forest_name=state.selected_forest,
        rollback_on_success=True,
    )
    report = {
        "ok": True,
        "forest_name": state.selected_forest,
        "cluster_candidate": cluster.choice,
        "cluster_operation_count": len(cluster.operations),
        "cluster_properties": [op.property_name for op in cluster.operations],
        "before_snapshot": result.before_snapshot,
        "after_write_snapshot": result.after_write_snapshot,
        "after_rollback_snapshot": result.after_rollback_snapshot,
        "write_verified": result.write_verified,
        "rollback_verified": result.rollback_verified,
        "rollback_step_count": result.rollback_step_count,
        "solitary_executable": solitary.executable,
        "solitary_blocked_reasons": list(solitary.blocked_reasons),
        "policy": {
            "candidate_profile_not_final_visual_preset": True,
            "cluster_size_uses_active_scene_units": True,
            "cluster_character_multi_parameter_atomic_transaction": True,
            "probability_array_excluded_while_read_only": True,
            "solitary_not_faked_without_cluster_disable_capability": True,
            "rollback_on_success": True,
            "final_state_preserved": result.rollback_verified,
        },
        "verified": bool(result.write_verified and result.rollback_verified),
    }
    print("Forest Manager Stage 7.8 Cluster Character Candidate Acceptance:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["verified"]:
        return 1
    print("Stage 7.8 cluster character candidate acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
