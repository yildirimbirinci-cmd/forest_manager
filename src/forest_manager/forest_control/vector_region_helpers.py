from __future__ import annotations

import re
from typing import Any, Mapping

from forest_manager.max_bridge.runtime_bridge import (
    delete_stage8_vector_region_helper,
    ensure_stage8_helper_layer,
    list_stage8_vector_region_helpers,
    upsert_stage8_vector_region_helper,
)


class VectorRegionHelperError(RuntimeError):
    pass


def _safe_source_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))


def _helper_specs(zones: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = str(zones.get("node_name") or "").strip()
    if not source:
        raise VectorRegionHelperError("Zone geometry has no node_name.")
    if zones.get("verified") is not True:
        raise VectorRegionHelperError("Zone geometry is not verified.")
    prefix = f"FM_Region_{_safe_source_name(source)}_"
    specs: list[dict[str, Any]] = []
    role_names = (("wall_band", "Wall"), ("walkway_band", "Walkway"), ("interior", "Interior"))
    for role, label in role_names:
        parts = list(((zones.get(role) or {}).get("parts")) or [])
        for index, part in enumerate(parts, start=1):
            points = list(part.get("points_world_xy") or [])
            if len(points) < 3:
                raise VectorRegionHelperError(f"{role} part {index} has fewer than three points.")
            specs.append({
                "name": f"{prefix}{label}_{index:03d}",
                "role": role,
                "points_world_xy": points,
            })
    if not specs:
        raise VectorRegionHelperError("Zone geometry produced no helper spline specs.")
    return specs


def sync_vector_region_helpers(zones: Mapping[str, Any], *, preflight: bool = True) -> dict[str, Any]:
    """Idempotently materialize FM-owned helper splines for vector planting regions."""
    source = str(zones.get("node_name") or "").strip()
    specs = _helper_specs(zones)
    layer = ensure_stage8_helper_layer(preflight=preflight)
    before = list_stage8_vector_region_helpers(source, preflight=False)
    actions = []
    for spec in specs:
        actions.append(upsert_stage8_vector_region_helper(
            spec["name"], source, spec["role"], spec["points_world_xy"], preflight=False
        ))
    expected = {spec["name"] for spec in specs}
    stale = [name for name in before if name not in expected]
    deleted = [delete_stage8_vector_region_helper(name, preflight=False) for name in stale]
    after = list_stage8_vector_region_helpers(source, preflight=False)
    verified = set(after) == expected and all(item.get("verified") is True for item in actions + deleted)
    if not verified:
        raise VectorRegionHelperError(
            f"Vector helper synchronization verification failed: expected={sorted(expected)!r}, after={after!r}"
        )
    return {
        "verified": True,
        "source_node_name": source,
        "before_helpers": before,
        "after_helpers": after,
        "expected_helpers": sorted(expected),
        "upsert_actions": actions,
        "deleted_stale_helpers": deleted,
        "helper_layer": layer,
        "distribution_map_used": False,
        "forest_pack_mutated": False,
    }
