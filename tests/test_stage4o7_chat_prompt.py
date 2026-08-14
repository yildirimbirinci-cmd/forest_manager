from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (
    ROOT
    / "src"
    / "forest_manager"
    / "reference_analysis"
    / "smolvlm500m_local_backend.py"
)
PROVIDER = (
    ROOT
    / "src"
    / "forest_manager"
    / "reference_analysis"
    / "local_semantic_provider.py"
)


def test_prompt_starts_with_official_im_start_token():
    source = BACKEND.read_text(encoding="utf-8")
    assert '"<|im_start|>User:<image>"' in source


def test_prompt_keeps_generation_boundary():
    source = BACKEND.read_text(encoding="utf-8")
    assert '"<end_of_utterance>\\nAssistant:"' in source


def test_generation_is_deterministic_and_bounded():
    source = BACKEND.read_text(encoding="utf-8")
    assert "max_new_tokens=min(self.config.max_new_tokens, 192)" in source
    assert "do_sample=False" in source
    assert "repetition_penalty=1.03" in source


def test_semantic_prompt_is_shorter_and_structured():
    source = PROVIDER.read_text(encoding="utf-8")
    assert "Do not repeat this request." in source
    assert "Reply only with these seven lines" in source
    assert "Do not invent cultivars." in source


def test_runtime_is_still_offline():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
