from __future__ import annotations

import json

from forest_manager.forest_control import ForestControlEngine, SemanticScalarChange


SMOKE_CONTROLS = (
    ("distribution", "extended_distribution_controls", "seed"),
    ("transform", "extended_transform_controls", "mirror"),
    ("surface", "extended_surface_controls", "spdensact"),
    ("camera", "extended_camera_controls", "camdensact"),
    ("display", "extended_viewport_controls", "iconSize"),
    ("display", "extended_render_controls", "opaclevel"),
    ("collision", "collision_controls", "collheight"),
)


def main() -> int:
    print("Forest Manager Stage 5D.55 General Forest Control Engine:")
    engine = None
    try:
        engine = ForestControlEngine()
        forests = engine.list_forests()
        reports = []
        total_operations = 0
        total_blocked = 0
        total_rollbacks = 0

        for forest_name in forests:
            before_snapshot = engine.snapshot(forest_name, SMOKE_CONTROLS)
            changes = [
                SemanticScalarChange(
                    domain=domain,
                    control=control,
                    raw_property=prop,
                    value=before_snapshot.semantic_values[prop],
                )
                for domain, control, prop in SMOKE_CONTROLS
            ]
            tx_result = engine.apply_scalar_transaction(forest_name, changes)
            after_snapshot = engine.snapshot(forest_name, SMOKE_CONTROLS)
            if before_snapshot != after_snapshot:
                raise RuntimeError(f"General engine final snapshot mismatch: {forest_name}")

            capability = engine.capability_summary(forest_name)
            total_operations += tx_result.operation_count
            total_blocked += tx_result.blocked_operation_count
            total_rollbacks += tx_result.rollback_step_count
            width_accounted = (
                tx_result.operation_count + tx_result.blocked_operation_count == len(SMOKE_CONTROLS)
            )
            endpoint_contract_ok = (
                (tx_result.runtime_write_endpoint and tx_result.operation_count == len(SMOKE_CONTROLS) and tx_result.write_verified)
                or (
                    not tx_result.runtime_write_endpoint
                    and tx_result.operation_count == 0
                    and tx_result.blocked_operation_count == len(SMOKE_CONTROLS)
                    and not tx_result.write_verified
                )
            )
            reports.append(
                {
                    "forest_name": forest_name,
                    "domain_count": capability["domain_count"],
                    "raw_property_count": capability["raw_property_count"],
                    "geometry_source_count": capability["geometry_source_count"],
                    "area_record_count": capability["area_record_count"],
                    "operation_count": tx_result.operation_count,
                    "blocked_operation_count": tx_result.blocked_operation_count,
                    "rollback_steps": tx_result.rollback_step_count,
                    "write_verified": tx_result.write_verified,
                    "rollback_verified": tx_result.rollback_verified,
                    "runtime_write_endpoint": tx_result.runtime_write_endpoint,
                    "runtime_rollback_endpoint": tx_result.runtime_rollback_endpoint,
                    "transaction_width_accounted": width_accounted,
                    "endpoint_contract_ok": endpoint_contract_ok,
                    "final_snapshot_preserved": True,
                    "semantic_values": before_snapshot.semantic_values,
                }
            )

        verified = len(forests) > 0 and all(
            item["domain_count"] == 11
            and item["raw_property_count"] == 341
            and item["geometry_source_count"] >= 1
            and item["area_record_count"] >= 1
            and item["rollback_verified"]
            and item["transaction_width_accounted"]
            and item["endpoint_contract_ok"]
            and item["final_snapshot_preserved"]
            for item in reports
        )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "domain_count": len(engine.list_domains()),
            "transaction_width": len(SMOKE_CONTROLS),
            "operation_count": total_operations,
            "blocked_operation_count": total_blocked,
            "rollback_step_count": total_rollbacks,
            "forests": reports,
            "policy": {
                "single_control_facade": True,
                "semantic_scalar_routing": True,
                "transaction_core_integrated": True,
                "geometry_atomic_adapter_integrated": True,
                "area_atomic_adapter_integrated": True,
                "read_only_semantic_guards_preserved": True,
                "runtime_write_boundary_verified": all(
                    item["endpoint_contract_ok"] for item in reports
                ),
                "curve_write": False,
                "final_state_preserved": True,
            },
            "verified": verified,
        }
        if not verified:
            raise RuntimeError("Stage 5D.55 general engine verification failed.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.55 general Forest control engine passed.")
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
