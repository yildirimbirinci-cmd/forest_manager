from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (
    ROOT
    / "src"
    / "forest_manager"
    / "reference_analysis"
    / "smolvlm500m_local_backend.py"
)


def test_auto_processor_is_removed():
    source = BACKEND.read_text(encoding="utf-8")
    assert "AutoProcessor.from_pretrained" not in source


def test_direct_idefics3_processor_is_used():
    source = BACKEND.read_text(encoding="utf-8")
    assert "Idefics3ImageProcessor.from_pretrained" in source
    assert "AutoTokenizer.from_pretrained" in source
    assert "Idefics3Processor(" in source


def test_processor_failure_is_explicit():
    source = BACKEND.read_text(encoding="utf-8")
    assert "Could not initialize local Idefics3 processor." in source


def test_runtime_stays_offline():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
