from __future__ import annotations

import argparse
import json
import time

from forest_manager.site_model.local_vision_provider import LocalVisionProvider
from forest_manager.site_model.reference_image import ReferenceImageAnalyzer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 local vision provider acceptance")
    parser.add_argument("--reference-image", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8089/v1/chat/completions")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        provider = LocalVisionProvider(endpoint=args.endpoint)
        analysis = ReferenceImageAnalyzer().analyze_with_provider(args.reference_image, provider)
        payload = {
            "ok": bool(analysis.zones) and abs(analysis.coverage_total - 1.0) <= 1e-6,
            "stage": "8-local-vision-provider",
            "mutated_scene": False,
            "provider": analysis.analysis_provider,
            "model": analysis.analysis_model,
            "analysis_version": analysis.analysis_version,
            "group_count": len(analysis.zones),
            "coverage_total": analysis.coverage_total,
            "groups": [
                {
                    "semantic_role": zone.semantic_role,
                    "label": zone.label,
                    "coverage_weight": zone.coverage_weight,
                    "naturalness": zone.naturalness,
                    "cluster_character": zone.cluster_character,
                    "confidence": zone.confidence,
                    "source_names": list(zone.source_names),
                }
                for zone in analysis.zones
            ],
            "total_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-local-vision-provider",
            "mutated_scene": False,
            "error": f"{type(exc).__name__}: {exc}",
            "total_seconds": round(time.perf_counter() - started, 3),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
