from pathlib import Path
from PIL import Image

from forest_manager.placement.species_mask_generator import generate_species_masks


def test_generator_is_deterministic(tmp_path):
    first = generate_species_masks(tmp_path / "a", width=96, height=96, seed=58173)
    second = generate_species_masks(tmp_path / "b", width=96, height=96, seed=58173)

    for a, b in zip(first["layers"], second["layers"]):
        assert Path(a["primary_mask"]).read_bytes() == Path(b["primary_mask"]).read_bytes()
        assert Path(a["soft_mask"]).read_bytes() == Path(b["soft_mask"]).read_bytes()


def test_primary_ownership_is_exclusive_and_complete(tmp_path):
    report = generate_species_masks(tmp_path, width=80, height=80)
    images = [Image.open(layer["primary_mask"]) for layer in report["layers"]]
    pixel_sets = [list(img.getdata()) for img in images]

    for idx in range(80 * 80):
        assert sum(1 for pixels in pixel_sets if pixels[idx] == 255) == 1


def test_target_coverage_is_exact_within_rounding(tmp_path):
    report = generate_species_masks(tmp_path, width=100, height=100)
    targets = [42.8571, 28.5714, 28.5715]
    achieved = [layer["achieved_primary_coverage_percent"] for layer in report["layers"]]
    for target, actual in zip(targets, achieved):
        assert abs(target - actual) <= 0.02


def test_soft_masks_are_grayscale_and_same_size(tmp_path):
    report = generate_species_masks(tmp_path, width=64, height=48)
    for layer in report["layers"]:
        img = Image.open(layer["soft_mask"])
        assert img.mode == "L"
        assert img.size == (64, 48)


def test_generator_writes_three_primary_and_three_soft_masks(tmp_path):
    report = generate_species_masks(tmp_path, width=64, height=64)
    assert len(report["layers"]) == 3
    for layer in report["layers"]:
        assert Path(layer["primary_mask"]).is_file()
        assert Path(layer["soft_mask"]).is_file()


def test_report_marks_verified(tmp_path):
    report = generate_species_masks(tmp_path, width=72, height=72)
    assert report["verified"] is True
    assert report["exclusive_primary_ownership"] is True
