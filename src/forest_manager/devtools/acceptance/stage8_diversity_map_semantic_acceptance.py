from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageChops

from forest_manager.forest_control.plant_group_execution import (
    _ensure_minimum_species_footprints,
    _exclusive_normalized_rgb,
    _normalized_species_shares,
    _shape_species_mask,
    _species_color_palette,
    _threshold_mask,
)


def _read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    encodings: list[str]
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        encodings = ["utf-16", "utf-8-sig", "utf-8"]
    elif raw.startswith(b"\xef\xbb\xbf"):
        encodings = ["utf-8-sig", "utf-8", "utf-16"]
    else:
        encodings = ["utf-8-sig", "utf-8", "utf-16-le", "utf-16"]

    decoder = json.JSONDecoder()
    errors: list[str] = []
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
        except Exception as exc:
            errors.append(f"{encoding}: decode failed: {exc}")
            continue

        start = text.find("{")
        if start < 0:
            errors.append(f"{encoding}: JSON object start was not found")
            continue
        try:
            value, _end = decoder.raw_decode(text[start:])
        except Exception as exc:
            errors.append(f"{encoding}: JSON decode failed: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{encoding}: runtime report root is not a JSON object")
            continue
        return value

    detail = "; ".join(errors[-4:])
    raise RuntimeError(f"Could not parse runtime report {path}: {detail}")


