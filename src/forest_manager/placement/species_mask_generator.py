from __future__ import annotations

from dataclasses import dataclass
from math import cos, exp, pi, sin
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFilter


@dataclass(frozen=True)
class SpeciesMaskSpec:
    key: str
    coverage_percent: float
    filename: str


DEFAULT_SPECS = (
    SpeciesMaskSpec("foreground_mass", 42.8571, "FM_Mask_01_foreground_mass.png"),
    SpeciesMaskSpec("mid_accent", 28.5714, "FM_Mask_02_mid_accent.png"),
    SpeciesMaskSpec("structural_shrub", 28.5715, "FM_Mask_03_structural_shrub.png"),
)


def _noise_field(x: float, y: float, seed: int) -> float:
    # Deterministic low-frequency field; no external RNG state.
    a = sin((x * 2.17 + y * 0.73 + seed * 0.013) * 2.0 * pi)
    b = cos((x * 0.61 - y * 1.83 + seed * 0.021) * 2.0 * pi)
    c = sin((x * 1.11 + y * 1.37 + seed * 0.008) * 2.0 * pi)
    return a * 0.52 + b * 0.31 + c * 0.17


def _gaussian(x: float, y: float, cx: float, cy: float, radius: float) -> float:
    dx = x - cx
    dy = y - cy
    return exp(-((dx * dx + dy * dy) / max(radius * radius, 1e-9)))


def _score_fields(width: int, height: int, seed: int) -> list[list[tuple[float, float, float]]]:
    rows: list[list[tuple[float, float, float]]] = []
    for py in range(height):
        y = (py + 0.5) / height
        row: list[tuple[float, float, float]] = []
        for px in range(width):
            x = (px + 0.5) / width

            # Foreground mass: broad connected sweeps.
            f = (
                1.35 * _gaussian(x, y, 0.28, 0.34, 0.42)
                + 1.05 * _gaussian(x, y, 0.72, 0.70, 0.46)
                + 0.20 * _noise_field(x, y, seed + 11)
            )

            # Mid accent: several smaller, separated islands.
            m = (
                1.25 * _gaussian(x, y, 0.72, 0.24, 0.20)
                + 1.05 * _gaussian(x, y, 0.36, 0.68, 0.18)
                + 0.95 * _gaussian(x, y, 0.82, 0.76, 0.16)
                + 0.28 * _noise_field(x, y, seed + 29)
            )

            # Structural shrub: medium / large structural regions.
            s = (
                1.22 * _gaussian(x, y, 0.22, 0.75, 0.29)
                + 1.12 * _gaussian(x, y, 0.78, 0.48, 0.31)
                + 0.24 * _noise_field(x, y, seed + 47)
            )
            row.append((f, m, s))
        rows.append(row)
    return rows


def _target_counts(total: int, specs: Iterable[SpeciesMaskSpec]) -> list[int]:
    specs = list(specs)
    raw = [total * (spec.coverage_percent / 100.0) for spec in specs]
    counts = [int(v) for v in raw]
    remainder = total - sum(counts)
    fractions = sorted(
        ((raw[i] - counts[i], i) for i in range(len(specs))),
        reverse=True,
    )
    for _, index in fractions[:remainder]:
        counts[index] += 1
    return counts


def _assign_exact_coverage(
    fields: list[list[tuple[float, float, float]]],
    specs: tuple[SpeciesMaskSpec, ...],
) -> tuple[list[int], list[int]]:
    height = len(fields)
    width = len(fields[0])
    total = width * height
    targets = _target_counts(total, specs)

    # Greedy quota-aware assignment using each species' relative score.
    ranked: list[tuple[float, int, int]] = []
    for y in range(height):
        for x in range(width):
            vals = fields[y][x]
            order = sorted(range(3), key=lambda i: vals[i], reverse=True)
            margin = vals[order[0]] - vals[order[1]]
            ranked.append((margin, y, x))
    ranked.sort(reverse=True)

    remaining = targets[:]
    owners = [-1] * total
    counts = [0, 0, 0]

    for _, y, x in ranked:
        vals = fields[y][x]
        candidates = sorted(range(3), key=lambda i: vals[i], reverse=True)
        chosen = next((i for i in candidates if remaining[i] > 0), None)
        if chosen is None:
            raise RuntimeError("No remaining mask quota during assignment.")
        idx = y * width + x
        owners[idx] = chosen
        remaining[chosen] -= 1
        counts[chosen] += 1

    if any(v != 0 for v in remaining):
        raise RuntimeError("Mask quota assignment did not finish exactly.")
    return owners, counts


