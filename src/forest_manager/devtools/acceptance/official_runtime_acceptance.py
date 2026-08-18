from __future__ import annotations

import json
import time
from typing import Any, Mapping

from forest_manager.forest_control.scene_runtime import ForestSceneRuntime
from forest_manager.forest_control.scene_state import SceneStateGateway
from forest_manager.forest_control.service import ForestPackControlService
from forest_manager.forest_control.unit_conversion import UnitConversionGateway
from forest_manager.max_bridge import runtime_bridge as rb
from forest_manager.ui.controller import ForestManagerUIController


def _check(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _geometry_source_count(service: ForestPackControlService, forest_name: str) -> int:
    inventory = service.inventory(forest_name, preflight=False)
    cobj = next(
        (
            item
            for item in (inventory.get("properties") or [])
            if isinstance(item, dict) and str(item.get("name") or "").lower() == "cobjlist"
        ),
        None,
    )
    metadata = cobj.get("array_metadata") if isinstance(cobj, dict) else None
    return int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0


def _group_snapshot(state: Any) -> list[dict[str, Any]]:
    return [
        {
            "group_id": group.group_id,
            "forest_name": group.forest_name,
            "spacing_system": list(group.spacing_system) if group.spacing_system is not None else None,
            "source_names": list(group.source_names),
        }
        for group in state.plant_groups
        if group.manifest_backed
    ]


def run_acceptance() -> dict[str, Any]:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    ping = rb.ensure_current_bridge()
    ping_data = ping.get("data") if isinstance(ping, Mapping) else {}
    ping_data = ping_data if isinstance(ping_data, Mapping) else {}
    checks.append(
        _check(
            "bridge_identity",
            ping_data.get("bridge_version") == rb.EXPECTED_BRIDGE_VERSION
            and ping_data.get("bridge_build_id") == rb.EXPECTED_BRIDGE_BUILD_ID,
            {
                "bridge_version": ping_data.get("bridge_version"),
                "bridge_build_id": ping_data.get("bridge_build_id"),
                "expected_version": rb.EXPECTED_BRIDGE_VERSION,
                "expected_build_id": rb.EXPECTED_BRIDGE_BUILD_ID,
            },
        )
    )

    service = ForestPackControlService()
    scene_state = SceneStateGateway(service)
    scene_runtime = ForestSceneRuntime(service=service)

    manifest = scene_state.read_manifest(preflight=False)
    groups = SceneStateGateway.groups(manifest)
    forest_name = str(manifest.get("primary_forest") or "FM_Forest_001").strip() or "FM_Forest_001"

    checks.append(_check("manifest_has_executable_groups", bool(groups), {"group_count": len(groups)}))
    checks.append(
        _check(
            "single_primary_forest_contract",
            forest_name == "FM_Forest_001",
            {"primary_forest": forest_name},
        )
    )

    before_sources = _geometry_source_count(service, forest_name)
    first = scene_runtime.execute_manifest(manifest, strict_acceptance=False)
    after_first_sources = _geometry_source_count(service, forest_name)
    second = scene_runtime.execute_manifest(manifest, strict_acceptance=False)
    after_second_sources = _geometry_source_count(service, forest_name)

    checks.append(
        _check(
            "manifest_execution_verified_twice",
            first.get("verified") is True and second.get("verified") is True,
            {
                "first_verified": first.get("verified"),
                "second_verified": second.get("verified"),
            },
        )
    )
    checks.append(
        _check(
            "geometry_sources_idempotent",
            before_sources == after_first_sources == after_second_sources,
            {
                "before": before_sources,
                "after_first": after_first_sources,
                "after_second": after_second_sources,
            },
        )
    )

    units = service.scene_units(preflight=False)
    system_value = UnitConversionGateway.display_to_system(75.0, units)
    roundtrip_display, suffix = UnitConversionGateway.system_to_display(system_value, units)
    checks.append(
        _check(
            "active_scene_unit_roundtrip",
            abs(roundtrip_display - 75.0) < 1e-9,
            {
                "display_unit": units.display_unit,
                "system_type": units.system_type,
                "one_meter_system_units": units.one_meter_system_units,
                "input_display": 75.0,
                "system_value": system_value,
                "roundtrip_display": roundtrip_display,
                "suffix": suffix,
            },
        )
    )

    first_controller = ForestManagerUIController()
    first_state = first_controller.refresh_scene(prefer_max_selection=False)
    second_controller = ForestManagerUIController()
    second_state = second_controller.refresh_scene(prefer_max_selection=False)

    first_snapshot = _group_snapshot(first_state)
    second_snapshot = _group_snapshot(second_state)
    checks.append(
        _check(
            "fresh_controller_scene_reconstruction",
            bool(first_snapshot) and first_snapshot == second_snapshot,
            {
                "before_count": len(first_snapshot),
                "after_count": len(second_snapshot),
                "equal": first_snapshot == second_snapshot,
            },
        )
    )
    checks.append(
        _check(
            "fresh_controller_pending_empty",
            second_state.pending_edits == (),
            {"pending_count": len(second_state.pending_edits)},
        )
    )
    checks.append(
        _check(
            "fresh_controller_selection_clean",
            second_state.selected_group_id is None,
            {"selected_group_id": second_state.selected_group_id},
        )
    )

    ok = all(item["passed"] for item in checks)
    return {
        "ok": ok,
        "acceptance": "forest_manager_official_runtime",
        "map_policy": "parked_not_part_of_official_acceptance",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
    }


def main() -> int:
    try:
        report = run_acceptance()
    except Exception as exc:
        report = {
            "ok": False,
            "acceptance": "forest_manager_official_runtime",
            "map_policy": "parked_not_part_of_official_acceptance",
            "error": type(exc).__name__ + ": " + str(exc),
            "checks": [],
        }

    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
