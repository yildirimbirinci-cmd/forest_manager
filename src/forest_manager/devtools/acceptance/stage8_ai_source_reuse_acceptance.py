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
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 AI source reuse acceptance")
    parser.add_argument("--reference-image", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8089/v1/chat/completions")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        provider = LocalVisionProvider(endpoint=args.endpoint)
        analysis = ReferenceImageAnalyzer().analyze_with_provider(args.reference_image, provider)
        site = SiteModelBuilder().discover(reference_image_path=args.reference_image)
        plan = PlantingPlanBuilder().from_reference_image(site, analysis)
        pipeline = OfficialStage8PlantingPipeline()
        prepared = pipeline.prepare_ai_candidates(plan, policy=_spacing_policy(plan))
        report = pipeline.inspect_scene_sources(prepared, preflight=True)
        payload = {
            "ok": True,
            "stage": "8-ai-source-reuse",
            "mutated_scene": False,
            "forest_name": report.forest_name,
            "existing_sources": list(report.existing_sources),
            "reuse_sources": list(report.reuse_sources),
            "missing_sources": [dict(item) for item in report.missing_sources],
            "ready_without_merge": report.ready,
            "resolved_group_count": len(prepared.resolved_plan.groups),
            "total_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-ai-source-reuse",
            "mutated_scene": False,
            "error": f"{type(exc).__name__}: {exc}",
            "total_seconds": round(time.perf_counter() - started, 3),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
