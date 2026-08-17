from __future__ import annotations

import copy
import json
import time

from forest_manager.forest_control.plant_group_execution import execute_plant_group_manifest
from forest_manager.max_bridge.runtime_bridge import (
    ensure_current_bridge,
    read_plant_group_manifest,
    write_plant_group_manifest,
)
from forest_manager.ui.controller import ForestManagerUIController


def _check(name: str, passed: bool, detail=None) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _group_snapshot(manifest: dict, group_id: str) -> dict | None:
    groups = manifest.get("groups") if isinstance(manifest, dict) else None
    for item in groups or []:
        if isinstance(item, dict) and str(item.get("group_id") or "") == group_id:
            return copy.deepcopy(item)
    return None


def _naturalness_of(group_payload: dict | None) -> str | None:
    if not isinstance(group_payload, dict):
        return None
    artist = group_payload.get("artist_values")
    if not isinstance(artist, dict):
        return None
    value = artist.get("naturalness")
    return str(value) if value is not None else None


def _alternate_naturalness(current: str | None) -> str:
    choices = ("Ordered", "Balanced", "Natural", "Wild")
    token = str(current or "Balanced")
    for choice in choices:
        if choice != token:
            return choice
    return "Natural"


def main() -> int:
    started = time.perf_counter()
    checks: list[dict] = []
    restore_error = None
    original_manifest = None

    try:
        ensure_current_bridge()
        controller = ForestManagerUIController()
        initial_state = controller.refresh_scene(prefer_max_selection=False)
        if initial_state.error is not None:
            raise RuntimeError(f"Initial scene refresh failed: {initial_state.error}")
        if "FM_Forest_001" not in tuple(initial_state.forest_names):
            raise RuntimeError("FM_Forest_001 was not discovered during initial scene refresh.")
        original_manifest = read_plant_group_manifest()
        groups = tuple(group for group in initial_state.plant_groups if group.manifest_backed)
        checks.append(_check("three_manifest_groups", len(groups) == 3, [g.label for g in groups]))
        if not groups:
            raise RuntimeError("No manifest-backed Plant Group is available for UI acceptance.")

        group = groups[0]
        original_group = _group_snapshot(original_manifest, group.group_id)
        original_naturalness = _naturalness_of(original_group)
        test_naturalness = _alternate_naturalness(original_naturalness)

        selected = controller.select_plant_group(group.group_id)
        checks.append(
            _check(
                "selection_before_apply",
                selected.selected_group_id == group.group_id,
                selected.selected_group_id,
            )
        )

        staged = controller.set_artist_control("naturalness", test_naturalness)
        checks.append(
            _check(
                "naturalness_creates_pending",
                bool(staged.pending_edits) and staged.error is None,
                {
                    "pending": [edit.property_name for edit in staged.pending_edits],
                    "error": staged.error,
                },
            )
        )

        apply_started = time.perf_counter()
        applied = controller.apply_pending()
        apply_seconds = time.perf_counter() - apply_started
        checks.append(
            _check(
                "apply_succeeds",
                applied.error is None and not applied.pending_edits,
                {"seconds": round(apply_seconds, 3), "status": applied.status, "error": applied.error},
            )
        )
        checks.append(
            _check(
                "selection_preserved_after_apply",
                applied.selected_group_id == group.group_id,
                applied.selected_group_id,
            )
        )

        applied_manifest = read_plant_group_manifest()
        applied_group = _group_snapshot(applied_manifest, group.group_id)
        checks.append(
            _check(
                "apply_manifest_readback",
                _naturalness_of(applied_group) == test_naturalness,
                {
                    "expected": test_naturalness,
                    "actual": _naturalness_of(applied_group),
                },
            )
        )

        restarted = ForestManagerUIController()
        restarted_state = restarted.refresh_scene(prefer_max_selection=False)
        restarted_group = next((g for g in restarted_state.plant_groups if g.group_id == group.group_id), None)
        restart_value = None
        if restarted_group is not None:
            restart_value = restarted_group.artist_values.get("naturalness")
        checks.append(
            _check(
                "restart_reads_applied_value",
                restarted_group is not None and str(restart_value) == test_naturalness,
                {"expected": test_naturalness, "actual": restart_value},
            )
        )

        restarted.select_plant_group(group.group_id)
        reset_started = time.perf_counter()
        reset_state = restarted.reset_selected_target()
        reset_seconds = time.perf_counter() - reset_started
        checks.append(
            _check(
                "selected_group_reset_succeeds",
                reset_state.error is None,
                {"seconds": round(reset_seconds, 3), "status": reset_state.status, "error": reset_state.error},
            )
        )
        checks.append(
            _check(
                "selection_preserved_after_reset",
                reset_state.selected_group_id == group.group_id,
                reset_state.selected_group_id,
            )
        )

        reset_manifest = read_plant_group_manifest()
        reset_group = _group_snapshot(reset_manifest, group.group_id)
        defaults = reset_group.get("reset_defaults") if isinstance(reset_group, dict) else None
        default_artist = defaults.get("artist_values") if isinstance(defaults, dict) else None
        expected_reset = (
            str(default_artist.get("naturalness"))
            if isinstance(default_artist, dict) and default_artist.get("naturalness") is not None
            else "Balanced"
        )
        checks.append(
            _check(
                "reset_manifest_readback",
                _naturalness_of(reset_group) == expected_reset,
                {"expected": expected_reset, "actual": _naturalness_of(reset_group)},
            )
        )

        reset_restart = ForestManagerUIController()
        reset_restart_state = reset_restart.refresh_scene(prefer_max_selection=False)
        reset_restart_group = next(
            (g for g in reset_restart_state.plant_groups if g.group_id == group.group_id),
            None,
        )
        reset_restart_value = None
        if reset_restart_group is not None:
            reset_restart_value = reset_restart_group.artist_values.get("naturalness")
        checks.append(
            _check(
                "restart_reads_reset_value",
                reset_restart_group is not None and str(reset_restart_value) == expected_reset,
                {"expected": expected_reset, "actual": reset_restart_value},
            )
        )
    except Exception as exc:
        checks.append(_check("acceptance_exception", False, f"{type(exc).__name__}: {exc}"))
    finally:
        if original_manifest is not None:
            try:
                restore_write = write_plant_group_manifest(original_manifest)
                if restore_write.get("verified") is not True:
                    raise RuntimeError("Original manifest restore write was not verified.")
                restore_result = execute_plant_group_manifest(
                    original_manifest,
                    strict_acceptance=False,
                )
                if restore_result.get("verified") is not True:
                    raise RuntimeError("Original scene distribution restore was not verified.")
            except Exception as exc:
                restore_error = f"{type(exc).__name__}: {exc}"
        else:
            restore_error = "Skipped because the original manifest was not captured."

    checks.append(_check("original_scene_restored", restore_error is None, restore_error or True))
    ok = all(item["passed"] for item in checks)
    payload = {
        "ok": ok,
        "total_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
