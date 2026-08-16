from __future__ import annotations

import json

from forest_manager.forest_control import ForestControlEngine, SemanticScalarChange


CONTROLS = (
    ("distribution", "extended_distribution_controls", "seed"),
    ("transform", "extended_transform_controls", "mirror"),
    ("display", "extended_viewport_controls", "iconSize"),
)


def _changed_value(name: str, value):
    if name == "seed":
        return int(value) + 1
    if name == "mirror":
        return not bool(value)
    if name == "iconSize":
        return float(value) + 1.0
    raise RuntimeError("Unsupported Stage 6.1 smoke property: " + name)


def main() -> int:
    print("Forest Manager Stage 6.1 General Semantic Scalar Write Endpoint:")
    engine = None
    try:
        engine = ForestControlEngine()
        forests = engine.list_forests()
        if not forests:
            raise RuntimeError("No Forest Pack objects found for Stage 6.1 runtime acceptance.")

        forest_name = "FM_Forest_001" if "FM_Forest_001" in forests else forests[0]
        before = engine.snapshot(forest_name, CONTROLS).semantic_values
        changes = tuple(
            SemanticScalarChange(domain, control, prop, _changed_value(prop, before[prop]))
            for domain, control, prop in CONTROLS
        )
        expected_write = {change.raw_property: change.value for change in changes}
        result = engine.apply_scalar_transaction(forest_name, changes)
        after = engine.snapshot(forest_name, CONTROLS).semantic_values

        verified = bool(
            result.runtime_write_endpoint
            and result.runtime_rollback_endpoint
            and result.operation_count == len(changes)
            and result.blocked_operation_count == 0
            and result.rollback_step_count == len(changes)
            and result.write_verified
            and result.rollback_verified
            and result.before_snapshot == before
            and result.after_write_snapshot == expected_write
            and result.after_rollback_snapshot == before
            and after == before
        )

        report = {
            "ok": True,
            "forest_name": forest_name,
            "transaction_width": len(changes),
            "operation_count": result.operation_count,
            "blocked_operation_count": result.blocked_operation_count,
            "rollback_step_count": result.rollback_step_count,
            "runtime_write_endpoint": result.runtime_write_endpoint,
            "runtime_rollback_endpoint": result.runtime_rollback_endpoint,
            "before_snapshot": result.before_snapshot,
            "after_write_snapshot": result.after_write_snapshot,
            "after_rollback_snapshot": result.after_rollback_snapshot,
            "final_snapshot": after,
            "policy": {
                "scalar_types": ["Integer", "BooleanClass", "Float"],
                "bridge_readback_verification": True,
                "service_readback_verification": True,
                "single_session_rollback_journal": True,
                "explicit_read_only_guard": True,
                "array_reference_curve_rejection": True,
                "final_state_preserved": after == before,
            },
            "verified": verified,
        }
        if not verified:
            raise RuntimeError("Stage 6.1 semantic scalar write verification failed.")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("Stage 6.1 general semantic scalar write endpoint passed.")
        return 0
    except Exception as exc:
        if engine is not None:
            try:
                engine.semantic.rollback()
            except Exception:
                pass
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
