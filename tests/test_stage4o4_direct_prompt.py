from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (
    ROOT
    / "src"
    / "forest_manager"
    / "reference_analysis"
    / "smolvlm500m_local_backend.py"
)


def test_apply_chat_template_is_not_used():
    source = BACKEND.read_text(encoding="utf-8")
    assert "processor.apply_chat_template(" not in source


def test_official_single_turn_template_format_is_used():
    source = BACKEND.read_text(encoding="utf-8")
    assert '"User:<image>"' in source
    assert '"<end_of_utterance>\\nAssistant:"' in source


def test_processor_receives_text_and_image_directly():
    source = BACKEND.read_text(encoding="utf-8")
    assert "text=[rendered]" in source
    assert "images=[image]" in source


def test_offline_policy_remains_enabled():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
