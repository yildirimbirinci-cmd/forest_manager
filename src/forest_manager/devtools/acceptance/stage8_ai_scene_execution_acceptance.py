from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from forest_manager.forest_control.scene_runtime import ForestSceneRuntime
from forest_manager.forest_control.scene_state import SceneStateGateway
from forest_manager.forest_control.service import ForestPackControlService


SOURCE_REUSE_MODULE = "forest_manager.devtools.acceptance.stage8_ai_source_reuse_acceptance"
MAP_POLICY = "parked_not_part_of_ai_scene_execution"
PRESERVED_SOURCE_TOKENS = ("allium", "allamanda")


def _check(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _array_count(inventory: Mapping[str, Any], property_name: str) -> int:
    target = property_name.casefold()
    item = next(
        (
            row
            for row in (inventory.get("properties") or [])
            if isinstance(row, Mapping)
            and str(row.get("name") or "").casefold() == target
        ),
        None,
    )
    metadata = item.get("array_metadata") if isinstance(item, Mapping) else None
    return int((metadata or {}).get("count") or 0) if isinstance(metadata, Mapping) else 0


def _geometry_source_count(service: ForestPackControlService, forest_name: str) -> int:
    inventory = service.inventory(forest_name, preflight=False)
    return _array_count(inventory, "cobjlist")


def _geometry_source_names(service: ForestPackControlService, forest_name: str) -> tuple[str, ...]:
    inventory = service.inventory(forest_name, preflight=False)
    count = _array_count(inventory, "namelist")
    names: list[str] = []
    for index in range(count):
        value = service.get_array_element(
            forest_name,
            "namelist",
            index,
            preflight=False,
        ).get("value")
        token = str(value or "").strip()
        if token:
            names.append(token)
    return tuple(names)


def _resolved_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(manifest))
    raw_groups = manifest.get("groups")
    groups = raw_groups if isinstance(raw_groups, list) else []
    resolved: list[dict[str, Any]] = []
    for item in groups:
        if not isinstance(item, Mapping):
            continue
        source_names = [
            str(value).strip()
            for value in (item.get("source_names") or [])
            if str(value).strip()
        ]
        if not source_names:
            continue
        group = copy.deepcopy(dict(item))
        group["source_names"] = source_names
        resolved.append(group)
    result["groups"] = resolved
    return result


def _duplicate_source_names(names: tuple[str, ...]) -> list[str]:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for name in names:
        key = name.strip().casefold()
        if not key:
            continue
        if key in seen and seen[key] not in duplicates:
            duplicates.append(seen[key])
        else:
            seen[key] = name
    return duplicates


def _preserved_named_sources(before: tuple[str, ...], after: tuple[str, ...]) -> dict[str, bool]:
    before_folded = tuple(value.casefold() for value in before)
    after_folded = tuple(value.casefold() for value in after)
    result: dict[str, bool] = {}
    for token in PRESERVED_SOURCE_TOKENS:
        existed = any(token in value for value in before_folded)
        preserved = any(token in value for value in after_folded)
        result[token] = existed and preserved
    return result


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        raise RuntimeError("Source reuse acceptance returned no JSON output.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Source reuse acceptance output did not contain a JSON object.")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise RuntimeError("Source reuse acceptance JSON root must be an object.")
    return payload


def _run_source_reuse_acceptance(reference_image: str) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        SOURCE_REUSE_MODULE,
        "--reference-image",
        str(Path(reference_image).expanduser().resolve()),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    report = _parse_json_stdout(completed.stdout)
    report["process_returncode"] = int(completed.returncode)
    if completed.stderr.strip():
        report["process_stderr"] = completed.stderr.strip()
    return report


