from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "forest_manager"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


forest_pkg = types.ModuleType("forest_manager")
forest_pkg.__path__ = [str(SRC)]
sys.modules.setdefault("forest_manager", forest_pkg)

ref_pkg = types.ModuleType("forest_manager.reference_analysis")
ref_pkg.__path__ = [str(SRC / "reference_analysis")]
sys.modules.setdefault("forest_manager.reference_analysis", ref_pkg)

_load(
    "forest_manager.reference_analysis.local_backend",
    SRC / "reference_analysis" / "local_backend.py",
)
_load(
    "forest_manager.reference_analysis.local_model_verifier",
    SRC / "reference_analysis" / "local_model_verifier.py",
)
smol = _load(
    "forest_manager.reference_analysis.smolvlm500m_local_backend",
    SRC / "reference_analysis" / "smolvlm500m_local_backend.py",
)

SmolVLM500MLocalBackend = smol.SmolVLM500MLocalBackend


def test_smolvlm_is_active_cpu_friendly_model():
    backend = SmolVLM500MLocalBackend()
    assert backend.config.model_dir.as_posix().endswith(
        "models/vision/smolvlm-500m-instruct"
    )
    assert backend.config.max_new_tokens == 512


def test_smolvlm_backend_is_offline_only():
    source = (
        SRC / "reference_analysis" / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")
    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
    assert 'trust_remote_code=False' in source


def test_smolvlm_uses_cpu_float32_fallback():
    source = (
        SRC / "reference_analysis" / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")
    assert 'device = "cuda" if torch.cuda.is_available() else "cpu"' in source
    assert "dtype = torch.float32" in source


def test_smolvlm_extracts_json():
    result = SmolVLM500MLocalBackend._extract_json(
        '```json\n{"style":"woodland","confidence":0.7}\n```'
    )
    assert result["style"] == "woodland"
    assert result["confidence"] == 0.7
