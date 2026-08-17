from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from forest_manager.forest_control.stage8_scene_execution import Stage8PlantingPlanSceneExecutor
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge
from forest_manager.site_model import (
    PlantingPlanBuilder,
    ReferenceImageAnalyzer,
    SiteModelBuilder,
    SpeciesCatalogResolver,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 reference-image scene execution acceptance")
    parser.add_argument("--reference-image", required=True)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    checks: list[dict] = []
    try:
        ping = ensure_current_bridge()
        checks.append({"name": "bridge_preflight", "passed": True, "detail": ping.get("data") or ping})

        site = SiteModelBuilder().discover(reference_image_path=args.reference_image)
        checks.append({
            "name": "closed_spline_site_model",
            "passed": site.primary_boundary.area_square_meters > 0.0,
            "detail": {
                "primary_boundary": site.primary_boundary.node_name,
                "area_square_meters": site.primary_boundary.area_square_meters,
                "width_system_units": site.primary_boundary.width_system_units,
                "depth_system_units": site.primary_boundary.depth_system_units,
            },
        })

        analysis = ReferenceImageAnalyzer().analyze(args.reference_image, output_dir=args.output_dir)
        unresolved_plan = PlantingPlanBuilder().from_reference_image(site, analysis)
        plan = SpeciesCatalogResolver().resolve_plan(unresolved_plan)
        checks.append({
            "name": "execution_ready_visual_plan",
            "passed": plan.execution_ready and plan.visual_intent_ready,
            "detail": {
                "execution_ready": plan.execution_ready,
                "visual_intent_ready": plan.visual_intent_ready,
                "groups": [
                    {
                        "group_id": group.group_id,
                        "source_names": list(group.source_names),
                        "coverage_weight": group.coverage_weight,
                        "naturalness": group.naturalness,
                        "cluster_character": group.cluster_character,
                        "zone_mask_path": group.zone_mask_path,
                    }
                    for group in plan.groups
                ],
            },
        })

        scene_result = Stage8PlantingPlanSceneExecutor().execute(plan)
        diagnostics = scene_result.get("diagnostics") or {}
        generated = diagnostics.get("generated_geometry_ids") or []
        checks.append({
            "name": "scene_execution",
            "passed": scene_result.get("verified") is True,
            "detail": {
                "forest": scene_result.get("forest"),
                "geometry": scene_result.get("geometry"),
                "t2_assets_merged": (scene_result.get("geometry") or {}).get("merged_from_t2") or [],
                "generated_items": diagnostics.get("generated_items"),
                "generated_geometry_ids": generated,
                "map_path": diagnostics.get("map_path"),
                "map_source_kind": (scene_result.get("execution") or {}).get("map_source_kind"),
                "map_source_paths": (scene_result.get("execution") or {}).get("map_source_paths") or [],
            },
        })
        execution_detail = scene_result.get("execution") or {}
        expected_zone_paths = [str(Path(group.zone_mask_path).expanduser().resolve()) for group in plan.groups]
        actual_source_paths = [str(Path(value).expanduser().resolve()) for value in execution_detail.get("map_source_paths") or []]
        checks.append({
            "name": "reference_zone_masks_bound",
            "passed": (
                execution_detail.get("map_source_kind") == "manifest_zone_masks"
                and actual_source_paths == expected_zone_paths
            ),
            "detail": {
                "map_source_kind": execution_detail.get("map_source_kind"),
                "expected_zone_paths": expected_zone_paths,
                "actual_source_paths": actual_source_paths,
            },
        })
        checks.append({
            "name": "three_species_generated",
            "passed": len([item for item in generated if int(item.get("generated_items") or 0) > 0]) >= 3,
            "detail": generated,
        })

        payload = {
            "ok": all(bool(item.get("passed")) for item in checks),
            "stage": "8-reference-image-scene-execution",
            "mutated_scene": True,
            "reference_image": str(Path(args.reference_image).expanduser().resolve()),
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-reference-image-scene-execution",
            "mutated_scene": True,
            "reference_image": str(Path(args.reference_image).expanduser().resolve()),
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
            "error": f"{type(exc).__name__}: {exc}",
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