def generate_species_masks(
    output_dir: Path,
    *,
    width: int = 512,
    height: int = 512,
    seed: int = 58173,
    blur_radius: float = 6.0,
    specs: tuple[SpeciesMaskSpec, ...] = DEFAULT_SPECS,
) -> dict:
    if width <= 0 or height <= 0:
        raise ValueError("Mask dimensions must be positive.")
    if len(specs) != 3:
        raise ValueError("Exactly three species mask specs are required.")
    if abs(sum(s.coverage_percent for s in specs) - 100.0) > 0.01:
        raise ValueError("Species mask coverage must total 100%.")

    output_dir.mkdir(parents=True, exist_ok=True)

    fields = _score_fields(width, height, seed)
    owners, counts = _assign_exact_coverage(fields, specs)
    total = width * height

    layers = []
    binary_images = []
    for species_index, spec in enumerate(specs):
        pixels = [255 if owner == species_index else 0 for owner in owners]
        primary = Image.new("L", (width, height))
        primary.putdata(pixels)
        binary_images.append(primary)

        soft = primary.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        primary_path = output_dir / spec.filename.replace(".png", "_primary.png")
        soft_path = output_dir / spec.filename
        primary.save(primary_path, format="PNG", optimize=True)
        soft.save(soft_path, format="PNG", optimize=True)

        achieved = counts[species_index] * 100.0 / total
        layers.append(
            {
                "key": spec.key,
                "target_coverage_percent": spec.coverage_percent,
                "achieved_primary_coverage_percent": round(achieved, 4),
                "primary_pixel_count": counts[species_index],
                "primary_mask": str(primary_path),
                "soft_mask": str(soft_path),
            }
        )

    # Validate one-and-only-one primary owner per pixel.
    ownership_sum_ok = True
    for pixel_index in range(total):
        active = 0
        for image in binary_images:
            if image.getdata()[pixel_index] == 255:
                active += 1
        if active != 1:
            ownership_sum_ok = False
            break

    return {
        "policy": "deterministic_species_masks_v1",
        "width": width,
        "height": height,
        "seed": seed,
        "blur_radius_pixels": blur_radius,
        "coverage_total_percent": round(sum(
            layer["achieved_primary_coverage_percent"] for layer in layers
        ), 4),
        "exclusive_primary_ownership": ownership_sum_ok,
        "layers": layers,
        "verified": ownership_sum_ok,
    }


def _clustered_score_fields(
    width: int,
    height: int,
    seed: int,
) -> list[list[tuple[float, float, float]]]:
    """Deterministic three-species landscape clusters for the 75 m tiled map."""
    rows: list[list[tuple[float, float, float]]] = []
    for py in range(height):
        y = (py + 0.5) / height
        row: list[tuple[float, float, float]] = []
        for px in range(width):
            x = (px + 0.5) / width

            # Lavandula: two broad connected foreground masses with a soft bridge.
            foreground = (
                1.70 * _gaussian(x, y, 0.24, 0.34, 0.31)
                + 1.55 * _gaussian(x, y, 0.68, 0.67, 0.34)
                + 0.72 * _gaussian(x, y, 0.47, 0.50, 0.30)
                + 0.08 * _noise_field(x, y, seed + 101)
            )

            # Butomus: smaller separated accents, avoiding a uniform carpet.
            accent = (
                1.75 * _gaussian(x, y, 0.71, 0.20, 0.115)
                + 1.60 * _gaussian(x, y, 0.34, 0.67, 0.105)
                + 1.50 * _gaussian(x, y, 0.83, 0.79, 0.095)
                + 1.32 * _gaussian(x, y, 0.18, 0.82, 0.090)
                + 0.10 * _noise_field(x, y, seed + 211)
            )

            # Berberis: fewer, larger structural islands around the composition.
            structural = (
                1.70 * _gaussian(x, y, 0.17, 0.73, 0.19)
                + 1.62 * _gaussian(x, y, 0.79, 0.47, 0.21)
                + 1.25 * _gaussian(x, y, 0.53, 0.16, 0.17)
                + 0.07 * _noise_field(x, y, seed + 307)
            )

            row.append((foreground, accent, structural))
        rows.append(row)
    return rows


def generate_clustered_species_masks(
    output_dir: Path,
    *,
    width: int = 512,
    height: int = 512,
    seed: int = 58173,
    blur_radius: float = 4.0,
    specs: tuple[SpeciesMaskSpec, ...] = DEFAULT_SPECS,
) -> dict:
    """Generate exact-ratio masks with stronger, species-specific cluster character."""
    if width <= 0 or height <= 0:
        raise ValueError("Mask dimensions must be positive.")
    if len(specs) != 3:
        raise ValueError("Exactly three species mask specs are required.")
    if abs(sum(s.coverage_percent for s in specs) - 100.0) > 0.01:
        raise ValueError("Species mask coverage must total 100%.")

    output_dir.mkdir(parents=True, exist_ok=True)

    fields = _clustered_score_fields(width, height, seed)
    owners, counts = _assign_exact_coverage(fields, specs)
    total = width * height

    layers = []
    binary_images = []
    for species_index, spec in enumerate(specs):
        pixels = [255 if owner == species_index else 0 for owner in owners]
        primary = Image.new("L", (width, height))
        primary.putdata(pixels)
        binary_images.append(primary)

        soft = primary.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        primary_path = output_dir / spec.filename.replace(".png", "_primary.png")
        soft_path = output_dir / spec.filename
        primary.save(primary_path, format="PNG", optimize=True)
        soft.save(soft_path, format="PNG", optimize=True)

        achieved = counts[species_index] * 100.0 / total
        layers.append(
            {
                "key": spec.key,
                "target_coverage_percent": spec.coverage_percent,
                "achieved_primary_coverage_percent": round(achieved, 4),
                "primary_pixel_count": counts[species_index],
                "primary_mask": str(primary_path),
                "soft_mask": str(soft_path),
            }
        )

    ownership_sum_ok = True
    for pixel_index in range(total):
        active = 0
        for image in binary_images:
            if image.getdata()[pixel_index] == 255:
                active += 1
        if active != 1:
            ownership_sum_ok = False
            break

    return {
        "policy": "deterministic_species_cluster_masks_v2",
        "profile": {
            "foreground_mass": "broad_connected_masses",
            "mid_accent": "small_separated_islands",
            "structural_shrub": "large_structural_islands",
        },
        "width": width,
        "height": height,
        "seed": seed,
        "blur_radius_pixels": blur_radius,
        "coverage_total_percent": round(
            sum(layer["achieved_primary_coverage_percent"] for layer in layers),
            4,
        ),
        "exclusive_primary_ownership": ownership_sum_ok,
        "layers": layers,
        "verified": ownership_sum_ok,
    }
