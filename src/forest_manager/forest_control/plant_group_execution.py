from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageChops, ImageFilter

from forest_manager.max_bridge.runtime_bridge import (
    bind_single_forest_diversity_map,
    get_single_forest_area_bounds,
    refresh_single_forest_diversity_map,
    finalize_plant_group_areas,
    upsert_plant_group_area,
)

from .area_records import AreaBoundaryRecordAdapter
from .geometry import GeometrySourcesAdapter
from .service import ForestControlError, ForestPackControlService


@dataclass(frozen=True)
class PlantGroupAreaPlan:
    group_id: str
    group_key: str
    base_area_index: int
    species_ids: tuple[int, ...]
    spacing_system: float
    scale_percent: float


def _group_key(group: Mapping[str, Any], position: int) -> str:
    raw = str(group.get("group_id") or f"plant_group:{position}")
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in raw)
    return safe[:96] or f"plant_group_{position}"


def _source_species_map(forest_name: str, service: ForestPackControlService) -> dict[str, int]:
    adapter = GeometrySourcesAdapter(service)
    inventory = service.inventory(forest_name, preflight=False)
    cobj = next(
        (item for item in inventory.get("properties") or [] if isinstance(item, dict) and item.get("name") == "cobjlist"),
        None,
    )
    metadata = cobj.get("array_metadata") if isinstance(cobj, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    result: dict[str, int] = {}
    for index in range(1, count + 1):
        record = adapter.read_record(forest_name, index)
        if record.source_node:
            result[record.source_node] = int(record.species_id or index)
        if record.name:
            result.setdefault(record.name, int(record.species_id or index))
    return result


def build_plant_group_area_plan(
    manifest: Mapping[str, Any],
    *,
    service: ForestPackControlService | None = None,
) -> tuple[str, float, tuple[PlantGroupAreaPlan, ...]]:
    svc = service or ForestPackControlService()
    forest_name = str(manifest.get("primary_forest") or "FM_Forest_001")
    groups = manifest.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ForestControlError("Plant-group manifest does not contain executable groups.")

    source_to_species = _source_species_map(forest_name, svc)
    area_records = AreaBoundaryRecordAdapter(svc).list_records(forest_name)
    area_by_node = {
        record.node_name: record.index
        for record in area_records
        if record.node_name and not str(record.name).startswith("FM_GROUP_")
    }

    spacings: list[float] = []
    raw: list[tuple[int, Mapping[str, Any], float]] = []
    for position, item in enumerate(groups, start=1):
        if not isinstance(item, Mapping):
            continue
        spacing_pair = item.get("spacing_system")
        if not isinstance(spacing_pair, (list, tuple)) or len(spacing_pair) != 2:
            raise ForestControlError(f"Plant group has no spacing_system pair: {item.get('group_id')}")
        try:
            spacing = float(spacing_pair[0])
        except (TypeError, ValueError) as exc:
            raise ForestControlError(f"Plant group has invalid spacing: {item.get('group_id')}") from exc
        if spacing <= 0.0:
            raise ForestControlError(f"Plant group spacing must be greater than zero: {item.get('group_id')}")
        spacings.append(spacing)
        raw.append((position, item, spacing))

    if not spacings:
        raise ForestControlError("Plant-group manifest has no valid spacing values.")
    base_spacing = min(spacings)

    plans: list[PlantGroupAreaPlan] = []
    for position, item, spacing in raw:
        area_nodes = [str(value) for value in (item.get("area_nodes") or []) if str(value).strip()]
        if not area_nodes:
            raise ForestControlError(f"Plant group has no Area assignment: {item.get('group_id')}")
        base_index = next((area_by_node[name] for name in area_nodes if name in area_by_node), None)
        if base_index is None:
            raise ForestControlError(f"Plant group Area was not found in Forest Pack: {area_nodes[0]}")
        source_names = [str(value) for value in (item.get("source_names") or []) if str(value).strip()]
        species_ids = tuple(source_to_species[name] for name in source_names if name in source_to_species)
        if not species_ids:
            raise ForestControlError(f"Plant group species could not be resolved in Geometry List: {item.get('group_id')}")
        plans.append(
            PlantGroupAreaPlan(
                group_id=str(item.get("group_id") or f"plant_group:{position}"),
                group_key=_group_key(item, position),
                base_area_index=int(base_index),
                species_ids=species_ids,
                spacing_system=spacing,
                scale_percent=(spacing / base_spacing) * 100.0,
            )
        )
    return forest_name, base_spacing, tuple(plans)


_SPECIES_MASK_FILENAMES = (
    "FM_Mask_01_foreground_mass.png",
    "FM_Mask_02_mid_accent.png",
    "FM_Mask_03_structural_shrub.png",
)

# The Stage 5D species masks were authored and accepted at a 75 m
# Distribution Image extent. This is a map calibration value, not Plant
# Spacing. Preserve its physical pixel pitch when the active spline is resized.
_AUTHORED_MASK_REFERENCE_METERS = 75.0



def _normalized_choice(value: Any, default: str) -> str:
    token = str(value or default).strip()
    return token if token else default


def _threshold_mask(image: Image.Image, threshold: int) -> Image.Image:
    return image.point(lambda value: 255 if int(value) >= threshold else 0, mode="L")


def _coarse_noise_mask(size: tuple[int, int], *, seed: int, cell: int, keep_ratio: float) -> Image.Image:
    """Create a cheap deterministic low-frequency binary noise field using Pillow only."""
    import random

    width, height = size
    cell = max(4, int(cell))
    small_w = max(2, (width + cell - 1) // cell)
    small_h = max(2, (height + cell - 1) // cell)
    rng = random.Random(int(seed))
    raw = bytes(255 if rng.random() < float(keep_ratio) else 0 for _ in range(small_w * small_h))
    small = Image.frombytes("L", (small_w, small_h), raw)
    try:
        return small.resize(size, Image.Resampling.BILINEAR).point(lambda v: 255 if v >= 128 else 0, mode="L")
    finally:
        small.close()


def _shape_species_mask(
    image: Image.Image,
    artist_values: Mapping[str, Any],
    *,
    species_index: int = 0,
) -> Image.Image:
    """Shape spatial character without changing a species' global planting share.

    Naturalness and Cluster Character are intentionally spatial controls only.
    Relative species quantity is resolved later by the normalized composition
    pass, so these controls cannot accidentally erase or dominate siblings.
    """
    naturalness = _normalized_choice(artist_values.get("naturalness"), "Balanced")
    cluster = _normalized_choice(artist_values.get("cluster_character"), "Medium Clusters")
    base = _threshold_mask(image, 128)

    if naturalness == "Ordered":
        shaped = base.filter(ImageFilter.MinFilter(size=9)).filter(ImageFilter.MedianFilter(size=5))
    elif naturalness == "Natural":
        expanded = base.filter(ImageFilter.MaxFilter(size=5))
        noise = _coarse_noise_mask(base.size, seed=731 + species_index * 97, cell=34, keep_ratio=0.88)
        shaped = ImageChops.multiply(expanded, noise)
        expanded.close(); noise.close()
    elif naturalness == "Wild":
        expanded = base.filter(ImageFilter.MaxFilter(size=9))
        noise = _coarse_noise_mask(base.size, seed=1297 + species_index * 131, cell=26, keep_ratio=0.78)
        shaped = ImageChops.multiply(expanded, noise)
        expanded.close(); noise.close()
    else:
        shaped = base.copy()
    base.close()

    cluster_sizes = {
        "Solitary": 1,
        "Small Groups": 3,
        "Medium Clusters": 5,
        "Large Masses": 9,
    }
    radius = int(cluster_sizes.get(cluster, 5))
    if radius > 1:
        expanded = shaped.filter(ImageFilter.MaxFilter(size=radius))
        shaped.close()
        shaped = expanded
    return _threshold_mask(shaped, 128)


def _white_count(image: Image.Image) -> int:
    hist = image.histogram()
    return int(hist[255] if len(hist) > 255 else 0)


def _normalized_species_shares(
    source_masks: list[Image.Image],
    groups: list[Mapping[str, Any]],
) -> list[float]:
    """Return bounded, normalized species shares for the active groups.

    The authored RGB support defines species coverage. Plant Spacing must never
    alter this composition map: spacing is applied later through Forest Pack's
    per-Geometry collision radius. Naturalness and Cluster Character are the
    only controls allowed to reshape the spatial mask.
    """
    active: list[bool] = []
    weighted: list[float] = []
    for index, group in enumerate(groups[:3]):
        artist_values = group.get("artist_values") if isinstance(group.get("artist_values"), Mapping) else {}
        enabled = artist_values.get("species_enabled") is not False
        active.append(enabled)
        weighted.append(float(max(1, _white_count(source_masks[index]))) if enabled else 0.0)

    total = sum(weighted)
    if total <= 0.0:
        return [0.0, 0.0, 0.0]
    shares = [value / total for value in weighted]

    active_indices = [i for i, flag in enumerate(active) if flag]
    if len(active_indices) > 1:
        floor = 0.12
        ceiling = 0.64
        for _ in range(6):
            changed = False
            for i in active_indices:
                bounded = max(floor, min(ceiling, shares[i]))
                if abs(bounded - shares[i]) > 1e-9:
                    shares[i] = bounded
                    changed = True
            subtotal = sum(shares[i] for i in active_indices)
            if subtotal > 0:
                for i in active_indices:
                    shares[i] /= subtotal
            if not changed:
                break
    return shares


def _exclusive_normalized_rgb(
    source_masks: list[Image.Image],
    shaped_masks: list[Image.Image],
    shares: list[float],
) -> Image.Image:
    """Compose pure R/G/B IDs with deterministic, mutually-exclusive pixels.

    NumPy is used opportunistically when already present, but is not a runtime
    dependency; the Pillow/byte fallback preserves identical semantics.
    """
    size = source_masks[0].size
    try:
        import numpy as np  # type: ignore

        source = np.stack([np.asarray(mask, dtype=np.uint8) >= 128 for mask in source_masks], axis=0)
        shaped = np.stack([np.asarray(mask, dtype=np.uint8) >= 128 for mask in shaped_masks], axis=0)
        share = np.asarray(shares, dtype=np.float64)[:, None, None]
        preferred_weights = shaped * share
        preferred_total = preferred_weights.sum(axis=0)
        authored_weights = source * share
        weights = np.where(preferred_total[None, :, :] > 0.0, preferred_weights, authored_weights)
        totals = weights.sum(axis=0)
        flat_index = np.arange(size[0] * size[1], dtype=np.uint64).reshape((size[1], size[0]))
        hashed = ((flat_index * np.uint64(1103515245) + np.uint64(12345)) & np.uint64(0x7FFFFFFF)).astype(np.float64)
        pick = (hashed / 2147483648.0) * totals
        cumulative = np.cumsum(weights, axis=0)
        chosen = np.full(totals.shape, -1, dtype=np.int8)
        previous = np.zeros(totals.shape, dtype=np.float64)
        for i in range(3):
            hit = (chosen < 0) & (totals > 0.0) & (pick >= previous) & (pick < cumulative[i])
            chosen[hit] = i
            previous = cumulative[i]
        # Numerical edge case at the upper boundary.
        chosen[(chosen < 0) & (totals > 0.0)] = 2
        planes = [Image.fromarray(np.where(chosen == i, 255, 0).astype(np.uint8), mode="L") for i in range(3)]
        try:
            return Image.merge("RGB", (planes[0], planes[1], planes[2]))
        finally:
            for plane in planes:
                plane.close()
    except ImportError:
        source_bytes = [mask.tobytes() for mask in source_masks]
        shaped_bytes = [mask.tobytes() for mask in shaped_masks]
        pixel_count = size[0] * size[1]
        outs = (bytearray(pixel_count), bytearray(pixel_count), bytearray(pixel_count))
        for pos in range(pixel_count):
            authored = [i for i in range(3) if source_bytes[i][pos] >= 128 and shares[i] > 0.0]
            if not authored:
                continue
            preferred = [i for i in authored if shaped_bytes[i][pos] >= 128]
            eligible = preferred or authored
            weight_total = sum(shares[i] for i in eligible)
            h = (pos * 1103515245 + 12345) & 0x7FFFFFFF
            pick = (h / 2147483648.0) * weight_total
            running = 0.0
            chosen = eligible[-1]
            for i in eligible:
                running += shares[i]
                if pick <= running:
                    chosen = i
                    break
            outs[chosen][pos] = 255
        planes = [Image.frombytes("L", size, bytes(buf)) for buf in outs]
        try:
            return Image.merge("RGB", (planes[0], planes[1], planes[2]))
        finally:
            for plane in planes:
                plane.close()


_SPECIES_COLOR_PALETTE = ((255, 0, 0), (0, 255, 0), (0, 0, 255))


def _paletteize_exclusive_rgb(image: Image.Image) -> Image.Image:
    src = image.convert("RGB")
    try:
        data = []
        for r, g, b in src.getdata():
            if r >= g and r >= b and r > 0:
                data.append(_SPECIES_COLOR_PALETTE[0])
            elif g >= r and g >= b and g > 0:
                data.append(_SPECIES_COLOR_PALETTE[1])
            elif b > 0:
                data.append(_SPECIES_COLOR_PALETTE[2])
            else:
                data.append((0, 0, 0))
        out = Image.new("RGB", src.size)
        out.putdata(data)
        return out
    finally:
        src.close()


def _resolve_diversity_mask_paths(
    manifest: Mapping[str, Any],
) -> tuple[list[Path], str]:
    """Resolve the three source masks for the single-Forest RGB map.

    Stage 8 reference-image plans carry an explicit ``zone_mask_path`` per
    Plant Group.  Those masks are authoritative and must be used directly.
    Older Stage 7 manifests do not carry those paths, so they retain the
    verified generated-mask fallback.
    """
    raw_groups = manifest.get("groups") if isinstance(manifest, Mapping) else None
    groups = [item for item in (raw_groups or []) if isinstance(item, Mapping)]
    if len(groups) < 3:
        raise ForestControlError("Single-Forest diversity map requires three Plant Group records.")

    authored_paths: list[Path] = []
    authored_present = False
    for group in groups[:3]:
        raw_path = str(group.get("zone_mask_path") or "").strip()
        if raw_path:
            authored_present = True
            authored_paths.append(Path(raw_path).expanduser().resolve())
        else:
            authored_paths.append(Path())

    if authored_present:
        if any(not str(group.get("zone_mask_path") or "").strip() for group in groups[:3]):
            raise ForestControlError(
                "Stage 8 visual-intent manifest must provide zone_mask_path for all three Plant Groups."
            )
        missing = [str(path) for path in authored_paths if not path.is_file()]
        if missing:
            raise ForestControlError(
                "Stage 8 reference-image zone masks were not found: " + ", ".join(missing)
            )
        return authored_paths, "manifest_zone_masks"

    project_root = Path(__file__).resolve().parents[3]
    mask_dir = project_root / "resources" / "generated_masks" / "stage5d18"
    fallback_paths = [mask_dir / name for name in _SPECIES_MASK_FILENAMES]
    missing = [str(path) for path in fallback_paths if not path.is_file()]
    if missing:
        raise ForestControlError(
            "Single-Forest diversity map requires the three generated species masks: " + ", ".join(missing)
        )
    return fallback_paths, "stage7_generated_masks"


def _build_single_forest_diversity_map(
    manifest: Mapping[str, Any],
    *,
    target_width_system: float | None = None,
    target_height_system: float | None = None,
    reference_tile_system: float | None = None,
) -> Path:
    project_root = Path(__file__).resolve().parents[3]
    mask_dir = project_root / "resources" / "generated_masks" / "stage5d18"
    mask_paths, _mask_source = _resolve_diversity_mask_paths(manifest)

    raw_groups = manifest.get("groups") if isinstance(manifest, Mapping) else None
    groups = [item for item in (raw_groups or []) if isinstance(item, Mapping)]

    sources: list[Image.Image] = []
    shaped: list[Image.Image] = []
    try:
        for index, path in enumerate(mask_paths):
            source = Image.open(path).convert("L")
            source = _threshold_mask(source, 128)
            sources.append(source)
            artist_values = groups[index].get("artist_values")
            if not isinstance(artist_values, Mapping):
                artist_values = {}
            if artist_values.get("species_enabled") is False:
                shaped.append(Image.new("L", source.size, 0))
            else:
                shaped.append(_shape_species_mask(source, artist_values, species_index=index))

        size = sources[0].size
        if any(image.size != size for image in sources[1:] + shaped):
            raise ForestControlError("Species distribution masks do not have matching dimensions.")
        shares = _normalized_species_shares(sources, groups)
        rgb = _exclusive_normalized_rgb(sources, shaped, shares)
        paletted = None
        resized = None
        try:
            paletted = _paletteize_exclusive_rgb(rgb)
            final_image = paletted
            if (
                target_width_system is not None
                and target_height_system is not None
                and reference_tile_system is not None
                and target_width_system > 0.0
                and target_height_system > 0.0
                and reference_tile_system > 0.0
            ):
                src_w, src_h = paletted.size
                dst_w = max(16, min(2048, int(round(src_w * float(target_width_system) / float(reference_tile_system)))))
                dst_h = max(16, min(2048, int(round(src_h * float(target_height_system) / float(reference_tile_system)))))
                if (dst_w, dst_h) != paletted.size:
                    resized = paletted.resize((dst_w, dst_h), resample=Image.Resampling.NEAREST)
                    final_image = resized
            output_path = mask_dir / "FM_SingleForest_Diversity_Map.png"
            final_image.save(output_path, format="PNG", optimize=False)
            return output_path
        finally:
            if resized is not None:
                resized.close()
            if paletted is not None:
                paletted.close()
            rgb.close()
    finally:
        for image in sources + shaped:
            try:
                image.close()
            except Exception:
                pass


def _authored_mask_reference_system(service: ForestPackControlService) -> float:
    units = service.scene_units(preflight=False)
    one_meter = float(units.one_meter_system_units or 0.0)
    if one_meter <= 0.0:
        raise ForestControlError("Could not resolve active scene meter conversion for distribution-map calibration.")
    return _AUTHORED_MASK_REFERENCE_METERS * one_meter


def refresh_plant_group_diversity_map(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Interactive UI path: rebuild only the RGB diversity map and rebind it once."""
    forest_name = str(manifest.get("primary_forest") or "FM_Forest_001")
    bounds = get_single_forest_area_bounds(forest_name)
    # Keep the original 75 m mask calibration. current_units_x/y are live
    # Forest Pack map projection values and must never be reinterpreted as
    # Plant Spacing. Using them here creates a feedback loop after every Apply.
    reference_tile = _authored_mask_reference_system(ForestPackControlService())
    diversity_map_path = _build_single_forest_diversity_map(
        manifest,
        target_width_system=float(bounds.get("width_system") or 0.0),
        target_height_system=float(bounds.get("height_system") or 0.0),
        reference_tile_system=reference_tile,
    )
    map_binding = refresh_single_forest_diversity_map(forest_name, diversity_map_path)
    return {
        "forest_name": forest_name,
        "map_path": str(diversity_map_path),
        "map_binding": map_binding,
        "verified": bool(map_binding.get("verified")),
    }



def _group_reset_spacing(group: Mapping[str, Any], fallback: float) -> float:
    defaults = group.get("reset_defaults")
    pair = defaults.get("spacing_system") if isinstance(defaults, Mapping) else None
    try:
        value = float(pair[0]) if isinstance(pair, (list, tuple)) and pair else float(fallback)
    except (TypeError, ValueError):
        value = float(fallback)
    return max(1e-6, value)


def _apply_species_spacing_collision(
    manifest: Mapping[str, Any],
    forest_name: str,
    plans: tuple[PlantGroupAreaPlan, ...],
    service: ForestPackControlService,
) -> list[dict[str, Any]]:
    """Apply group spacing without touching the RGB diversity map.

    Forest Pack has one X/Y grid per Forest, but each Geometry List item has an
    independent Collision Radius (`radiuslist`). We keep the authored grid fixed
    at its reset baseline and express each Plant Group's spacing as a bounded
    multiplier of that species' local collision radius. This preserves map/color
    IDs and lets sibling species influence each other through Forest collisions.
    """
    groups = manifest.get("groups")
    if not isinstance(groups, list):
        raise ForestControlError("Plant-group manifest is missing groups for spacing apply.")
    by_id = {str(item.get("group_id") or ""): item for item in groups if isinstance(item, Mapping)}

    inventory = service.inventory(forest_name, preflight=False)
    spec_prop = next(
        (item for item in inventory.get("properties") or [] if isinstance(item, dict) and item.get("name") == "specidlist"),
        None,
    )
    metadata = spec_prop.get("array_metadata") if isinstance(spec_prop, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    species_to_index: dict[int, int] = {}
    for index in range(count):
        try:
            species_id = int(service.get_array_element(forest_name, "specidlist", index, preflight=False).get("value") or 0)
        except Exception:
            species_id = 0
        if species_id > 0:
            species_to_index[species_id] = index

    results: list[dict[str, Any]] = []
    for plan in plans:
        group = by_id.get(plan.group_id)
        baseline = _group_reset_spacing(group or {}, plan.spacing_system)
        ratio = max(0.25, min(8.0, float(plan.spacing_system) / baseline))
        radius_percent = max(25.0, min(800.0, 100.0 * ratio))
        radius_percent_int = int(round(radius_percent))
        for species_id in plan.species_ids:
            index = species_to_index.get(int(species_id))
            if index is None:
                raise ForestControlError(f"Plant Group species ID is missing from Geometry List: {species_id}")
            response = service.set_array_element(
                forest_name, "radiuslist", index, radius_percent_int, preflight=False
            )
            readback = service.get_array_element(
                forest_name, "radiuslist", index, preflight=False
            )
            actual = int(readback.get("value") or 0)
            if actual != radius_percent_int:
                raise ForestControlError(
                    f"Plant-group Collision Radius verification failed: species={species_id} "
                    f"expected={radius_percent_int} actual={actual}"
                )
            results.append({
                "group_id": plan.group_id,
                "species_id": int(species_id),
                "geometry_index": int(index),
                "spacing_system": float(plan.spacing_system),
                "baseline_spacing_system": float(baseline),
                "radius_percent": int(actual),
                "verified": response.get("verified") is True,
            })
    return results


def refresh_plant_group_distribution_fast(
    manifest: Mapping[str, Any],
    *,
    service: ForestPackControlService | None = None,
) -> dict[str, Any]:
    """Interactive spacing Apply that leaves the RGB diversity map unchanged.

    Forest-wide X/Y Units stay at the scene's authored reset baseline. Per-group
    spacing is applied through Geometry List Collision Radius only.
    """
    svc = service or ForestPackControlService()
    forest_name, _current_base, plans = build_plant_group_area_plan(manifest, service=svc)
    groups = manifest.get("groups")
    raw_groups = [item for item in groups if isinstance(item, Mapping)] if isinstance(groups, list) else []
    baseline_by_id = {str(item.get("group_id") or ""): _group_reset_spacing(item, 1.0) for item in raw_groups}
    baseline_grid = min((baseline_by_id.get(plan.group_id, plan.spacing_system) for plan in plans), default=1.0)

    # IMPORTANT: Forest Pack X/Y Units are the physical scale of the
    # Distribution Image, not Plant Spacing. Never overwrite map projection
    # while applying a per-species spacing edit.
    collision_results = _apply_species_spacing_collision(manifest, forest_name, plans, svc)

    # Spacing must not rebuild or alter the RGB map. A lightweight Forest refresh
    # is enough after radiuslist changes and avoids the map reset/flicker seen in
    # the previous implementations.
    try:
        svc.set_property(forest_name, "collpreview", True, preflight=False)
    except Exception:
        pass
    return {
        "forest_name": forest_name,
        "base_spacing_system": float(baseline_grid),
        "group_spacings_system": [float(plan.spacing_system) for plan in plans],
        "spacing_mode": "per_species_collision_radius",
        "collision_results": collision_results,
        "map_rebuilt": False,
        "verified": bool(collision_results) and all(item.get("verified") for item in collision_results),
    }

def execute_plant_group_manifest(
    manifest: Mapping[str, Any],
    *,
    service: ForestPackControlService | None = None,
    strict_acceptance: bool = True,
) -> dict[str, Any]:
    svc = service or ForestPackControlService()
    forest_name, base_spacing, plans = build_plant_group_area_plan(manifest, service=svc)

    groups = manifest.get("groups")
    raw_groups = [item for item in groups if isinstance(item, Mapping)] if isinstance(groups, list) else []
    baseline_by_id = {str(item.get("group_id") or ""): _group_reset_spacing(item, 1.0) for item in raw_groups}
    baseline_grid = min((baseline_by_id.get(plan.group_id, plan.spacing_system) for plan in plans), default=base_spacing)
    # X/Y Units belong to distribution-map projection and are set by the
    # map binder from the active Area bounds. Plant Spacing must not drive them.
    try:
        svc.set_property(forest_name, "Disabled", False, preflight=False)
    except ForestControlError:
        svc.set_property(forest_name, "disabled", False, preflight=False)

    area_results: list[dict[str, Any]] = []
    for plan in plans:
        area_results.append(
            upsert_plant_group_area(
                forest_name,
                plan.group_key,
                plan.base_area_index,
                ",".join(str(value) for value in plan.species_ids),
                plan.scale_percent,
            )
        )
    finalize = finalize_plant_group_areas(
        forest_name,
        sorted({plan.base_area_index for plan in plans}),
        [plan.group_key for plan in plans],
    )
    # Restore the final Geometry collision/spacing state before map acceptance.
    # Running a strict generated-item scan before this step can falsely reject a
    # valid reset when a previous edit left one species with a large radius.
    collision_results = _apply_species_spacing_collision(manifest, forest_name, plans, svc)
    bounds = get_single_forest_area_bounds(forest_name)
    reference_tile = _authored_mask_reference_system(svc)
    diversity_map_path = _build_single_forest_diversity_map(
        manifest,
        target_width_system=float(bounds.get("width_system") or 0.0),
        target_height_system=float(bounds.get("height_system") or 0.0),
        reference_tile_system=reference_tile,
    )
    map_binding = bind_single_forest_diversity_map(
        forest_name,
        diversity_map_path,
        strict_verify=bool(strict_acceptance),
    )
    map_source_paths, map_source_kind = _resolve_diversity_mask_paths(manifest)
    return {
        "forest_name": forest_name,
        "base_spacing_system": baseline_grid,
        "groups": [
            {
                "group_id": plan.group_id,
                "base_area_index": plan.base_area_index,
                "species_ids": list(plan.species_ids),
                "spacing_system": plan.spacing_system,
                "scale_percent": plan.scale_percent,
            }
            for plan in plans
        ],
        "area_results": area_results,
        "finalize": finalize,
        "map_binding": map_binding,
        "map_source_kind": map_source_kind,
        "map_source_paths": [str(path) for path in map_source_paths],
        "spacing_mode": "per_species_collision_radius",
        "collision_results": collision_results,
        "verified": bool(finalize.get("verified")) and bool(map_binding.get("verified")) and all(item.get("verified") for item in collision_results),
    }
