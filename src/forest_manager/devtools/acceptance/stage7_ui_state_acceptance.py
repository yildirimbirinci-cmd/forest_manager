from __future__ import annotations

import json
import time
from contextlib import ExitStack
from unittest.mock import patch

from forest_manager.ui.controller import ForestManagerUIController


def _check(name: str, passed: bool, detail=None) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def main() -> int:
    started = time.perf_counter()
    controller = ForestManagerUIController()
    state = controller.refresh_scene(prefer_max_selection=False)

    checks: list[dict] = []
    checks.append(_check("bridge_online", state.bridge_online, state.error or state.status))
    checks.append(_check("primary_forest_present", bool(state.primary_forest), state.primary_forest))

    groups = tuple(group for group in state.plant_groups if group.manifest_backed)
    checks.append(_check("three_manifest_plant_groups", len(groups) == 3, [g.label for g in groups]))
    checks.append(_check("no_pending_after_refresh", not state.pending_edits, len(state.pending_edits)))

    # Capture the scene-derived UI values. A second controller refresh later in
    # the test must reconstruct the same values without requiring any Apply.
    baseline = {
        group.group_id: {
            "label": group.label,
            "spacing_system": list(group.spacing_system) if group.spacing_system is not None else None,
            "artist_values": dict(group.artist_values),
        }
        for group in groups
    }

    # Tree navigation is required to be cache-only. If any of these methods are
    # touched while switching Forest 01 / child Plant Groups, the test fails.
    guarded_methods = (
        "inventory",
        "list_forests",
        "scene_units",
        "selected_forest_name",
        "get_array_element",
        "set_array_element",
    )
    selection_durations: list[float] = []
    selection_error = None
    try:
        with ExitStack() as stack:
            for method_name in guarded_methods:
                if hasattr(controller.service, method_name):
                    stack.enter_context(
                        patch.object(
                            controller.service,
                            method_name,
                            side_effect=AssertionError(
                                f"selection unexpectedly called service.{method_name}"
                            ),
                        )
                    )

            for _ in range(20):
                t0 = time.perf_counter()
                global_state = controller.select_global_planting()
                selection_durations.append(time.perf_counter() - t0)
                if global_state.selected_group_id is not None:
                    raise AssertionError("Forest 01 selection retained a child Plant Group id")
                if global_state.pending_edits:
                    raise AssertionError("Forest 01 selection created pending edits")

                for group in groups:
                    t0 = time.perf_counter()
                    group_state = controller.select_plant_group(group.group_id)
                    selection_durations.append(time.perf_counter() - t0)
                    if group_state.selected_group_id != group.group_id:
                        raise AssertionError(
                            f"selection mismatch: expected {group.group_id}, got {group_state.selected_group_id}"
                        )
                    if group_state.pending_edits:
                        raise AssertionError(f"selection created pending edits for {group.group_id}")
    except Exception as exc:
        selection_error = f"{type(exc).__name__}: {exc}"

    max_selection_ms = max(selection_durations, default=0.0) * 1000.0
    mean_selection_ms = (
        sum(selection_durations) / len(selection_durations) * 1000.0
        if selection_durations
        else 0.0
    )
    checks.append(
        _check(
            "selection_cache_only",
            selection_error is None,
            selection_error or {"transitions": len(selection_durations)},
        )
    )
    checks.append(
        _check(
            "selection_latency",
            selection_error is None and max_selection_ms < 250.0,
            {
                "max_ms": round(max_selection_ms, 3),
                "mean_ms": round(mean_selection_ms, 3),
                "threshold_ms": 250.0,
            },
        )
    )

    # Restart/readback contract: a fresh controller must reconstruct the same
    # scene-authoritative Plant Group state from Max + the scene manifest.
    restart_error = None
    restart_snapshot = None
    try:
        restarted = ForestManagerUIController()
        restarted_state = restarted.refresh_scene(prefer_max_selection=False)
        restarted_groups = tuple(group for group in restarted_state.plant_groups if group.manifest_backed)
        restart_snapshot = {
            group.group_id: {
                "label": group.label,
                "spacing_system": list(group.spacing_system) if group.spacing_system is not None else None,
                "artist_values": dict(group.artist_values),
            }
            for group in restarted_groups
        }
    except Exception as exc:
        restart_error = f"{type(exc).__name__}: {exc}"

    checks.append(
        _check(
            "restart_scene_state_roundtrip",
            restart_error is None and restart_snapshot == baseline,
            restart_error or {"before": baseline, "after": restart_snapshot},
        )
    )

    ok = all(item["passed"] for item in checks)
    payload = {
        "ok": ok,
        "forest": state.primary_forest,
        "plant_groups": [group.label for group in groups],
        "total_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
