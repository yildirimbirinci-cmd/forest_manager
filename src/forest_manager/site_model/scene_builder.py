from __future__ import annotations

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, list_closed_spline_candidates

from .model import SiteBoundary, SiteModel


class SiteModelBuilder:
    """Build the Stage 8 site model from live 3ds Max scene geometry."""

    def discover(self, *, reference_image_path: str | None = None) -> SiteModel:
        ensure_current_bridge()
        raw = list_closed_spline_candidates()
        boundaries = tuple(
            SiteBoundary.from_bridge(item)
            for item in raw
            if str(item.get("node_name") or "").strip()
        )
        if not boundaries:
            raise RuntimeError("No closed spline boundary was found in the active 3ds Max scene.")

        # Prefer artist geometry over FM-generated helpers.  Within that set,
        # choose the largest closed region as the initial project boundary.
        artist = tuple(item for item in boundaries if not item.forest_manager_owned)
        pool = artist or boundaries
        primary = max(pool, key=lambda item: (item.area_square_meters, item.node_name.lower()))
        return SiteModel(
            primary_boundary=primary,
            boundaries=boundaries,
            reference_image_path=reference_image_path,
        )
