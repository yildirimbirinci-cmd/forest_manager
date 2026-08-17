from __future__ import annotations

import argparse
import json
import time

from forest_manager.forest_control.planting_plan_service import Forest01FoundationService
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge
from forest_manager.site_model import PlantingPlanBuilder, SiteModelBuilder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 8 foundation acceptance")
    parser.add_argument("--ensure-forest", action="store_true", help="Create/reuse FM_Forest_001 on the detected closed spline.")
    parser.add_argument("--reference-image", default=None, help="Optional reference image path stored in the foundation plan.")
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

        plan = PlantingPlanBuilder().bootstrap(site, reference_image_path=args.reference_image)
        service = Forest01FoundationService()
        validation = service.validate_plan(plan)
        checks.append({"name": "three_group_planting_plan", "passed": validation["group_count"] == 3, "detail": validation})

        if args.ensure_forest:
            result = service.ensure_forest(site)
            checks.append({"name": "primary_forest_ensure", "passed": result.get("verified") is True, "detail": result})

        ok = all(bool(item.get("passed")) for item in checks)
        payload = {
            "ok": ok,
            "stage": "8-foundation",
            "mutated_scene": bool(args.ensure_forest),
            "reference_image": args.reference_image,
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "stage": "8-foundation",
            "mutated_scene": bool(args.ensure_forest),
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
