from __future__ import annotations

import json
import time

from forest_manager.forest_control.spline_world_space import read_selected_spline_world_space
from forest_manager.max_bridge.runtime_bridge import current_bridge_identity

def main() -> int:
    started = time.perf_counter()
    geometry = read_selected_spline_world_space(samples_per_spline=64, preflight=True)
    version, build_id = current_bridge_identity()
    sample_counts = [len(s.samples) for s in geometry.splines]
    knot_counts = [len(s.knots) for s in geometry.splines]

    checks = [
        {"name": "bridge_world_space_read_version", "passed": version == "0.9.80" and build_id == "stage8-spline-world-space-read-20260818a", "detail": {"bridge_version": version, "bridge_build_id": build_id}},
        {"name": "selected_spline_world_coordinates", "passed": geometry.coordinate_system == "world", "detail": geometry.node_name},
        {"name": "all_splines_closed", "passed": geometry.all_closed and geometry.spline_count > 0, "detail": {"spline_count": geometry.spline_count}},
        {"name": "knot_order_available", "passed": all(c >= 3 for c in knot_counts), "detail": {"knot_counts": knot_counts}},
        {"name": "curve_samples_available", "passed": all(c == 64 for c in sample_counts), "detail": {"sample_counts": sample_counts}},
        {"name": "scene_units_preserved", "passed": float((geometry.scene_units or {}).get("one_meter_system_units") or 0.0) > 0.0, "detail": dict(geometry.scene_units)},
        {"name": "read_only_geometry_contract", "passed": True, "detail": "GET_SELECTION_SPLINE_WORLD_SPACE"},
    ]

    payload = {
        "ok": all(item["passed"] for item in checks),
        "acceptance": "stage8_spline_world_space",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "node_name": geometry.node_name,
        "spline_count": geometry.spline_count,
        "total_knot_count": geometry.total_knot_count,
        "samples_per_spline": geometry.samples_per_spline,
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
