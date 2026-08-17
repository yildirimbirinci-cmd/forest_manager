from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from forest_manager.forest_control.planting_plan_service import Forest01FoundationService
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge
from forest_manager.site_model import (
    PlantingPlanBuilder,
    ReferenceImageAnalyzer,
    SiteModelBuilder,
    SpeciesCatalogResolver,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 reference-image species-resolution acceptance")
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
            },
        })

        analyzer = ReferenceImageAnalyzer()
        analysis = analyzer.analyze(args.reference_image, output_dir=args.output_dir)
        plan = PlantingPlanBuilder().from_reference_image(site, analysis)
        resolver = SpeciesCatalogResolver()
        resolved_plan = resolver.resolve_plan(plan)
        validation = Forest01FoundationService().validate_plan(resolved_plan)

        checks.append({
            "name": "species_catalog_resolution",
            "passed": validation["execution_ready"] is True and not validation["unresolved_group_ids"],
            "detail": {
                "catalog": resolver.summary(),
                "groups": validation["groups"],
            },
        })
        checks.append({
            "name": "execution_ready_visual_plan",
            "passed": validation["visual_intent_ready"] is True and validation["execution_ready"] is True,
            "detail": validation,
        })

        payload = {
            "ok": all(bool(item.get("passed")) for item in checks),
            "stage": "8-reference-image-species-resolution",
            "mutated_scene": False,
            "reference_image": str(Path(args.reference_image).expanduser().resolve()),
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-reference-image-species-resolution",
            "mutated_scene": False,
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
            "error": f"{type(exc).__name__}: {exc}",
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
