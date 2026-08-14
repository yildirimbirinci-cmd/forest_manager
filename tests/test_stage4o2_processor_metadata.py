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

compat = _load(
    "forest_manager.reference_analysis.smolvlm_processor_compat",
    SRC / "reference_analysis" / "smolvlm_processor_compat.py",
)


def test_metadata_fix_adds_required_processor_fields(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    (model_dir / "preprocessor_config.json").write_text(
        json.dumps({
            "do_resize": True,
            "size": {"longest_edge": 1536},
        }),
        encoding="utf-8",
    )
    (model_dir / "processor_config.json").write_text(
        json.dumps({"image_seq_len": 64}),
        encoding="utf-8",
    )

    result = compat.ensure_smolvlm_processor_metadata(model_dir)

    assert result["verified"] is True
    assert result["preprocessor_changed"] is True
    assert result["processor_changed"] is True

    pre = json.loads(
        (model_dir / "preprocessor_config.json").read_text(encoding="utf-8")
    )
    proc = json.loads(
        (model_dir / "processor_config.json").read_text(encoding="utf-8")
    )

    assert pre["image_processor_type"] == "Idefics3ImageProcessor"
    assert pre["processor_class"] == "Idefics3Processor"
    assert proc["processor_class"] == "Idefics3Processor"


def test_metadata_fix_is_idempotent(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    (model_dir / "preprocessor_config.json").write_text(
        json.dumps({
            "image_processor_type": "Idefics3ImageProcessor",
            "processor_class": "Idefics3Processor",
        }),
        encoding="utf-8",
    )
    (model_dir / "processor_config.json").write_text(
        json.dumps({"processor_class": "Idefics3Processor"}),
        encoding="utf-8",
    )

    result = compat.ensure_smolvlm_processor_metadata(model_dir)

    assert result["verified"] is True
    assert result["preprocessor_changed"] is False
    assert result["processor_changed"] is False


def test_backend_runs_metadata_fix_before_auto_processor():
    source = (
        SRC
        / "reference_analysis"
        / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")

    assert source.index("ensure_smolvlm_processor_metadata(") < source.index(
        "AutoProcessor.from_pretrained("
    )


def test_runtime_remains_offline():
    source = (
        SRC
        / "reference_analysis"
        / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")

    assert 'HF_HUB_OFFLINE' in source
    assert 'TRANSFORMERS_OFFLINE' in source
    assert 'local_files_only=True' in source
