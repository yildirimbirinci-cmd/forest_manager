from pathlib import Path

from PIL import Image

from forest_manager.placement.species_mask_generator import generate_species_masks


def test_masks_are_clipped_to_spline_polygon(tmp_path: Path) -> None:
    rings = [[(0.05, 0.20), (0.85, 0.05), (0.95, 0.55), (0.75, 0.90), (0.15, 0.80)]]
    report = generate_species_masks(
        tmp_path,
        width=128,
        height=128,
        blur_radius=2.0,
        normalized_rings=rings,
    )

    assert report["verified"] is True
    assert report["spline_polygon_applied"] is True
    assert report["area_pixel_count"] < 128 * 128
    assert abs(float(report["coverage_total_percent"]) - 100.0) < 0.05

    for layer in report["layers"]:
        image = Image.open(layer["soft_mask"]).convert("L")
        assert image.getpixel((0, 0)) == 0
        assert image.getpixel((127, 127)) == 0
