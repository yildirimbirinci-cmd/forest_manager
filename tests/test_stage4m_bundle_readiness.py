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

local_backend = _load(
    "forest_manager.reference_analysis.local_backend",
    SRC / "reference_analysis" / "local_backend.py",
)
hardware = _load(
    "forest_manager.reference_analysis.local_hardware_profiler",
    SRC / "reference_analysis" / "local_hardware_profiler.py",
)
verifier = _load(
    "forest_manager.reference_analysis.local_model_verifier",
    SRC / "reference_analysis" / "local_model_verifier.py",
)
qwen = _load(
    "forest_manager.reference_analysis.qwen25_vl_local_backend",
    SRC / "reference_analysis" / "qwen25_vl_local_backend.py",
)
bundle = _load(
    "forest_manager.reference_analysis.local_bundle_verifier",
    SRC / "reference_analysis" / "local_bundle_verifier.py",
)


def test_hardware_profiler_returns_local_profile():
    result = hardware.LocalVisionHardwareProfiler().inspect()
    assert result.logical_cpu_count is None or result.logical_cpu_count > 0
    assert isinstance(result.torch_available, bool)
    assert isinstance(result.cuda_available, bool)


def test_qwen_backend_uses_auto_device_map():
    source = (SRC / "reference_analysis" / "qwen25_vl_local_backend.py").read_text(
        encoding="utf-8"
    )
    assert 'device_map="auto"' in source
    assert 'local_files_only=True' in source
    assert 'trust_remote_code=False' in source


def test_bundle_verifier_reports_missing_model_as_blocker(tmp_path, monkeypatch):
    class FakeBackend:
        class Config:
            model_dir = tmp_path / "missing-model"
        config = Config()

    monkeypatch.setattr(bundle, "Qwen25VLLocalBackend", lambda: FakeBackend())

    result = bundle.LocalVisionBundleVerifier().inspect()

    assert result.runtime_ready is False
    assert "model_weights_missing" in result.blockers
