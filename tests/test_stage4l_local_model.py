from __future__ import annotations

import importlib.util
import json
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

local_backend = _load(
    "forest_manager.reference_analysis.local_backend",
    SRC / "reference_analysis" / "local_backend.py",
)
verifier_module = _load(
    "forest_manager.reference_analysis.local_model_verifier",
    SRC / "reference_analysis" / "local_model_verifier.py",
)
qwen_module = _load(
    "forest_manager.reference_analysis.qwen25_vl_local_backend",
    SRC / "reference_analysis" / "qwen25_vl_local_backend.py",
)

LocalModelVerifier = verifier_module.LocalModelVerifier
Qwen25VLLocalBackend = qwen_module.Qwen25VLLocalBackend


def test_qwen_backend_uses_fixed_local_model_directory():
    backend = Qwen25VLLocalBackend()
    assert backend.config.model_dir.as_posix().endswith(
        "models/vision/qwen2.5-vl-3b-instruct"
    )


def test_qwen_backend_json_extraction():
    result = Qwen25VLLocalBackend._extract_json(
        '```json\n{"style":"naturalistic","confidence":0.8}\n```'
    )
    assert result["style"] == "naturalistic"
    assert result["confidence"] == 0.8


def test_local_model_verifier_requires_real_weights(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "forest_manager_model.json").write_text("{}", encoding="utf-8")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    result = LocalModelVerifier(model_dir).inspect()

    assert result.weights_exist is False
    assert result.ready is False


def test_local_model_verifier_accepts_weight_index_contract(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "forest_manager_model.json").write_text("{}", encoding="utf-8")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {}}),
        encoding="utf-8",
    )

    verifier = LocalModelVerifier(model_dir)
    monkeypatch.setattr(verifier, "_module_exists", lambda name: True)

    result = verifier.inspect()

    assert result.weights_exist is True
    assert result.ready is True
