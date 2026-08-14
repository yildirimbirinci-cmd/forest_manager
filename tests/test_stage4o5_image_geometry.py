from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (
    ROOT
    / "src"
    / "forest_manager"
    / "reference_analysis"
    / "smolvlm500m_local_backend.py"
)


def test_image_processor_uses_smolvlm_512_geometry():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'size={"longest_edge": 2048}' in source
    assert 'max_image_size={"longest_edge": 512}' in source
    assert "do_image_splitting=True" in source


def test_generation_has_geometry_guard():
    source = BACKEND.read_text(encoding="utf-8")
    assert "pixel_height % 512 != 0" in source
    assert "pixel_width % 512 != 0" in source


def test_runtime_remains_offline():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source


def test_model_weights_are_not_modified():
    source = BACKEND.read_text(encoding="utf-8")
    assert "model.safetensors" not in source
