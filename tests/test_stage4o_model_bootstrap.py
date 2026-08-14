from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_is_pinned():
    source = (ROOT / "tools" / "bootstrap_smolvlm_model.py").read_text(
        encoding="ascii"
    )
    assert 'REVISION = "e2d212496dbdaa5d0e540b14645c2a0a77eece6e"' in source


def test_bootstrap_excludes_onnx():
    source = (ROOT / "tools" / "bootstrap_smolvlm_model.py").read_text(
        encoding="ascii"
    )
    assert '"onnx/*"' in source
    assert '"*.onnx"' in source


def test_bootstrap_verifies_model_hash():
    source = (ROOT / "tools" / "bootstrap_smolvlm_model.py").read_text(
        encoding="ascii"
    )
    assert 'MODEL_SHA256 = "d05b567eeaf534e83d375551f068ed57b5f52d37c657197f644af5ef9db091a2"' in source
    assert "sha256_file(model_file)" in source


def test_runtime_backend_remains_offline():
    source = (
        ROOT
        / "src"
        / "forest_manager"
        / "reference_analysis"
        / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")

    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
    assert 'trust_remote_code=False' in source


def test_backend_supports_current_multimodal_auto_class():
    source = (
        ROOT
        / "src"
        / "forest_manager"
        / "reference_analysis"
        / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")
    assert "AutoModelForMultimodalLM" in source
