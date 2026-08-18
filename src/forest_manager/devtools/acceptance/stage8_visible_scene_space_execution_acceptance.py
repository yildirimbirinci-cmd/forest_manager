from __future__ import annotations

import argparse
import json
import time
from typing import Any

from forest_manager.forest_control.ai_t2_scene_region_runtime import resolve_ai_t2_runtime_groups
from forest_manager.forest_control.scene_runtime import ForestSceneRuntime
from forest_manager.forest_control.service import ForestPackControlService
from forest_manager.forest_control.stage8_asset_resolution import Stage8T2AssetResolver


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-image", required=True)
    return parser


def _resolution_by_source(resolution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in resolution.get("asset_resolution") or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("resolved_name") or "").strip()
        if source:
            result[source] = item
    return result


def _prepare_geometry_sources(
    manifest: dict[str, Any],
    resolution: dict[str, Any],
    *,
    service: ForestPackControlService,
) -> dict[str, Any]:
    forest_name = str(manifest.get("primary_forest") or "FM_Forest_001").strip() or "FM_Forest_001"
    resolver = Stage8T2AssetResolver(control_service=service)
    existing = list(resolver.list_geometry_source_names(forest_name, preflight=True))
    before = list(existing)
    resolution_map = _resolution_by_source(resolution)
    actions: list[dict[str, Any]] = []

    required: list[str] = []
    for group in manifest.get("groups") or []:
        if not isinstance(group, dict):
            continue
        for name in group.get("source_names") or []:
            source = str(name or "").strip()
            if source and source not in required:
                required.append(source)

    for source in required:
        if source in existing:
            actions.append({"source_name": source, "action": "reuse_geometry_list", "verified": True})
            continue

        # Reuse an already-present scene node first. This is the safest and
        # cheapest path and preserves the existing FM_References lifecycle.
        try:
            reuse = service.add_geometry_source_by_name(forest_name, source, preflight=False)
        except Exception as exc:
            reuse = {"verified": False, "error": f"{type(exc).__name__}: {exc}"}

        refreshed = list(resolver.list_geometry_source_names(forest_name, preflight=False))
        if source in refreshed:
            existing = refreshed
            actions.append({"source_name": source, "action": "reuse_scene_node", "verified": True})
            continue

        info = resolution_map.get(source)
        if not info:
            raise RuntimeError(f"No T2 resolution evidence is available for missing source: {source}")
        asset_path = str(info.get("asset_path") or "").strip()
        if not asset_path:
            raise RuntimeError(f"Resolved source has no T2 asset path: {source}")

        merged = resolver.merge_resolved_asset(
            asset_path=asset_path,
            requested_name=str(info.get("requested_name") or source),
            semantic_role=str(info.get("semantic_role") or ""),
            geometry_count=len(existing),
        )
        refreshed = list(resolver.list_geometry_source_names(forest_name, preflight=False))
        if source not in refreshed:
            raise RuntimeError(
                f"T2 merge completed but source was not bound to {forest_name} Geometry List: {source}"
            )
        existing = refreshed
        actions.append({
            "source_name": source,
            "action": "merge_t2_asset",
            "asset_path": asset_path,
            "verified": bool(merged.get("verified")),
        })

    missing_after = [source for source in required if source not in existing]
    if missing_after:
        raise RuntimeError("Required Geometry sources remain missing: " + ", ".join(missing_after))

    lowered = [name.casefold() for name in existing]
    duplicates = sorted({name for name in existing if lowered.count(name.casefold()) > 1})
    if duplicates:
        raise RuntimeError("Duplicate Geometry sources detected after preparation: " + ", ".join(duplicates))

    return {
        "forest_name": forest_name,
        "before_sources": before,
        "after_sources": existing,
        "required_sources": required,
        "actions": actions,
        "missing_after": missing_after,
        "duplicates": duplicates,
        "verified": True,
    }


def main() -> int:
    args = _parser().parse_args()
    started = time.perf_counter()
    resolution, groups, group_source = resolve_ai_t2_runtime_groups(args.reference_image)
    manifest = dict(resolution.get("manifest") or {})
    if not manifest.get("groups"):
        raise SystemExit("AI/T2 resolution returned no executable manifest groups.")

    service = ForestPackControlService()
    source_preparation = _prepare_geometry_sources(manifest, resolution, service=service)

    runtime = ForestSceneRuntime(service=service)
    first = runtime.execute_manifest(manifest, strict_acceptance=False)
    second = runtime.execute_manifest(manifest, strict_acceptance=False)

    expected_sources = [
        name
        for group in manifest["groups"]
        for name in (group.get("source_names") or [])
    ]
    checks = [
        {
            "name": "resolved_groups_execute",
            "passed": len(groups) > 0 and len(first.get("groups") or []) == len(groups),
            "detail": {"resolved": len(groups), "executed": len(first.get("groups") or [])},
        },
        {
            "name": "all_resolved_sources_prepared",
            "passed": source_preparation["verified"] is True
            and not source_preparation["missing_after"]
            and not source_preparation["duplicates"]
            and all(source in source_preparation["after_sources"] for source in expected_sources),
            "detail": source_preparation,
        },
        {
            "name": "scene_space_map_bound",
            "passed": first.get("map_binding", {}).get("verified") is True
            and first.get("map_source_kind") == "selected_3ds_max_boundary_semantic_regions",
            "detail": {
                "map_source_kind": first.get("map_source_kind"),
                "map_path": (first.get("map_source_paths") or [""])[0],
            },
        },
        {
            "name": "color_ids_applied_to_all_groups",
            "passed": len(first.get("color_id_results") or []) >= len(groups)
            and all(item.get("verified") for item in first.get("color_id_results") or []),
            "detail": first.get("color_id_results"),
        },
        {
            "name": "real_site_polygon_used",
            "passed": first.get("site_polygon", {}).get("verified") is True
            and int(first.get("site_polygon", {}).get("sample_count") or 0) >= 3,
            "detail": first.get("site_polygon"),
        },
        {
            "name": "reference_pixels_not_projected",
            "passed": first.get("distribution_threshold", {}).get("reference_image_projection") is False,
            "detail": first.get("distribution_threshold"),
        },
        {
            "name": "second_execution_idempotent",
            "passed": second.get("verified") is True
            and second.get("map_source_kind") == first.get("map_source_kind"),
            "detail": {"first_verified": first.get("verified"), "second_verified": second.get("verified")},
        },
    ]
    payload = {
        "ok": all(item["passed"] for item in checks),
        "acceptance": "stage8_visible_scene_space_execution",
        "reference_image": args.reference_image,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "forest_name": first.get("forest_name"),
        "resolved_sources": expected_sources,
        "group_source": group_source,
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
