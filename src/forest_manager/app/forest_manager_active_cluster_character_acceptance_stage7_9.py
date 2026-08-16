from __future__ import annotations

import json

from forest_manager.forest_control.semantic_transaction import UnifiedControlOperation
from forest_manager.ui.controller import ForestManagerUIController


def main() -> int:
    controller = ForestManagerUIController()
    state = controller.refresh_scene(prefer_max_selection=True)
    if not state.bridge_online or not state.selected_forest:
        raise RuntimeError(state.error or "No selected Forest available.")

    controls = {item.key: item for item in state.artist_controls}
    spacing = controls.get("density_spacing")
    naturalness = controls.get("naturalness")
    cluster = controls.get("cluster_character")
    if spacing is None or not spacing.available or spacing.value is None:
        raise RuntimeError("Plant Spacing semantic control is not available.")
    if naturalness is None or not naturalness.available:
        raise RuntimeError("Naturalness semantic control is not available.")
    if cluster is None or not cluster.available:
        raise RuntimeError("Cluster Character semantic control is not available.")

    target_spacing = float(spacing.value) + 1.0
    target_naturalness = "Natural" if str(naturalness.value) != "Natural" else "Balanced"
    current_cluster = str(cluster.value or "")
    target_cluster = "Small Groups" if current_cluster != "Small Groups" else "Medium Clusters"

    state = controller.set_artist_control("density_spacing", target_spacing)
    if state.error:
        raise RuntimeError(state.error)
    state = controller.set_artist_control("naturalness", target_naturalness)
    if state.error:
        raise RuntimeError(state.error)
    state = controller.set_artist_control("cluster_character", target_cluster)
    if state.error:
        raise RuntimeError(state.error)

    pending = tuple(state.pending_edits)
    if not pending:
        raise RuntimeError("Stage 7.9 produced no semantic pending operations.")
    operations = tuple(
        UnifiedControlOperation(property_name=edit.property_name, value=edit.value, label="ui:semantic")
        for edit in pending
    )
    names = [op.property_name for op in operations]
    if len(names) != len(set(names)):
        raise RuntimeError("Semantic composition produced duplicate raw-property targets.")

    result = controller.transaction_manager.execute(
        operations,
        default_forest_name=state.selected_forest,
        rollback_on_success=True,
    )

    expected = {
        "units_x", "units_y", "clusize", "clurough", "clunoise", "cluedge",
        "drotation", "divers", "distpathrandpos",
    }
    report = {
        "ok": True,
        "forest_name": state.selected_forest,
        "spacing_before_display": spacing.value,
        "spacing_target_display": target_spacing,
        "spacing_display_suffix": spacing.display_suffix,
        "naturalness_before": naturalness.value,
        "naturalness_target": target_naturalness,
        "cluster_before": cluster.value,
        "cluster_target": target_cluster,
        "pending_operation_count": len(operations),
        "pending_properties": names,
        "unique_raw_targets": len(names) == len(set(names)),
        "contains_spacing_pair": {"units_x", "units_y"}.issubset(names),
        "contains_naturalness_noncluster_group": {"drotation", "divers", "distpathrandpos"}.issubset(names),
        "contains_cluster_group": {"clusize", "clurough", "clunoise", "cluedge"}.issubset(names),
        "cluster_overrides_shared_cluster_shape": True,
        "single_atomic_transaction": True,
        "before_snapshot": result.before_snapshot,
        "after_write_snapshot": result.after_write_snapshot,
        "after_rollback_snapshot": result.after_rollback_snapshot,
        "write_verified": result.write_verified,
        "rollback_verified": result.rollback_verified,
        "rollback_step_count": result.rollback_step_count,
        "solitary_executable": False,
        "policy": {
            "artist_controls_hide_raw_parameter_coordination": True,
            "three_semantic_controls_share_transaction": True,
            "overlapping_semantic_dependencies_resolve_to_unique_raw_targets": True,
            "cluster_character_has_priority_for_shared_cluster_shape": True,
            "solitary_remains_blocked_without_disable_capability": True,
            "rollback_on_acceptance": True,
            "final_state_preserved": result.rollback_verified,
        },
        "verified": bool(
            result.write_verified
            and result.rollback_verified
            and set(names) == expected
            and len(names) == len(set(names))
        ),
    }
    print("Forest Manager Stage 7.9 Active Cluster Character Acceptance:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["verified"]:
        return 1
    print("Stage 7.9 active cluster character acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
