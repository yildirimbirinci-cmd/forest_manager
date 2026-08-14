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

semantic = _load(
    "forest_manager.reference_analysis.semantic",
    SRC / "reference_analysis" / "semantic.py",
)
local_backend = _load(
    "forest_manager.reference_analysis.local_backend",
    SRC / "reference_analysis" / "local_backend.py",
)
transformers_backend = _load(
    "forest_manager.reference_analysis.transformers_local_backend",
    SRC / "reference_analysis" / "transformers_local_backend.py",
)
provider_module = _load(
    "forest_manager.reference_analysis.local_semantic_provider",
    SRC / "reference_analysis" / "local_semantic_provider.py",
)

LocalSemanticVisionProvider = provider_module.LocalSemanticVisionProvider
SemanticVisionError = semantic.SemanticVisionError


class FakeBackend:
    @property
    def name(self):
        return "test_backend"

    def is_available(self):
        return True

    def analyze(self, image_path, prompt):
        return {
            "style": "naturalistic",
            "density": "medium",
            "diversity": "medium",
            "canopy_bias": "mixed",
            "composition_notes": ["layered planting"],
            "plant_candidates": [
                {"query": "Acer campestre", "weight": 40},
                {"query": "Alnus glutinosa", "weight": 35},
                {"query": "Alnus x spaethii", "weight": 25},
            ],
            "confidence": 0.88,
        }


class UnavailableBackend:
    @property
    def name(self):
        return "missing"

    def is_available(self):
        return False

    def analyze(self, image_path, prompt):
        raise AssertionError("Should not be called")


def test_local_provider_has_no_cloud_dependency(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"local-test")

    provider = LocalSemanticVisionProvider(backend=FakeBackend())
    result = provider.analyze_image(
        str(image),
        width=1920,
        height=1080,
        orientation="landscape",
    )

    assert result.provider == "forest_manager_local_vision"
    assert len(result.plant_candidates) == 3
    assert result.confidence == 0.88


def test_local_provider_rejects_missing_backend(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"local-test")

    provider = LocalSemanticVisionProvider(backend=UnavailableBackend())

    try:
        provider.analyze_image(
            str(image),
            width=100,
            height=100,
            orientation="square",
        )
    except SemanticVisionError as exc:
        assert "not available" in str(exc).lower()
    else:
        raise AssertionError("Expected SemanticVisionError")


def test_local_provider_rejects_missing_fields(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"local-test")

    class IncompleteBackend(FakeBackend):
        def analyze(self, image_path, prompt):
            return {"style": "naturalistic"}

    provider = LocalSemanticVisionProvider(backend=IncompleteBackend())

    try:
        provider.analyze_image(
            str(image),
            width=100,
            height=100,
            orientation="square",
        )
    except SemanticVisionError as exc:
        assert "missing fields" in str(exc).lower()
    else:
        raise AssertionError("Expected SemanticVisionError")
