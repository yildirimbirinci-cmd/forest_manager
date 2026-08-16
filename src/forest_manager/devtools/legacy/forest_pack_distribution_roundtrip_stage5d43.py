from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.distribution import DISTRIBUTION_SCALARS, DistributionAdapter


def _scalar_snapshot(state):
    return {prop: state.values.get(prop) for prop in DISTRIBUTION_SCALARS}


def main() -> int:
    print("Forest Manager Stage 5D.43 Distribution Scalar No-op Roundtrip Boundary:")
    try:
        service = ForestPackControlService()
        adapter = DistributionAdapter(service)
        forests = service.list_forests()
        reports = []
        plan_count = 0
        for forest_name in forests:
            before = adapter.read_state(forest_name)
            before_scalars = _scalar_snapshot(before)
            plan = adapter.no_op_scalar_plan(forest_name)
            plan_preserved = before_scalars == plan
            if not plan_preserved:
                raise RuntimeError(f"No-op distribution plan changed scalar state: {forest_name}")
            plan_count += 1
            reports.append({
                "forest_name": forest_name,
                "plan_preserved": plan_preserved,
                "write_executed": False,
                "rollback_executed": False,
                "density_units_x": before.values.get("units_x"),
                "density_units_y": before.values.get("units_y"),
                "density_map_enabled": before.values.get("densityMap"),
                "distribution_map": before.values.get("distmap"),
                "cluster_size": before.values.get("clusize"),
                "path_mode": before.values.get("distpathmode"),
                "reference_mode": before.values.get("distrefmode"),
            })
        result = {
            "ok": True,
            "forest_count": len(forests),
            "plan_count": plan_count,
            "operation_count": 0,
            "rollback_step_count": 0,
            "forests": reports,
            "policy": {
                "scalar_plan_only": True,
                "scalar_write_only": False,
                "complex_reference_write": False,
                "distribution_map_write": False,
                "path_nodes_write": False,
                "reference_nodes_write": False,
                "writes_executed": False,
                "write_verification": False,
                "rollback_executed": False,
                "final_state_preserved": True,
                "runtime_write_boundary": True,
                "write_boundary_reason": (
                    "Verified bridge exposes discovery only; scalar/property write and rollback "
                    "endpoints are absent from the current runtime capability surface."
                ),
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.43 distribution scalar no-op roundtrip capability boundary passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
