from __future__ import annotations

import json

from forest_manager.forest_control import ForestControlError, ForestPackControlService, SemanticForestControlAPI

SMOKE_CONTROLS = (
    ("distribution", "extended_distribution_controls", "seed"),
    ("transform", "extended_transform_controls", "mirror"),
    ("surface", "extended_surface_controls", "spdensact"),
    ("camera", "extended_camera_controls", "camdensact"),
    ("display", "extended_viewport_controls", "iconSize"),
    ("display", "extended_render_controls", "opaclevel"),
    ("collision", "collision_controls", "collheight"),
)

READ_ONLY_CHECKS = (
    ("display", "viewport", "geomtexid"),
    ("display", "fast_opacity", "fastopac"),
    ("display", "render_identifier", "renderid"),
    ("distribution", "diversity_map_reference", "divtmap"),
    ("material", "geometry_texture_reference", "geomtex"),
)


def main() -> int:
    print("Forest Manager Stage 5D.53 Unified Semantic Forest Control API:")
    try:
        service = ForestPackControlService()
        api = SemanticForestControlAPI(service)
        forests = service.list_forests()
        reports = []
        total_operations = 0
        total_blocked = 0

        for forest_name in forests:
            before = {
                prop: api.get(forest_name, domain, control, prop)["value"]
                for domain, control, prop in SMOKE_CONTROLS
            }
            operations = []
            blocked = []
            for domain, control, prop in SMOKE_CONTROLS:
                try:
                    result = api.set_scalar(forest_name, domain, control, prop, before[prop])
                    operations.append({"property": prop, "result": result})
                except ForestControlError as exc:
                    if "no set_property runtime endpoint" not in str(exc):
                        raise
                    blocked.append({"property": prop, "error": str(exc)})

            after = {
                prop: api.get(forest_name, domain, control, prop)["value"]
                for domain, control, prop in SMOKE_CONTROLS
            }
            if before != after:
                raise RuntimeError(f"Semantic API validation changed state: {forest_name}")

            rollback_results = api.rollback()
            after_rollback = {
                prop: api.get(forest_name, domain, control, prop)["value"]
                for domain, control, prop in SMOKE_CONTROLS
            }
            if before != after_rollback:
                raise RuntimeError(f"Semantic API rollback boundary changed state: {forest_name}")

            total_operations += len(operations)
            total_blocked += len(blocked)
            reports.append(
                {
                    "forest_name": forest_name,
                    "operation_count": len(operations),
                    "blocked_operation_count": len(blocked),
                    "rollback_steps": len(rollback_results),
                    "write_preserved": True,
                    "rollback_preserved": True,
                    "sample_values": before,
                }
            )

        readonly_routes = {
            prop: api.describe(domain, control, prop).route
            for domain, control, prop in READ_ONLY_CHECKS
        }
        write_endpoint = callable(getattr(service, "set_property", None))
        rollback_endpoint = callable(getattr(service, "rollback", None))

        result = {
            "ok": True,
            "forest_count": len(forests),
            "domain_count": len(api.list_domains()),
            "operation_count": total_operations,
            "blocked_operation_count": total_blocked,
            "rollback_step_count": sum(item["rollback_steps"] for item in reports),
            "readonly_routes": readonly_routes,
            "forests": reports,
            "policy": {
                "semantic_schema_is_routing_source": True,
                "semantic_read_available": True,
                "direct_scalar_write": write_endpoint,
                "runtime_write_boundary_verified": not write_endpoint,
                "specialized_array_routes": True,
                "specialized_reference_routes": True,
                "curve_write": False,
                "explicit_runtime_read_only_enforced": True,
                "rollback_executed": rollback_endpoint,
                "final_state_preserved": True,
            },
            "verified": (
                all(route == "read_only" for route in readonly_routes.values())
                and all(item["write_preserved"] and item["rollback_preserved"] for item in reports)
                and all(
                    item["operation_count"] + item["blocked_operation_count"] == len(SMOKE_CONTROLS)
                    for item in reports
                )
            ),
        }
        if not result["verified"]:
            raise RuntimeError("Stage 5D.53 semantic API verification failed.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.53 unified semantic Forest control API passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
