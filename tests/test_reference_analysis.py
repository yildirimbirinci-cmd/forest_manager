from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "forest_manager"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Build only the lightweight module structure needed by these unit tests.
forest_pkg = types.ModuleType("forest_manager")
forest_pkg.__path__ = [str(SRC)]
sys.modules.setdefault("forest_manager", forest_pkg)

ref_pkg = types.ModuleType("forest_manager.reference_analysis")
ref_pkg.__path__ = [str(SRC / "reference_analysis")]
sys.modules.setdefault("forest_manager.reference_analysis", ref_pkg)

placement_pkg = types.ModuleType("forest_manager.placement")
placement_pkg.__path__ = [str(SRC / "placement")]
sys.modules.setdefault("forest_manager.placement", placement_pkg)

models = _load_module(
    "forest_manager.reference_analysis.models",
    SRC / "reference_analysis" / "models.py",
)
analyzer = _load_module(
    "forest_manager.reference_analysis.analyzer",
    SRC / "reference_analysis" / "analyzer.py",
)
composition_plan = _load_module(
    "forest_manager.placement.composition_plan",
    SRC / "placement" / "composition_plan.py",
)
plan_builder = _load_module(
    "forest_manager.reference_analysis.plan_builder",
    SRC / "reference_analysis" / "plan_builder.py",
)

ReferenceImageAnalyzer = analyzer.ReferenceImageAnalyzer
ReferencePlanBuilder = plan_builder.ReferencePlanBuilder
ReferencePlanError = plan_builder.ReferencePlanError


def _write_minimal_png(path, width, height):
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_length = struct.pack(">I", 13)
    ihdr_type = b"IHDR"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    fake_crc = b"\x00\x00\x00\x00"
    path.write_bytes(signature + ihdr_length + ihdr_type + ihdr_data + fake_crc)


def test_reference_image_analyzer_reads_png_dimensions(tmp_path):
    image = tmp_path / "reference.png"
    _write_minimal_png(image, 1920, 1080)

    result = ReferenceImageAnalyzer().analyze(image)

    assert result.image.width == 1920
    assert result.image.height == 1080
    assert result.image.orientation == "landscape"
    assert result.analyzer == "stage4i_structural_v1"
    assert result.suggested_queries == ()


def test_reference_plan_builder_refuses_to_invent_species(tmp_path):
    image = tmp_path / "reference.png"
    _write_minimal_png(image, 1000, 1000)
    analysis = ReferenceImageAnalyzer().analyze(image)

    try:
        ReferencePlanBuilder().build(analysis)
    except ReferencePlanError as exc:
        assert "no plant queries" in str(exc).lower()
    else:
        raise AssertionError("Expected ReferencePlanError")


def test_reference_plan_builder_accepts_semantic_queries(tmp_path):
    image = tmp_path / "reference.png"
    _write_minimal_png(image, 1200, 800)
    structural = ReferenceImageAnalyzer().analyze(image)

    enriched = models.ReferenceAnalysisResult(
        image=structural.image,
        intent=structural.intent,
        suggested_queries=(
            "Acer campestre (Field maple)",
            "Alnus glutinosa (Black alder)",
        ),
        confidence=0.9,
        analyzer="test_semantic_analyzer",
    )

    plan = ReferencePlanBuilder().build(enriched)

    assert len(plan.items) == 2
    assert plan.items[0].query == "Acer campestre (Field maple)"
    assert plan.normalized_probabilities == [50.0, 50.0]
