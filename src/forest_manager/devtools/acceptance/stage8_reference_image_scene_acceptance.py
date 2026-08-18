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
        checks.append({
            "name": "ai_vision_analysis",
            "passed": analysis.analysis_provider not in {"", "unknown", "legacy"} and len(analysis.zones) > 0,
            "detail": {
                "provider": analysis.analysis_provider,
                "model": analysis.analysis_model,
                "candidate_count": len(analysis.zones),
                "scene_summary": analysis.scene_summary,
                "candidates": [
                    {
                        "label": zone.label,
                        "scientific_name": zone.scientific_name,
                        "common_name": zone.common_name,
                        "growth_form": zone.growth_form,
                        "flower_color": zone.flower_color,
                        "confidence": zone.confidence,
                    }
                    for zone in analysis.zones
                ],
            },
        })
        plan = PlantingPlanBuilder().from_reference_image(site, analysis)
        checks.append({
            "name": "ai_visual_plan_ready_for_t2_resolution",
            "passed": plan.visual_intent_ready and bool(plan.groups),
            "detail": {
                "execution_ready_before_t2_resolution": plan.execution_ready,
                "visual_intent_ready": plan.visual_intent_ready,
                "groups": [
                    {
                        "group_id": group.group_id,
                        "source_names": list(group.source_names),
                        "coverage_weight": group.coverage_weight,
                        "naturalness": group.naturalness,
                        "cluster_character": group.cluster_character,
                        "zone_mask_path": group.zone_mask_path,
                        "scientific_name_hint": group.scientific_name_hint,
                        "common_name_hint": group.common_name_hint,
                        "growth_form": group.growth_form,
                        "model_match_confidence": group.model_match_confidence,
                        "resolved_asset_path": group.resolved_asset_path,
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
                "ai_asset_resolution": scene_result.get("ai_asset_resolution") or [],
                "t2_assets_merged": (scene_result.get("geometry") or {}).get("merged_from_t2") or [],
                "generated_items": diagnostics.get("generated_items"),
                "generated_geometry_ids": generated,
                "map_path": diagnostics.get("map_path"),
                "map_source_kind": (scene_result.get("execution") or {}).get("map_source_kind"),
                "map_source_paths": (scene_result.get("execution") or {}).get("map_source_paths") or [],
            },
        })
        pre_scene_readiness = scene_result.get("pre_scene_readiness") or {}
        checks.append({
            "name": "pre_scene_readiness_verified_before_mutation",
            "passed": (
                pre_scene_readiness.get("ready") is True
                and int(pre_scene_readiness.get("ready_group_count") or 0) == len(plan.groups)
            ),
            "detail": pre_scene_readiness,
        })

        ai_asset_resolution = scene_result.get("ai_asset_resolution") or []
        merged_from_t2 = (scene_result.get("geometry") or {}).get("merged_from_t2") or []
        selected_paths = {
            str(Path(item.get("resolved_asset_path") or "").expanduser().resolve())
            for item in ai_asset_resolution
            if isinstance(item, dict) and item.get("resolved_asset_path")
        }
        merged_paths = {
            str(Path(item.get("asset_path") or "").expanduser().resolve())
            for item in merged_from_t2
            if isinstance(item, dict) and item.get("asset_path")
        }
        checks.append({
            "name": "ai_selected_asset_identity_preserved",
            "passed": bool(selected_paths) and merged_paths.issubset(selected_paths),
            "detail": {
                "ai_selected_paths": sorted(selected_paths),
                "merged_paths": sorted(merged_paths),
                "all_merged_paths_were_ai_selected": merged_paths.issubset(selected_paths),
            },
        })

        execution_lineage = scene_result.get("execution_lineage") or []
        lineage_group_ids = {
            str(item.get("group_id") or "")
            for item in execution_lineage
            if isinstance(item, dict) and item.get("verified") is True
        }
        planned_group_ids = {str(group.group_id) for group in plan.groups}
        checks.append({
            "name": "exact_group_asset_scene_species_lineage",
            "passed": (
                bool(planned_group_ids)
                and lineage_group_ids == planned_group_ids
                and all(
                    int(item.get("generated_items") or 0) > 0
                    or (
                        item.get("verified") is True
                        and str(item.get("generated_item_verification_mode") or "") in {"single_forest_binding", "map_free_total_binding"}
                    )
                    for item in execution_lineage
                )
                and all(item.get("diversity_binding_mode") == "map_free_random" for item in execution_lineage)
            ),
            "detail": {
                "planned_group_ids": sorted(planned_group_ids),
                "verified_lineage_group_ids": sorted(lineage_group_ids),
                "execution_lineage": execution_lineage,
            },
        })

        execution_detail = scene_result.get("execution") or {}
        map_binding = execution_detail.get("map_binding") or {}
        checks.append({
            "name": "map_pipeline_disabled",
            "passed": (
                execution_detail.get("map_source_kind") == "disabled_map_free"
                and map_binding.get("enabled") is False
                and not str(map_binding.get("map_path") or "")
            ),
            "detail": {
                "map_source_kind": execution_detail.get("map_source_kind"),
                "map_binding": map_binding,
            },
        })
        map_free_mode = execution_detail.get("map_source_kind") == "disabled_map_free"
        if map_free_mode:
            generated_positive = [
                item
                for item in execution_lineage
                if isinstance(item, dict)
                and item.get("verified") is True
                and str(item.get("generated_item_verification_mode") or "") == "map_free_total_binding"
            ]
        else:
            generated_positive = [
                item
                for item in generated
                if int(item.get("generated_items") or 0) > 0
                or (
                    item.get("verified") is True
                    and str(item.get("generated_item_verification_mode") or "") == "single_forest_binding"
                )
            ]
        planned_group_count = len(plan.groups)
        checks.append({
            "name": "all_planned_species_generated",
            "passed": len(generated_positive) >= planned_group_count,
            "detail": {
                "planned_group_count": planned_group_count,
                "generated_positive_count": len(generated_positive),
                "generated_geometry_ids": generated,
            },
        })

        checks.append({
            "name": "random_diversity_species_runtime",
            "passed": (
                execution_detail.get("map_source_kind") == "disabled_map_free"
                and len(generated_positive) >= planned_group_count
                and all(item.get("diversity_binding_mode") == "map_free_random" for item in execution_lineage)
            ),
            "detail": {
                "planned_group_count": planned_group_count,
                "generated_positive_count": len(generated_positive),
                "map_source_kind": execution_detail.get("map_source_kind"),
                "execution_lineage": execution_lineage,
            },
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