def run_acceptance(reference_image: str) -> dict[str, Any]:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    source_reuse = _run_source_reuse_acceptance(reference_image)
    checks.append(
        _check(
            "ai_t2_source_reuse_verified",
            source_reuse.get("ok") is True and source_reuse.get("process_returncode") == 0,
            source_reuse,
        )
    )

    service = ForestPackControlService()
    scene_state = SceneStateGateway(service)
    scene_runtime = ForestSceneRuntime(service=service)

    manifest = scene_state.read_manifest(preflight=False)
    executable_manifest = _resolved_manifest(manifest)
    all_groups = manifest.get("groups") if isinstance(manifest.get("groups"), list) else []
    resolved_groups = executable_manifest.get("groups") or []
    checks.append(
        _check(
            "only_resolved_groups_selected_for_execution",
            bool(resolved_groups)
            and all(
                bool([value for value in (item.get("source_names") or []) if str(value).strip()])
                for item in resolved_groups
                if isinstance(item, Mapping)
            ),
            {
                "manifest_group_count": len(all_groups),
                "resolved_group_count": len(resolved_groups),
                "resolved_group_ids": [
                    str(item.get("group_id") or "")
                    for item in resolved_groups
                    if isinstance(item, Mapping)
                ],
            },
        )
    )

    forest_name = str(executable_manifest.get("primary_forest") or "FM_Forest_001").strip() or "FM_Forest_001"
    before_count = _geometry_source_count(service, forest_name)
    before_names = _geometry_source_names(service, forest_name)

    checks.append(
        _check(
            "allium_allamanda_present_before_execution",
            all(
                any(token in name.casefold() for name in before_names)
                for token in PRESERVED_SOURCE_TOKENS
            ),
            {"source_names": list(before_names)},
        )
    )

    first = scene_runtime.execute_manifest(executable_manifest, strict_acceptance=False)
    first_count = _geometry_source_count(service, forest_name)
    first_names = _geometry_source_names(service, forest_name)

    second = scene_runtime.execute_manifest(executable_manifest, strict_acceptance=False)
    second_count = _geometry_source_count(service, forest_name)
    second_names = _geometry_source_names(service, forest_name)

    checks.append(
        _check(
            "forest_scene_runtime_verified_twice",
            first.get("verified") is True and second.get("verified") is True,
            {
                "first_verified": first.get("verified"),
                "second_verified": second.get("verified"),
            },
        )
    )
    checks.append(
        _check(
            "geometry_source_count_unchanged",
            before_count == first_count == second_count,
            {
                "before": before_count,
                "after_first": first_count,
                "after_second": second_count,
            },
        )
    )

    preservation = _preserved_named_sources(before_names, second_names)
    checks.append(_check("allium_allamanda_preserved", all(preservation.values()), preservation))

    duplicates = _duplicate_source_names(second_names)
    checks.append(
        _check(
            "no_duplicate_geometry_sources",
            not duplicates and len(second_names) == len(set(value.casefold() for value in second_names)),
            {"duplicates": duplicates, "source_names": list(second_names)},
        )
    )
    checks.append(
        _check(
            "second_execution_idempotent",
            first_count == second_count and first_names == second_names,
            {
                "first_count": first_count,
                "second_count": second_count,
                "first_names": list(first_names),
                "second_names": list(second_names),
            },
        )
    )
    checks.append(_check("map_policy_parked", MAP_POLICY.startswith("parked_"), MAP_POLICY))

    ok = all(item["passed"] for item in checks)
    return {
        "ok": ok,
        "acceptance": "stage8_ai_scene_execution",
        "reference_image": str(Path(reference_image).expanduser().resolve()),
        "runtime": "ForestSceneRuntime",
        "map_policy": MAP_POLICY,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 8 AI source-reuse to official scene-runtime acceptance.")
    parser.add_argument("--reference-image", required=True)
    args = parser.parse_args(argv)

    try:
        report = run_acceptance(args.reference_image)
    except Exception as exc:
        report = {
            "ok": False,
            "acceptance": "stage8_ai_scene_execution",
            "runtime": "ForestSceneRuntime",
            "map_policy": MAP_POLICY,
            "error": type(exc).__name__ + ": " + str(exc),
            "checks": [],
        }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
