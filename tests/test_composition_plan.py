from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "forest_manager"
    / "placement"
    / "composition_plan.py"
)

spec = importlib.util.spec_from_file_location(
    "forest_manager_composition_plan_isolated",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
import sys as _sys
_sys.modules[spec.name] = module
spec.loader.exec_module(module)

CompositionPlan = module.CompositionPlan


def test_composition_plan_normalizes_weights():
    plan = CompositionPlan.from_dict({
        "name": "test",
        "items": [
            {"query": "A", "weight": 40},
            {"query": "B", "weight": 35},
            {"query": "C", "weight": 25},
        ],
    })
    assert plan.normalized_probabilities == [40.0, 35.0, 25.0]


def test_composition_plan_normalizes_arbitrary_positive_weights():
    plan = CompositionPlan.from_dict({
        "items": [
            {"query": "A", "weight": 2},
            {"query": "B", "weight": 1},
        ],
    })
    probabilities = plan.normalized_probabilities
    assert round(probabilities[0], 6) == round(200 / 3, 6)
    assert round(probabilities[1], 6) == round(100 / 3, 6)


def test_composition_plan_rejects_empty_items():
    try:
        CompositionPlan.from_dict({"items": []})
    except ValueError as exc:
        assert "requires at least one item" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
