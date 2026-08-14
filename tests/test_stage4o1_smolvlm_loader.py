from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (
    ROOT
    / "src"
    / "forest_manager"
    / "reference_analysis"
    / "smolvlm500m_local_backend.py"
)


def test_official_vision2seq_path_is_primary():
    source = BACKEND.read_text(encoding="utf-8")
    a = source.index("AutoModelForVision2Seq")
    b = source.index("Idefics3ForConditionalGeneration")
    assert a < b


def test_direct_idefics3_fallback_exists():
    source = BACKEND.read_text(encoding="utf-8")
    assert "Idefics3ForConditionalGeneration.from_pretrained" in source


def test_model_load_errors_are_not_hidden():
    source = BACKEND.read_text(encoding="utf-8")
    assert "load_errors" in source
    assert "type(exc).__name__" in source
    assert "Could not load bundled SmolVLM locally. " in source


def test_runtime_still_offline_only():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
