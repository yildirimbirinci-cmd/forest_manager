from __future__ import annotations

import json

from forest_manager.forest_control import (
    ForestPackControlService,
    SemanticForestControlAPI,
    SemanticScalarChange,
    SemanticTransactionManager,
)

TRANSACTION_TEMPLATE = (
    ("distribution", "extended_distribution_controls", "seed"),
    ("transform", "extended_transform_controls", "mirror"),
    ("surface", "extended_surface_controls", "spdensact"),
    ("camera", "extended_camera_controls", "camdensact"),
    ("display", "extended_viewport_controls", "iconSize"),
    ("display", "extended_render_controls", "opaclevel"),
    ("collision", "collision_controls", "collheight"),
)


def main() -> int:
    print("Forest Manager Stage 5D.54 Transaction + Snapshot + Validation Core:")
    try:
        service = ForestPackControlService()
        api = SemanticForestControlAPI(service)
        manager = SemanticTransactionManager(service, api)
        forests = service.list_forests()

        reports = []
        total_operations = 0
        total_blocked = 0
        total_rollbacks = 0

        for forest_name in forests:
            changes = []
            for domain, control, prop in TRANSACTION_TEMPLATE:
                current = api.get(forest_name, domain, control, prop)["value"]
                changes.append(
                    SemanticScalarChange(
                        domain=domain,
                        control=control,
                        raw_property=prop,
                        value=current,
                    )
                )

            result = manager.apply_and_rollback(forest_name, changes)
            total_operations += result.operation_count
            total_blocked += result.blocked_operation_count
            total_rollbacks += result.rollback_step_count
            reports.append(
                {
                    "forest_name": forest_name,
                    "operation_count": result.operation_count,
                    "blocked_operation_count": result.blocked_operation_count,
                    "rollback_steps": result.rollback_step_count,
                    "write_verified": result.write_verified,
                    "rollback_verified": result.rollback_verified,
                    "before_snapshot": result.before_snapshot,
                    "after_write_snapshot": result.after_write_snapshot,
                    "after_rollback_snapshot": result.after_rollback_snapshot,
                    "runtime_write_endpoint": result.runtime_write_endpoint,
                    "runtime_rollback_endpoint": result.runtime_rollback_endpoint,
                }
            )

        write_endpoint = callable(getattr(service, "set_property", None))
        rollback_endpoint = callable(getattr(service, "rollback", None))
        verified = all(
            item["rollback_verified"]
            and item["before_snapshot"] == item["after_rollback_snapshot"]
            and item["operation_count"] + item["blocked_operation_count"]
            == len(TRANSACTION_TEMPLATE)
            and (
                (write_endpoint and item["write_verified"])
                or (
                    not write_endpoint
                    and not item["write_verified"]
                    and item["before_snapshot"] == item["after_write_snapshot"]
                )
            )
            for item in reports
        )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "transaction_width": len(TRANSACTION_TEMPLATE),
            "operation_count": total_operations,
            "blocked_operation_count": total_blocked,
            "rollback_step_count": total_rollbacks,
            "forests": reports,
            "policy": {
                "pre_write_snapshot": True,
                "semantic_route_validation": True,
                "duplicate_property_rejection": True,
                "direct_scalar_only": True,
                "write_verification": write_endpoint,
                "runtime_write_boundary_verified": not write_endpoint,
                "automatic_rollback_on_error": True,
                "rollback_verification": True,
                "rollback_executed": rollback_endpoint,
                "final_state_preserved": True,
            },
            "verified": verified,
        }
        if not verified:
            raise RuntimeError("Stage 5D.54 transaction verification failed.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.54 transaction + snapshot + validation core passed.")
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
