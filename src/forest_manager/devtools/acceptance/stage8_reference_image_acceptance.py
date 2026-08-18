from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from forest_manager.forest_control.planting_plan_service import Forest01FoundationService
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge
from forest_manager.site_model import PlantingPlanBuilder, ReferenceImageAnalyzer, SiteModelBuilder


DEMO_SOURCES = {
    "foreground_mass": ("Lavandula angustifolia 'Hidcote' (Lavender)",),
    "mid_accent": ("Butomus umbellatus (Flowering rush )",),
    "structural_shrub": ("Bush_Berberis",),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 reference-image intent acceptance")
    parser.add_argument("--reference-image", required=True, help="Reference planting image to analyze.")
    parser.add_argument("--output-dir", default=None, help="Directory for generated semantic zone masks.")
    parser.add_argument(
        "--use-stage7-demo-species",
        action="store_true",
        help="Resolve the three semantic groups to the existing Stage 7 development species set.",
    )
    parser.add_argument("--write-plan", default=None, help="Optional JSON path for the generated PlantingPlan summary.")
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
                "candidate_count": len(site.boundaries),
            },
        })

        analyzer = ReferenceImageAnalyzer()
        analysis = analyzer.analyze(args.reference_image, output_dir=args.output_dir)
        analysis_dict = analyzer.to_dict(analysis)
        masks_exist = all(Path(zone["mask_path"]).is_file() for zone in analysis_dict["zones"] if zone.get("mask_path"))
        coverage_total = float(analysis_dict["coverage_total"])
        checks.append({
            "name": "reference_image_semantic_analysis",
            "passed": bool(analysis.zones) and masks_exist and abs(coverage_total - 1.0) <= 1e-6,
            "detail": analysis_dict,
        })

        source_names = DEMO_SOURCES if args.use_stage7_demo_species else None
        plan = PlantingPlanBuilder().from_reference_image(site, analysis, source_names=source_names)
        validation = Forest01FoundationService().validate_plan(plan)
        checks.append({
            "name": "visual_intent_planting_plan",
            "passed": validation["group_count"] == len(analysis.zones) and validation["visual_intent_ready"] is True,
            "detail": validation,
        })

        if args.use_stage7_demo_species:
            checks.append({
                "name": "execution_ready_with_demo_species",
                "passed": validation["execution_ready"] is True,
                "detail": validation["unresolved_group_ids"],
            })

        payload = {
            "ok": all(bool(item.get("passed")) for item in checks),
            "stage": "8-reference-image-intent",
            "mutated_scene": False,
            "reference_image": str(Path(args.reference_image).expanduser().resolve()),
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
        }
        if args.write_plan:
            destination = Path(args.write_plan).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            payload["written_plan"] = str(destination)
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-reference-image-intent",
            "mutated_scene": False,
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
            "error": f"{type(exc).__name__}: {exc}",
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
