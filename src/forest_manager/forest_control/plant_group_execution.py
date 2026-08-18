from __future__ import annotations

from dataclasses import dataclass
import base64
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageChops, ImageFilter, ImageDraw

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
    mask_count = len(source_masks)
    if mask_count <= 0:
        return []
    if len(groups) < mask_count:
        raise ForestControlError(
            f"Plant-group manifest has fewer groups than diversity masks: groups={len(groups)} masks={mask_count}"
        )

    active: list[bool] = []
    weighted: list[float] = []
    for index, group in enumerate(groups[:mask_count]):
        artist_values = group.get("artist_values") if isinstance(group.get("artist_values"), Mapping) else {}
        enabled = artist_values.get("species_enabled") is not False
        active.append(enabled)
        weighted.append(float(max(1, _white_count(source_masks[index]))) if enabled else 0.0)

    total = sum(weighted)
    if total <= 0.0:
        return [0.0] * mask_count
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


def _species_color_palette(count: int) -> tuple[tuple[int, int, int], ...]:
    """Return deterministic, non-black Forest Pack Color IDs for N groups.

    Preserve the historically accepted first three IDs as pure R/G/B so
    existing three-species scenes remain byte-compatible. Additional IDs are
    sampled from HSV space with fixed saturation/value and deterministic hue.
    """
    import colorsys

    if count <= 0:
        return ()
    base = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    if count <= 3:
        return tuple(base[:count])
    colors = list(base)
    # Golden-ratio hue stepping avoids near-adjacent colors as the group count
    # grows while remaining stable across runs and machines.
    golden = 0.6180339887498949
    hue = 0.11
    while len(colors) < count:
        hue = (hue + golden) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.78, 1.0)
        candidate = (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
        if candidate != (0, 0, 0) and candidate not in colors:
            colors.append(candidate)
    return tuple(colors)





def _get_single_forest_site_polygon(
    forest_name: str,
    sample_count: int = 256,
    *,
    service: ForestPackControlService | None = None,
) -> dict[str, Any]:
    """Read and normalize the active Forest area polygon payload.

    Stage 8 bridge 0.9.81 returns normalized_rings plus meter bounds. Older
    callers used a flat points_normalized payload with system-unit bounds.
    Normalize both contracts here so the scene-space map builder has one
    stable internal schema.
    """
    svc = service or ForestPackControlService()
    data = svc.single_forest_area_polygon(
        forest_name,
        sample_count=sample_count,
        preflight=False,
    )

    normalized = data.get("points_normalized")
    if not isinstance(normalized, list) or len(normalized) < 3:
        rings = data.get("normalized_rings")
        if not isinstance(rings, list) or len(rings) != 1:
            raise ForestControlError(
                "Forest area polygon must contain exactly one normalized closed ring."
            )
        normalized = rings[0]

    clean_points: list[list[float]] = []
    for item in normalized:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            raise ForestControlError("Forest area polygon contains an invalid normalized point.")
        clean_points.append([float(item[0]), float(item[1])])
    if len(clean_points) < 3:
        raise ForestControlError("Forest area polygon returned fewer than three points.")

    width = float(
        data.get("width_system")
        or data.get("bounds_width_meters")
        or 0.0
    )
    height = float(
        data.get("height_system")
        or data.get("depth_system")
        or data.get("bounds_height_meters")
        or 0.0
    )
    if width <= 0.0 or height <= 0.0:
        raise ForestControlError("Forest area polygon returned invalid bounds.")

    normalized_payload = dict(data)
    normalized_payload["points_normalized"] = clean_points
    normalized_payload["width_system"] = width
    normalized_payload["height_system"] = height
    return normalized_payload


def _reference_photo_semantic_layout(
    source_masks: list[Image.Image],
    groups: list[Mapping[str, Any]],
    shares: list[float],
    *,
    size: tuple[int, int],
    site_polygon_normalized: list[tuple[float, float]],
) -> Image.Image:
    """Build the scene map from the actual Line/spline silhouette.

    Reference masks contribute only semantic foreground/background order and
    relative species shares. Their pixels are never projected into scene XY.
    """
    import math

    count = min(len(source_masks), len(groups), len(shares))
    if count <= 0:
        raise ForestControlError("Line-site semantic layout requires active species masks.")
    width, height = size
    if width <= 0 or height <= 0:
        raise ForestControlError("Line-site semantic layout size is invalid.")
    if len(site_polygon_normalized) < 3:
        raise ForestControlError("Line-site semantic layout requires the sampled planting spline.")

    def centroid_y(mask: Image.Image, fallback: float) -> float:
        bbox = mask.getbbox()
        if bbox is None:
            return fallback
        return (float(bbox[1]) + float(bbox[3])) * 0.5 / max(1.0, float(mask.size[1]))

    active = [i for i in range(count) if float(shares[i]) > 0.0]
    if not active:
        raise ForestControlError("Line-site semantic layout has no enabled species.")

    foreground_to_background = sorted(
        active,
        key=lambda i: (-centroid_y(source_masks[i], (i + 0.5) / count), i),
    )
    total = sum(float(shares[i]) for i in foreground_to_background)
    normalized = {i: float(shares[i]) / total for i in foreground_to_background}
    palette = _species_color_palette(count)

    cumulative: list[tuple[int, float, float]] = []
    cursor = 0.0
    for i in foreground_to_background:
        start = cursor
        cursor += normalized[i]
        cumulative.append((i, start, cursor))
    cumulative[-1] = (cumulative[-1][0], cumulative[-1][1], 1.0)

    polygon_pixels = [
        (
            min(width - 1, max(0, int(round(nx * (width - 1))))),
            min(height - 1, max(0, int(round((1.0 - ny) * (height - 1))))),
        )
        for nx, ny in site_polygon_normalized
    ]
    site_mask = Image.new("L", size, 0)
    ImageDraw.Draw(site_mask).polygon(polygon_pixels, fill=255)

    out = Image.new("RGB", size, (0, 0, 0))
    out_pixels = out.load()
    mask_pixels = site_mask.load()
    for y in range(height):
        depth = 1.0 - ((y + 0.5) / max(1.0, float(height)))
        wave = 0.018 * math.sin(((y + 0.5) / max(1.0, float(height))) * math.tau * 2.0)
        t = min(0.999999, max(0.0, depth + wave))
        chosen = cumulative[-1][0]
        for species_index, start, end in cumulative:
            if start <= t < end:
                chosen = species_index
                break
        color = palette[chosen]
        for x in range(width):
            if mask_pixels[x, y] != 0:
                out_pixels[x, y] = color
    site_mask.close()
    return out


def _scene_space_semantic_diversity_map(
    groups: list[Mapping[str, Any]],
    *,
    size: tuple[int, int],
    site_polygon_normalized: list[tuple[float, float]],
) -> Image.Image:
    """Build a visible single-Forest Color-ID map from scene-space semantics only.

    The selected 3ds Max spline defines the legal site polygon. Plant-group
    semantic roles define depth bands; groups sharing a band are partitioned
    laterally by their normalized coverage weights. Reference-image pixels and
    masks are never projected into scene XY.
    """
    import math

    width, height = size
    if width < 8 or height < 8:
        raise ForestControlError("Scene-space diversity map size is too small.")
    if len(site_polygon_normalized) < 3:
        raise ForestControlError("Scene-space diversity map requires the sampled planting spline.")
    if not groups:
        raise ForestControlError("Scene-space diversity map requires Plant Groups.")

    role_band = {
        "foreground_mass": "foreground",
        "groundcover": "foreground",
        "flower_accent": "midground",
        "mid_accent": "midground",
        "purple_accent": "midground",
        "structural_shrub": "background",
        "tree_canopy": "background",
    }
    band_range = {
        "foreground": (0.0, 0.32),
        "midground": (0.32, 0.68),
        "background": (0.68, 1.0),
    }

    grouped: dict[str, list[tuple[int, Mapping[str, Any], float]]] = {
        "foreground": [], "midground": [], "background": []
    }
    for index, group in enumerate(groups):
        role = str(group.get("semantic_role") or "").strip()
        band = role_band.get(role)
        if band is None:
            raise ForestControlError(
                f"No approved visible scene-space band exists for semantic role: {role or '<empty>'}"
            )
        try:
            weight = max(0.0, float(group.get("coverage_weight") or 0.0))
        except (TypeError, ValueError):
            weight = 0.0
        grouped[band].append((index, group, weight))

    palette = _species_color_palette(len(groups))
    partitions: dict[str, list[tuple[int, float, float]]] = {}
    for band, items in grouped.items():
        if not items:
            partitions[band] = []
            continue
        total = sum(item[2] for item in items)
        if total <= 0.0:
            shares = [1.0 / len(items)] * len(items)
        else:
            shares = [item[2] / total for item in items]
        cursor = 0.0
        parts=[]
        for pos, ((group_index, _group, _weight), share) in enumerate(zip(items, shares)):
            start=cursor
            cursor += share
            end=1.0 if pos == len(items)-1 else cursor
            parts.append((group_index,start,end))
        partitions[band]=parts

    polygon_pixels = [
        (
            min(width - 1, max(0, int(round(nx * (width - 1))))),
            min(height - 1, max(0, int(round((1.0 - ny) * (height - 1))))),
        )
        for nx, ny in site_polygon_normalized
    ]
    site_mask = Image.new("L", size, 0)
    ImageDraw.Draw(site_mask).polygon(polygon_pixels, fill=255)
    mask_pixels = site_mask.load()
    out = Image.new("RGB", size, (0, 0, 0))
    pixels = out.load()
    try:
        for y in range(height):
            # 0 = visual/front edge, 1 = back edge. The existing normalized
            # polygon convention places Max +depth upward in the bitmap.
            depth = 1.0 - ((y + 0.5) / float(height))
            if depth < 0.32:
                band="foreground"
                b0,b1=band_range[band]
            elif depth < 0.68:
                band="midground"
                b0,b1=band_range[band]
            else:
                band="background"
                b0,b1=band_range[band]
            parts=partitions.get(band) or []
            if not parts:
                # If AI omitted an entire semantic layer, choose the nearest
                # populated layer without inventing a new species.
                available=[name for name in ("foreground","midground","background") if partitions.get(name)]
                if not available:
                    raise ForestControlError("Scene-space diversity map has no populated semantic band.")
                center=(b0+b1)*0.5
                band=min(available,key=lambda name: abs(center-sum(band_range[name])*0.5))
                parts=partitions[band]
            local_depth=(depth-b0)/max(1e-9,b1-b0)
            wave=0.035*math.sin((local_depth*2.0 + 0.25)*math.tau)
            for x in range(width):
                if mask_pixels[x,y] == 0:
                    continue
                lateral=min(0.999999,max(0.0,(x+0.5)/float(width)+wave))
                chosen=parts[-1][0]
                for group_index,start,end in parts:
                    if start <= lateral < end:
                        chosen=group_index
                        break
                pixels[x,y]=palette[chosen]
        return out
    except Exception:
        out.close()
        raise
    finally:
        site_mask.close()


def _build_visible_scene_space_map(
    manifest: Mapping[str, Any],
    forest_name: str,
    service: ForestPackControlService,
) -> tuple[Path, dict[str, Any]]:
    raw_groups = manifest.get("groups") if isinstance(manifest, Mapping) else None
    groups = [item for item in (raw_groups or []) if isinstance(item, Mapping)]
    if not groups:
        raise ForestControlError("Visible scene-space execution requires Plant Groups.")
    polygon = _get_single_forest_site_polygon(forest_name, sample_count=256, service=service)
    normalized=list(polygon.get("points_normalized") or [])
    if len(normalized) < 3:
        raise ForestControlError("Visible scene-space execution could not read the active site polygon.")
    width_system=float(polygon.get("width_system") or 0.0)
    height_system=float(polygon.get("height_system") or polygon.get("depth_system") or 0.0)
    if width_system <= 0.0 or height_system <= 0.0:
        raise ForestControlError(f"Visible scene-space execution received invalid polygon dimensions: {polygon}")

    # Keep enough pixels for stable region boundaries while bounding memory.
    longest=max(width_system,height_system)
    scale=1024.0/longest if longest > 0 else 1.0
    width=max(256,min(1536,int(round(width_system*scale))))
    height=max(256,min(1536,int(round(height_system*scale))))
    image=_scene_space_semantic_diversity_map(groups,size=(width,height),site_polygon_normalized=normalized)
    output_dir=Path(__file__).resolve().parents[3]/"runtime"/"stage8_scene_maps"
    output_dir.mkdir(parents=True,exist_ok=True)
    output=output_dir/"FM_SingleForest_SceneSpace_Diversity.png"
    try:
        image.save(output,format="PNG",optimize=False)
    finally:
        image.close()
    return output, polygon


def _exclusive_normalized_rgb(
    source_masks: list[Image.Image],
    shaped_masks: list[Image.Image],
    shares: list[float],
) -> Image.Image:
    """Compose deterministic mutually-exclusive Color IDs for any group count."""
    count = len(source_masks)
    if count <= 0 or len(shaped_masks) != count or len(shares) != count:
        raise ForestControlError(
            "Diversity-map inputs must contain the same positive group count: "
            f"source_masks={len(source_masks)}, shaped_masks={len(shaped_masks)}, shares={len(shares)}"
        )
    size = source_masks[0].size
    palette = _species_color_palette(count)
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
        chosen = np.full(totals.shape, -1, dtype=np.int32)
        previous = np.zeros(totals.shape, dtype=np.float64)
        for i in range(count):
            hit = (chosen < 0) & (totals > 0.0) & (pick >= previous) & (pick < cumulative[i])
            chosen[hit] = i
            previous = cumulative[i]
        chosen[(chosen < 0) & (totals > 0.0)] = count - 1
        out = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        for i, color in enumerate(palette):
            mask = chosen == i
            out[mask, 0] = color[0]
            out[mask, 1] = color[1]
            out[mask, 2] = color[2]
        return Image.fromarray(out, mode="RGB")
    except ImportError:
        source_bytes = [mask.tobytes() for mask in source_masks]
        shaped_bytes = [mask.tobytes() for mask in shaped_masks]
        pixel_count = size[0] * size[1]
        out = bytearray(pixel_count * 3)
        for pos in range(pixel_count):
            authored = [i for i in range(count) if source_bytes[i][pos] >= 128 and shares[i] > 0.0]
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
            color = palette[chosen]
            offset = pos * 3
            out[offset:offset + 3] = bytes(color)
        return Image.frombytes("RGB", size, bytes(out))


def _ensure_minimum_species_footprints(
    image: Image.Image,
    source_masks: list[Image.Image],
    groups: list[Mapping[str, Any]],
    *,
    target_width_system: float | None,
    target_height_system: float | None,
) -> Image.Image:
    """Preserve a physically viable Color-ID footprint for every active species.

    Reference-image masks can become very small after the authored 75 m map is
    projected onto a compact site.  A valid species may then retain a few pixels
    but still receive no Forest Pack distribution samples.  Repair only those
    under-sized footprints, near their own authored support, and never consume
    another species below its own minimum.  This keeps the single-Forest map
    deterministic while preventing a verified execution group from disappearing
    purely because of map down-sampling.
    """
    count = min(len(source_masks), len(groups))
    if count <= 1:
        return image
    palette = _species_color_palette(count)
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    width_system = float(target_width_system or 0.0)
    height_system = float(target_height_system or 0.0)
    px_per_system_values = []
    if width_system > 0.0:
        px_per_system_values.append(width / width_system)
    if height_system > 0.0:
        px_per_system_values.append(height / height_system)
    px_per_system = sum(px_per_system_values) / len(px_per_system_values) if px_per_system_values else 0.0

    pixels = image.load()
    palette_index = {tuple(color): index for index, color in enumerate(palette)}
    current = [0] * count
    for y in range(height):
        for x in range(width):
            owner = palette_index.get(tuple(int(v) for v in pixels[x, y][:3]))
            if owner is not None:
                current[owner] += 1

    targets: list[int] = []
    supports: list[Image.Image] = []
    try:
        for index in range(count):
            group = groups[index]
            artist_values = group.get("artist_values") if isinstance(group.get("artist_values"), Mapping) else {}
            if artist_values.get("species_enabled") is False:
                targets.append(0)
            else:
                spacing_pair = group.get("spacing_system")
                try:
                    spacing = float(spacing_pair[0]) if isinstance(spacing_pair, (list, tuple)) and spacing_pair else 0.0
                except (TypeError, ValueError):
                    spacing = 0.0
                # Forest Pack samples the distribution map on its own placement grid.
                # A tiny but non-zero Color-ID island can therefore contain many
                # pixels while still falling entirely between generated samples.
                # Keep a physically meaningful footprint around the authored
                # support: a 1.5-spacing radius gives the color island enough
                # diameter to cross multiple placement cells on compact sites.
                radius_px = max(3, int(round(max(0.0, spacing) * px_per_system * 1.5))) if px_per_system > 0.0 else 3
                target_pixels = max(36, int(round(3.141592653589793 * radius_px * radius_px)))
                targets.append(min(target_pixels, max(16, (width * height) // max(2, count))))
            support = source_masks[index].resize((width, height), resample=Image.Resampling.NEAREST)
            support = _threshold_mask(support, 128)
            supports.append(support)

        repair_order = sorted(range(count), key=lambda idx: (current[idx] - targets[idx], idx))
        for index in repair_order:
            target = targets[index]
            if target <= 0 or current[index] >= target:
                continue
            support = supports[index]
            bbox = support.getbbox()
            if bbox is None:
                continue
            sx0, sy0, sx1, sy1 = bbox
            cx = (sx0 + sx1 - 1) * 0.5
            cy = (sy0 + sy1 - 1) * 0.5

            deficit = target - current[index]
            # Grow locally around the authored mask only as much as needed.
            grow_radius = max(2, int(round((target / 3.141592653589793) ** 0.5)))
            kernel = max(3, grow_radius * 2 + 1)
            if kernel % 2 == 0:
                kernel += 1
            kernel = min(kernel, 63)
            expanded = support.filter(ImageFilter.MaxFilter(size=kernel))
            try:
                ex = expanded.load()
                candidates = []
                for y in range(height):
                    for x in range(width):
                        if int(ex[x, y]) < 128:
                            continue
                        candidates.append(((x - cx) * (x - cx) + (y - cy) * (y - cy), y, x))
                candidates.sort()
                color = palette[index]
                for _distance, y, x in candidates:
                    if deficit <= 0:
                        break
                    old = tuple(int(v) for v in pixels[x, y][:3])
                    old_owner = palette_index.get(old)
                    if old_owner == index:
                        continue
                    if old_owner is not None and current[old_owner] <= targets[old_owner]:
                        continue
                    if old_owner is not None:
                        current[old_owner] -= 1
                    pixels[x, y] = color
                    current[index] += 1
                    deficit -= 1
            finally:
                expanded.close()

        missing = [index + 1 for index in range(count) if targets[index] > 0 and current[index] < targets[index]]
        if missing:
            raise ForestControlError(
                "Single-Forest diversity map could not preserve a viable Color-ID footprint for group(s): "
                + ", ".join(str(value) for value in missing)
            )
        return image
    finally:
        for support in supports:
            support.close()


def _apply_species_color_ids(
    forest_name: str,
    plans: tuple[PlantGroupAreaPlan, ...],
    service: ForestPackControlService,
) -> list[dict[str, Any]]:
    """Bind every Geometry species ID to the same deterministic palette as the map."""
    palette = _species_color_palette(len(plans))
    inventory = service.inventory(forest_name, preflight=False)
    spec_prop = next(
        (item for item in inventory.get("properties") or [] if isinstance(item, dict) and item.get("name") == "specidlist"),
        None,
    )
    metadata = spec_prop.get("array_metadata") if isinstance(spec_prop, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    species_to_index: dict[int, int] = {}
    for index in range(count):
        value = service.get_array_element(forest_name, "specidlist", index, preflight=False).get("value")
        try:
            species_id = int(value or 0)
        except (TypeError, ValueError):
            species_id = 0
        if species_id > 0:
            species_to_index[species_id] = index

    results: list[dict[str, Any]] = []
    for group_index, plan in enumerate(plans):
        color = palette[group_index]
        for species_id in plan.species_ids:
            geometry_index = species_to_index.get(int(species_id))
            if geometry_index is None:
                raise ForestControlError(f"Plant Group species ID is missing from Geometry List: {species_id}")
            target = [float(color[0]), float(color[1]), float(color[2])]
            response = service.set_array_element(
                forest_name, "coloridlist", geometry_index, target, preflight=False
            )
            readback = service.get_array_element(
                forest_name, "coloridlist", geometry_index, preflight=False
            ).get("value")
            if isinstance(readback, (list, tuple)):
                actual = [int(round(float(v))) for v in readback[:3]]
            else:
                text = str(readback or "").strip().strip("[]")
                try:
                    actual = [int(round(float(v.strip()))) for v in text.split(",")[:3]]
                except Exception:
                    actual = []
            expected = list(color)
            if actual != expected:
                raise ForestControlError(
                    f"Plant-group Color ID verification failed: species={species_id} "
                    f"expected={expected} actual={actual}"
                )
            results.append({
                "group_id": plan.group_id,
                "species_id": int(species_id),
                "geometry_index": int(geometry_index),
                "color_id": expected,
                "verified": response.get("verified") is True,
            })
    return results

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
    if not groups:
        raise ForestControlError("Single-Forest diversity map requires Plant Group records.")

    authored_tokens = [str(group.get("zone_mask_path") or "").strip() for group in groups]
    authored_present = any(authored_tokens)
    authored_paths: list[Path] = []

    if authored_present:
        if any(not token for token in authored_tokens):
            raise ForestControlError(
                "Stage 8 visual-intent manifest must provide zone_mask_path for every Plant Group."
            )
        authored_paths = [Path(token).expanduser().resolve() for token in authored_tokens]
        missing = [str(path) for path in authored_paths if not path.is_file()]
        if missing:
            raise ForestControlError(
                "Stage 8 reference-image zone masks were not found: " + ", ".join(missing)
            )
        return authored_paths, "line_site_polygon_semantic_layout"

    if len(groups) < 3:
        raise ForestControlError("Legacy single-Forest diversity map requires three Plant Group records.")

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
    site_polygon_normalized: list[tuple[float, float]] | None = None,
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
        authored_photo = _mask_source in {"manifest_zone_masks", "reference_photo_semantic_layout", "line_site_semantic_layout", "line_site_polygon_semantic_layout"}
        if (
            target_width_system is not None
            and target_height_system is not None
            and reference_tile_system is not None
            and target_width_system > 0.0
            and target_height_system > 0.0
            and reference_tile_system > 0.0
        ):
            src_w, src_h = sources[0].size
            dst_w = max(32, min(2048, int(round(src_w * float(target_width_system) / float(reference_tile_system)))))
            dst_h = max(32, min(2048, int(round(src_h * float(target_height_system) / float(reference_tile_system)))))
        else:
            dst_w, dst_h = sources[0].size

        final_image = None
        rgb = None
        resized = None
        try:
            if authored_photo:
                if not site_polygon_normalized:
                    raise ForestControlError(
                        "Stage 8 Line-site map requires the sampled 3ds Max planting spline."
                    )
                final_image = _reference_photo_semantic_layout(
                    sources,
                    groups,
                    shares,
                    size=(dst_w, dst_h),
                    site_polygon_normalized=site_polygon_normalized,
                )
            else:
                rgb = _exclusive_normalized_rgb(sources, shaped, shares)
                final_image = rgb
                if (dst_w, dst_h) != rgb.size:
                    resized = rgb.resize((dst_w, dst_h), resample=Image.Resampling.NEAREST)
                    final_image = resized
                final_image = _ensure_minimum_species_footprints(
                    final_image,
                    sources,
                    groups,
                    target_width_system=target_width_system,
                    target_height_system=target_height_system,
                )
            output_path = mask_dir / "FM_SingleForest_Diversity_Map.png"
            final_image.save(output_path, format="PNG", optimize=False)
            return output_path
        finally:
            if resized is not None:
                resized.close()
            if rgb is not None:
                rgb.close()
            if final_image is not None and final_image is not rgb and final_image is not resized:
                final_image.close()
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
    site_polygon = _get_single_forest_site_polygon(forest_name, service=service)
    # Keep the original 75 m mask calibration. current_units_x/y are live
    # Forest Pack map projection values and must never be reinterpreted as
    # Plant Spacing. Using them here creates a feedback loop after every Apply.
    reference_tile = _authored_mask_reference_system(ForestPackControlService())
    diversity_map_path = _build_single_forest_diversity_map(
        manifest,
        target_width_system=float(site_polygon.get("width_system") or bounds.get("width_system") or 0.0),
        target_height_system=float(site_polygon.get("height_system") or bounds.get("height_system") or 0.0),
        reference_tile_system=reference_tile,
        site_polygon_normalized=list(site_polygon.get("points_normalized") or []),
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

def _set_array_bool(
    forest_name: str,
    property_name: str,
    zero_index: int,
    value: bool,
    *,
    service: ForestPackControlService,
) -> dict[str, Any]:
    return service.set_array_element(
        forest_name,
        property_name,
        int(zero_index),
        bool(value),
        preflight=False,
    )


def _set_array_int(
    forest_name: str,
    property_name: str,
    zero_index: int,
    value: int,
    *,
    service: ForestPackControlService,
) -> dict[str, Any]:
    return service.set_array_element(
        forest_name,
        property_name,
        int(zero_index),
        int(value),
        preflight=False,
    )


def _set_array_float(
    forest_name: str,
    property_name: str,
    zero_index: int,
    value: float,
    *,
    service: ForestPackControlService,
) -> dict[str, Any]:
    return service.set_array_element(
        forest_name,
        property_name,
        int(zero_index),
        float(value),
        preflight=False,
    )



def _normalize_requested_spline_areas(
    forest_name: str,
    requested_zero_indices: list[int],
    *,
    service: ForestPackControlService,
) -> dict[str, Any]:
    """Force requested Stage 8 base Areas to Forest Pack spline/include semantics.

    A stale Area record can still reference the correct Line node while carrying
    a non-spline or exclude mode. In that state the UI looks correctly linked
    but Forest Pack does not clip generated items to the intended boundary.
    """
    requested = sorted({int(i) for i in requested_zero_indices})
    if not requested:
        raise ForestControlError("Stage 8 Area normalization received no requested base Area indices.")

    records: list[dict[str, Any]] = []
    for zero_index in requested:
        area_type = _set_array_int(forest_name, "artypelist", zero_index, 0, service=service)
        include_mode = _set_array_int(forest_name, "arincexclist", zero_index, 0, service=service)
        obstacle_scale = _set_array_float(forest_name, "arobscalelist", zero_index, 100.0, service=service)
        records.append({
            "zero_index": zero_index,
            "area_type": int(area_type.get("after_value")),
            "include_exclude": int(include_mode.get("after_value")),
            "obstacle_scale": float(obstacle_scale.get("after_value")),
            "verified": True,
        })
    return {
        "requested_zero_indices": requested,
        "records": records,
        "verified": all(item.get("verified") is True for item in records),
    }


def _enforce_only_requested_base_areas_active(
    forest_name: str,
    requested_zero_indices: list[int],
    service: ForestPackControlService,
) -> dict[str, Any]:
    inventory = service.inventory(forest_name, preflight=False)
    prop = next(
        (item for item in inventory.get("properties") or []
         if isinstance(item, dict) and item.get("name") == "pf_aractivelist"),
        None,
    )
    metadata = prop.get("array_metadata") if isinstance(prop, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    if count <= 0:
        raise ForestControlError("Forest Pack pf_aractivelist is unavailable for Stage 8 Area enforcement.")

    requested = {int(i) for i in requested_zero_indices}
    if not requested:
        raise ForestControlError("Stage 8 Area enforcement received no requested base Area indices.")
    if any(i < 0 or i >= count for i in requested):
        raise ForestControlError(f"Stage 8 requested Area index is out of range: requested={sorted(requested)} count={count}")

    writes: list[dict[str, Any]] = []
    for zero_index in range(count):
        writes.append(_set_array_bool(
            forest_name,
            "pf_aractivelist",
            zero_index,
            zero_index in requested,
            service=service,
        ))

    active = [int(item.get("index")) for item in writes if item.get("after_value") is True]
    if active != sorted(requested):
        raise ForestControlError(
            f"Stage 8 active Area set mismatch: expected={sorted(requested)} actual={active}"
        )
    return {
        "area_count": count,
        "requested_active_zero_indices": sorted(requested),
        "active_zero_indices": active,
        "disabled_zero_indices": [i for i in range(count) if i not in requested],
        "verified": True,
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
    requested_base_area_indices = sorted({plan.base_area_index for plan in plans})
    finalize = finalize_plant_group_areas(
        forest_name,
        requested_base_area_indices,
        [plan.group_key for plan in plans],
    )
    area_activation = _enforce_only_requested_base_areas_active(
        forest_name,
        requested_base_area_indices,
        svc,
    )
    area_normalization = _normalize_requested_spline_areas(
        forest_name,
        requested_base_area_indices,
        service=svc,
    )
    # Restore the final Geometry collision/spacing state before map acceptance.
    # Running a strict generated-item scan before this step can falsely reject a
    # valid reset when a previous edit left one species with a large radius.
    collision_results = _apply_species_spacing_collision(manifest, forest_name, plans, svc)
    color_id_results: list[dict[str, Any]] = []

    # Stage 8 visible scene-space execution. The diversity map is generated
    # from the active Line/spline polygon and semantic Plant Group roles only.
    # Reference-image pixels are never projected into scene XY.
    diversity_map_path, site_polygon = _build_visible_scene_space_map(
        manifest,
        forest_name,
        svc,
    )
    color_id_results = _apply_species_color_ids(forest_name, plans, svc)
    map_binding = bind_single_forest_diversity_map(
        forest_name,
        diversity_map_path,
        strict_verify=bool(strict_acceptance),
    )
    if map_binding.get("verified") is not True:
        raise ForestControlError(f"Scene-space diversity map binding did not verify: {map_binding}")

    distribution_threshold = {
        "applied": True,
        "mode": "scene_space_semantic_color_id",
        "reference_image_projection": False,
        "verified": True,
    }
    map_source_paths = [diversity_map_path]
    map_source_kind = "selected_3ds_max_boundary_semantic_regions"

    # The binder owns the final projection extents. Read the authoritative
    # Area bounds for acceptance reporting only; Plant Spacing never drives
    # map projection units.
    area_bounds = get_single_forest_area_bounds(forest_name)
    target_units_x = float(area_bounds.get("width_system") or 0.0)
    target_units_y = float(area_bounds.get("height_system") or area_bounds.get("depth_system") or 0.0)
    if target_units_x <= 0.0 or target_units_y <= 0.0:
        raise ForestControlError(f"Could not resolve active Forest Area bounds for scene-space distribution: {area_bounds}")
    units_x_write = {"after_value": target_units_x, "verified": True}
    units_y_write = {"after_value": target_units_y, "verified": True}

    # Do not finalize again after the Color-ID map bind.  The bridge finalize
    # contract intentionally restores Random diversity (divers=0) for the
    # pre-map consolidated-Forest state.  Re-running it here would immediately
    # undo the verified Image Mode / Match Color ID state (distmode=0,
    # densityMap=false, divers=1) established by the binder.
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
        "area_activation": area_activation,
        "area_normalization": area_normalization,
        "distribution_threshold": distribution_threshold,
        "map_binding": map_binding,
        "map_free_distribution_extents": {
            "units_x": float(units_x_write.get("after_value") or target_units_x),
            "units_y": float(units_y_write.get("after_value") or target_units_y),
            "source": "active_area_bounds_scene_space_map",
            "verified": True,
        },
        "map_source_kind": map_source_kind,
        "map_source_paths": [str(path) for path in map_source_paths],
        "site_polygon": {
            "spline_name": site_polygon.get("spline_name"),
            "sample_count": site_polygon.get("sample_count"),
            "width_system": site_polygon.get("width_system"),
            "height_system": site_polygon.get("height_system"),
            "verified": site_polygon.get("verified") is True,
        },
        "spacing_mode": "per_species_collision_radius",
        "collision_results": collision_results,
        "color_id_results": color_id_results,
        "verified": (
            bool(finalize.get("verified"))
            and bool(area_activation.get("verified"))
            and bool(area_normalization.get("verified"))
            and bool(map_binding.get("verified"))
            and bool(color_id_results)
            and all(item.get("verified") for item in color_id_results)
            and all(item.get("verified") for item in collision_results)
        ),
    }
