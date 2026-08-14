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

placement_pkg = types.ModuleType("forest_manager.placement")
placement_pkg.__path__ = [str(SRC / "placement")]
sys.modules.setdefault("forest_manager.placement", placement_pkg)

semantic = _load(
    "forest_manager.reference_analysis.semantic",
    SRC / "reference_analysis" / "semantic.py",
)
composition_plan = _load(
    "forest_manager.placement.composition_plan",
    SRC / "placement" / "composition_plan.py",
)
semantic_plan = _load(
    "forest_manager.reference_analysis.semantic_plan_builder",
    SRC / "reference_analysis" / "semantic_plan_builder.py",
)
json_provider = _load(
    "forest_manager.reference_analysis.json_semantic_provider",
    SRC / "reference_analysis" / "json_semantic_provider.py",
)


def test_semantic_plan_preserves_weights():
    analysis = semantic.SemanticLandscapeAnalysis(
        style="naturalistic",
        density="medium",
        diversity="medium",
        canopy_bias="mixed",
        composition_notes=("note",),
        plant_candidates=(
            semantic.SemanticPlantCandidate("Acer", 40),
            semantic.SemanticPlantCandidate("Alnus", 35),
            semantic.SemanticPlantCandidate("Spaeth", 25),
        ),
        confidence=0.9,
        provider="test",
    )

    plan = semantic_plan.SemanticCompositionPlanBuilder().build(
        analysis,
        image_filename="reference.jpg",
    )

    assert plan.normalized_probabilities == [40.0, 35.0, 25.0]


def test_semantic_plan_rejects_low_confidence():
    analysis = semantic.SemanticLandscapeAnalysis(
        style="unknown",
        density="unknown",
        diversity="unknown",
        canopy_bias="unknown",
        composition_notes=(),
        plant_candidates=(
            semantic.SemanticPlantCandidate("Acer", 1),
        ),
        confidence=0.2,
        provider="test",
    )

    try:
        semantic_plan.SemanticCompositionPlanBuilder().build(
            analysis,
            image_filename="reference.jpg",
        )
    except semantic_plan.SemanticPlanError as exc:
        assert "confidence" in str(exc).lower()
    else:
        raise AssertionError("Expected SemanticPlanError")


def test_json_provider_parses_contract(tmp_path):
    payload = {
        "style": "naturalistic",
        "density": "medium",
        "diversity": "high",
        "canopy_bias": "tall",
        "composition_notes": ["mixed"],
        "plant_candidates": [
            {"query": "Acer", "weight": 2},
            {"query": "Alnus", "weight": 1},
        ],
        "confidence": 0.8,
    }
    path = tmp_path / "semantic.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    provider = json_provider.JsonSemanticVisionProvider(path)
    result = provider.analyze_image(
        "reference.jpg",
        width=1920,
        height=1080,
        orientation="landscape",
    )

    assert result.provider == "json_contract_provider"
    assert len(result.plant_candidates) == 2
    assert result.confidence == 0.8
