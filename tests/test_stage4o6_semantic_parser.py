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

parser = _load(
    "forest_manager.reference_analysis.local_semantic_parser",
    SRC / "reference_analysis" / "local_semantic_parser.py",
)


def test_json_output_still_supported():
    result = parser.parse_local_semantic_output(
        '{"style":"woodland","density":"medium","diversity":"medium",'
        '"canopy_bias":"mixed","composition_notes":[],'
        '"plant_candidates":[{"query":"tree","weight":1}],'
        '"confidence":0.8}'
    )
    assert result["style"] == "woodland"


def test_line_format_is_supported():
    result = parser.parse_local_semantic_output(
        """STYLE: naturalistic woodland
DENSITY: medium
DIVERSITY: high
CANOPY_BIAS: mixed
NOTES: layered; irregular
PLANTS: deciduous tree|40; alder|35; field maple|25
CONFIDENCE: 0.77
"""
    )
    assert len(result["plant_candidates"]) == 3
    assert result["plant_candidates"][0]["weight"] == 40.0
    assert result["confidence"] == 0.77


def test_unparseable_output_includes_raw_preview():
    try:
        parser.parse_local_semantic_output("This is just a garden.")
    except parser.LocalSemanticParseError as exc:
        assert "Raw output:" in str(exc)
        assert "This is just a garden." in str(exc)
    else:
        raise AssertionError("Expected LocalSemanticParseError")


def test_backend_uses_robust_parser():
    source = (
        SRC
        / "reference_analysis"
        / "smolvlm500m_local_backend.py"
    ).read_text(encoding="utf-8")
    assert "parse_local_semantic_output(text)" in source
