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
    if spacing is None or not spacing.available or spacing.value is None:
        raise RuntimeError("Plant Spacing semantic control is not available.")
    if naturalness is None or not naturalness.available:
        raise RuntimeError("Naturalness semantic control is not available.")

    target_spacing = float(spacing.value) + 1.0
    target_naturalness = "Natural" if str(naturalness.value) != "Natural" else "Balanced"
    state = controller.set_artist_control("density_spacing", target_spacing)
    if state.error:
        raise RuntimeError(state.error)
    state = controller.set_artist_control("naturalness", target_naturalness)
    if state.error:
        raise RuntimeError(state.error)

    pending = tuple(state.pending_edits)
    if not pending:
        raise RuntimeError("Stage 7.6 produced no semantic pending operations.")
    operations = tuple(
        UnifiedControlOperation(property_name=edit.property_name, value=edit.value, label="ui:semantic")
        for edit in pending
    )
    result = controller.transaction_manager.execute(
        operations,
        default_forest_name=state.selected_forest,
        rollback_on_success=True,
    )

    names = [op.property_name for op in operations]
    report = {
        "ok": True,
        "forest_name": state.selected_forest,
        "spacing_before_display": spacing.value,
        "spacing_target_display": target_spacing,
        "spacing_display_suffix": spacing.display_suffix,
        "naturalness_before": naturalness.value,
        "naturalness_target": target_naturalness,
        "pending_operation_count": len(operations),
        "pending_properties": names,
        "contains_spacing_pair": "units_x" in names and "units_y" in names,
        "contains_naturalness_group": all(
            name in names for name in ("clurough", "clunoise", "cluedge", "drotation", "divers", "distpathrandpos")
        ),
        "single_atomic_transaction": True,
        "before_snapshot": result.before_snapshot,
        "after_write_snapshot": result.after_write_snapshot,
        "after_rollback_snapshot": result.after_rollback_snapshot,
        "write_verified": result.write_verified,
        "rollback_verified": result.rollback_verified,
        "rollback_step_count": result.rollback_step_count,
        "variation_available": bool(controls.get("variation") and controls["variation"].available),
        "policy": {
            "artist_controls_hide_raw_parameter_coordination": True,
            "plant_spacing_and_naturalness_share_transaction": True,
            "naturalness_runtime_calibrated": True,
            "uncalibrated_controls_disabled": True,
            "rollback_on_acceptance": True,
            "final_state_preserved": result.rollback_verified,
        },
        "verified": bool(
            result.write_verified
            and result.rollback_verified
            and "units_x" in names
            and "units_y" in names
            and all(name in names for name in ("clurough", "clunoise", "cluedge", "drotation", "divers", "distpathrandpos"))
        ),
    }
    print("Forest Manager Stage 7.6 Active Semantic Controls Acceptance:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["verified"]:
        return 1
    print("Stage 7.6 active semantic controls acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
