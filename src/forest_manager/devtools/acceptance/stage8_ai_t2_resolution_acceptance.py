from __future__ import annotations

import argparse
import json
import time

from forest_manager.forest_control.official_planting_pipeline import OfficialStage8PlantingPipeline
from forest_manager.forest_control.runtime_manifest import MapFreeManifestPolicy
from forest_manager.site_model import PlantingPlanBuilder, SiteModelBuilder
from forest_manager.site_model.local_vision_provider import LocalVisionProvider
from forest_manager.site_model.reference_image import ReferenceImageAnalyzer


_COMPACT_ROLES = {"purple_accent", "flower_accent", "groundcover", "ornamental_grass"}


def _spacing_policy(plan) -> MapFreeManifestPolicy:
    return MapFreeManifestPolicy({
        group.group_id: 2500.0 if group.semantic_role in _COMPACT_ROLES else 7500.0
        for group in plan.groups
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 AI to T2 resolution acceptance")
    parser.add_argument("--reference-image", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8089/v1/chat/completions")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        provider = LocalVisionProvider(endpoint=args.endpoint)
        analysis = ReferenceImageAnalyzer().analyze_with_provider(args.reference_image, provider)
        site = SiteModelBuilder().discover(reference_image_path=args.reference_image)
        plan = PlantingPlanBuilder().from_reference_image(site, analysis)
        prepared = OfficialStage8PlantingPipeline().prepare_ai_candidates(
            plan,
            policy=_spacing_policy(plan),
        )
        active = [item for item in prepared.asset_resolution if not item.get("excluded")]
        excluded = [item for item in prepared.asset_resolution if item.get("excluded")]
        payload = {
            "ok": bool(active) and bool(prepared.manifest.get("groups")),
            "stage": "8-ai-t2-resolution",
            "mutated_scene": False,
            "provider": analysis.analysis_provider,
            "model": analysis.analysis_model,
            "ai_group_count": len(analysis.zones),
            "resolved_group_count": len(prepared.resolved_plan.groups),
            "excluded_group_count": len(excluded),
            "asset_resolution": active,
            "excluded_groups": excluded,
            "manifest": prepared.manifest,
            "map_policy": prepared.manifest.get("map_policy"),
            "total_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-ai-t2-resolution",
            "mutated_scene": False,
            "error": f"{type(exc).__name__}: {exc}",
            "total_seconds": round(time.perf_counter() - started, 3),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
