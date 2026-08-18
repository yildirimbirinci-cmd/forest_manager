from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"


def test_stage8_reference_image_manifest_spacing_is_authoritative():
    source = CONTROLLER.read_text(encoding="utf-8")

    assert "def _manifest_preserves_authored_spacing(" in source
    assert 'generated_by.startswith("stage8-reference-image-")' in source
    assert "preserve_authored_spacing = self._manifest_preserves_authored_spacing(manifest)" in source
    assert "if not preserve_authored_spacing:" in source


def test_legacy_live_spacing_sync_remains_available():
    source = CONTROLLER.read_text(encoding="utf-8")

    assert '"radiuslist"' in source
    assert 'target["spacing_system"] = [float(live_spacing), float(live_spacing)]' in source