def _latest_runtime_report(project_root: Path) -> Path:
    candidates = list((project_root / "artifacts" / "stage8" / "logs").glob("stage8_scene_execution_*.txt"))
    candidates.extend(project_root.glob("stage8_scene_execution_*.txt"))
    matches = sorted(
        {path.resolve() for path in candidates if path.is_file()},
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    if not matches:
        raise RuntimeError(
            "No stage8_scene_execution_*.txt runtime report was found. "
            "Run Stage 8 final runtime acceptance or pass --runtime-report explicitly."
        )

    rejected: list[str] = []
    for path in matches:
        try:
            report = _read_json(path)
        except Exception as exc:
            rejected.append(f"{path.name}: unreadable ({exc})")
            continue
        if report.get("ok") is True and str(report.get("stage") or "").startswith("8-"):
            return path
        rejected.append(
            f"{path.name}: ok={report.get('ok')!r} stage={report.get('stage')!r}"
        )

    detail = "; ".join(rejected[:8])
    raise RuntimeError(
        "No successful Stage 8 runtime report (ok=true) was found. "
        "Run Stage 8 final runtime acceptance again. Checked: " + detail
    )


def _execution_from_report(report: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("second_execution", "first_execution"):
        value = report.get(key)
        if isinstance(value, Mapping) and value.get("verified") is True:
            return value
    raise RuntimeError("Runtime report does not contain a verified Stage 8 scene execution.")


def _normalize_paths(values: list[str]) -> list[str]:
    return [str(Path(value).expanduser().resolve()).casefold() for value in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the saved single-Forest diversity map pixel-for-pixel against the exact "
            "zone masks and manifest used by a successful Stage 8 runtime report."
        )
    )
    parser.add_argument("--runtime-report", default="")
    parser.add_argument("--map-path", default="")
    parser.add_argument("--details-path", default="")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[4]
    report_path = (
        Path(args.runtime_report).expanduser().resolve()
        if str(args.runtime_report).strip()
        else _latest_runtime_report(project_root)
    )
    if not report_path.is_file():
        raise RuntimeError(f"Runtime report not found: {report_path}")

    report = _read_json(report_path)
    if report.get("ok") is not True:
        raise RuntimeError("Semantic map acceptance requires a successful Stage 8 runtime report (ok=true).")

    scene = _execution_from_report(report)
    manifest = scene.get("manifest")
    execution = scene.get("execution")
    if not isinstance(manifest, Mapping) or not isinstance(execution, Mapping):
        raise RuntimeError("Runtime report is missing manifest/execution evidence.")

    groups = [item for item in (manifest.get("groups") or []) if isinstance(item, Mapping)]
    if not groups:
        raise RuntimeError("Runtime manifest contains no executed Plant Groups.")

    manifest_mask_paths = [str(item.get("zone_mask_path") or "").strip() for item in groups]
    if any(not value for value in manifest_mask_paths):
        raise RuntimeError("Every executed Plant Group must carry its exact zone_mask_path.")
    source_paths = [Path(value).expanduser().resolve() for value in manifest_mask_paths]
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise RuntimeError("Runtime zone mask file(s) were not found: " + ", ".join(missing))

    map_binding = execution.get("map_binding")
    if not isinstance(map_binding, Mapping) or map_binding.get("verified") is not True:
        raise RuntimeError("Runtime report does not contain a verified diversity-map binding.")

    map_path = (
        Path(args.map_path).expanduser().resolve()
        if str(args.map_path).strip()
        else Path(str(map_binding.get("map_path") or "")).expanduser().resolve()
    )
    if not map_path.is_file():
        raise RuntimeError(f"Diversity map not found: {map_path}")

    runtime_source_paths = [str(value) for value in (execution.get("map_source_paths") or []) if str(value).strip()]
    exact_source_lineage = _normalize_paths(runtime_source_paths) == _normalize_paths(manifest_mask_paths)

    palette = _species_color_palette(len(groups))
    runtime_colors = []
    for value in map_binding.get("color_ids") or []:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 3:
                runtime_colors.append(tuple(int(float(part)) for part in parts[:3]))
        elif isinstance(value, (list, tuple)) and len(value) >= 3:
            runtime_colors.append(tuple(int(float(part)) for part in value[:3]))
    color_binding_matches_palette = runtime_colors == list(palette)

    with Image.open(map_path) as opened:
        actual = opened.convert("RGB")

    sources: list[Image.Image] = []
    shaped: list[Image.Image] = []
    expected: Image.Image | None = None
    resized: Image.Image | None = None
    try:
        for index, (path, group) in enumerate(zip(source_paths, groups)):
            with Image.open(path) as opened:
                source = _threshold_mask(opened.convert("L"), 128)
            sources.append(source)
            artist_values = group.get("artist_values")
            if not isinstance(artist_values, Mapping):
                artist_values = {}
            if artist_values.get("species_enabled") is False:
                shaped.append(Image.new("L", source.size, 0))
            else:
                shaped.append(_shape_species_mask(source, artist_values, species_index=index))

        source_size = sources[0].size
        if any(image.size != source_size for image in sources[1:] + shaped):
            raise RuntimeError("Runtime zone masks do not share identical source dimensions.")

        shares = _normalized_species_shares(sources, groups)
        expected = _exclusive_normalized_rgb(sources, shaped, shares)
        if expected.size != actual.size:
            resized = expected.resize(actual.size, resample=Image.Resampling.NEAREST)
            expected.close()
            expected = resized
            resized = None

        expected = _ensure_minimum_species_footprints(
            expected,
            sources,
            groups,
            target_width_system=float(map_binding.get("map_units_x") or 0.0),
            target_height_system=float(map_binding.get("map_units_y") or 0.0),
        )

        difference = ImageChops.difference(actual, expected)
        difference_bbox = difference.getbbox()
        diff_data = list(difference.get_flattened_data()) if hasattr(difference, "get_flattened_data") else list(difference.getdata())
        differing_pixels = sum(1 for pixel in diff_data if any(int(value) != 0 for value in pixel))
        difference.close()

        actual_pixels = list(actual.get_flattened_data()) if hasattr(actual, "get_flattened_data") else list(actual.getdata())
        palette_set = set(palette)
        unexpected_colors = sorted(
            {
                tuple(int(value) for value in pixel[:3])
                for pixel in actual_pixels
                if tuple(int(value) for value in pixel[:3]) != (0, 0, 0)
                and tuple(int(value) for value in pixel[:3]) not in palette_set
            }
        )
        color_counts = {
            color: sum(1 for pixel in actual_pixels if tuple(int(value) for value in pixel[:3]) == color)
            for color in palette
        }
        each_species_has_pixels = all(value > 0 for value in color_counts.values())
        pixel_exact_match = difference_bbox is None and differing_pixels == 0

        checks = {
            "runtime_report_ok": report.get("ok") is True,
            "scene_execution_verified": scene.get("verified") is True,
            "map_binding_verified": map_binding.get("verified") is True,
            "map_source_kind_is_manifest_zone_masks": execution.get("map_source_kind") == "manifest_zone_masks",
            "exact_manifest_to_runtime_mask_lineage": exact_source_lineage,
            "unique_runtime_mask_paths": len(set(_normalize_paths(runtime_source_paths))) == len(runtime_source_paths),
            "runtime_color_ids_match_production_palette": color_binding_matches_palette,
            "no_unexpected_nonblack_colors": not unexpected_colors,
            "each_species_has_map_pixels": each_species_has_pixels,
            "pixel_exact_reconstruction_match": pixel_exact_match,
        }
        ok = all(checks.values())

        result = {
            "ok": ok,
            "stage": "8-diversity-map-semantic-acceptance",
            "runtime_report": str(report_path),
            "reference_image": str(report.get("reference_image") or ""),
            "map_path": str(map_path),
            "map_size": list(actual.size),
            "group_count": len(groups),
            "group_ids": [str(item.get("group_id") or "") for item in groups],
            "zone_mask_paths": [str(path) for path in source_paths],
            "palette": [list(color) for color in palette],
            "runtime_color_ids": [list(color) for color in runtime_colors],
            "species_color_pixel_counts": [
                {"species_id": index + 1, "color_id": list(color), "pixels": color_counts[color]}
                for index, color in enumerate(palette)
            ],
            "unexpected_nonblack_colors": [list(color) for color in unexpected_colors],
            "differing_pixels": differing_pixels,
            "difference_bbox": list(difference_bbox) if difference_bbox is not None else None,
            "checks": checks,
        }
        details_path = (
            Path(args.details_path).expanduser().resolve()
            if str(args.details_path).strip()
            else project_root / "artifacts" / "stage8" / "reports" / "stage8_diversity_map_semantic_acceptance.json"
        )
        details_path.parent.mkdir(parents=True, exist_ok=True)
        details_path.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")

        print("Stage 8 Diversity Map Acceptance")
        print(f"OK: {str(ok).lower()}")
        print(f"Groups: {len(groups)}")
        print(f"Pixel exact match: {str(pixel_exact_match).lower()}")
        print(f"Differing pixels: {differing_pixels}")
        print(f"Unexpected colors: {len(unexpected_colors)}")
        print(f"Details: {details_path}")
        return 0 if ok else 1
    finally:
        actual.close()
        if expected is not None:
            expected.close()
        if resized is not None:
            resized.close()
        for image in sources + shaped:
            try:
                image.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
