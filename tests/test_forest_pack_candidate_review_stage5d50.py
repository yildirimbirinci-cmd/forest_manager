from __future__ import annotations

from forest_manager.forest_control.candidate_review import (
    CANDIDATE_DOMAIN_MAP,
    CandidateReview,
)
from forest_manager.forest_control.undeclared_classification import USER_CONTROL_CANDIDATES


class FakeService:
    def inventory(self, forest_name: str):
        rows = []
        for name in sorted(USER_CONTROL_CANDIDATES):
            if name == "geomtex":
                mode = "read_only"
                value_class = "Bitmaptexture"
            elif name == "renderid":
                mode = "color"
                value_class = "Color"
            else:
                mode = "scalar"
                value_class = "Integer"
            rows.append(
                {
                    "name": name,
                    "value_class": value_class,
                    "write_mode": mode,
                    "writable": None,
                    "value": f"value:{name}",
                }
            )
        return {"properties": rows}


def test_candidate_domain_map_covers_all_40_candidates():
    assert len(USER_CONTROL_CANDIDATES) == 40
    assert set(CANDIDATE_DOMAIN_MAP) == set(USER_CONTROL_CANDIDATES)


def test_review_forest_assigns_domains_and_policies():
    result = CandidateReview(FakeService()).review_forest("FM_Forest_001")

    assert result["candidate_count"] == 40
    assert sum(result["domain_counts"].values()) == 40
    assert sum(result["policy_counts"].values()) == 40
    assert result["domain_counts"] == {
        "camera": 4,
        "collision": 2,
        "display": 5,
        "distribution": 12,
        "material": 1,
        "render": 4,
        "surface": 8,
        "transform": 4,
    }
    assert result["policy_counts"] == {
        "semantic_read_only_candidate": 1,
        "semantic_scalar_candidate": 38,
        "typed_color_candidate": 1,
    }


def test_review_preserves_value_and_inventory_metadata():
    result = CandidateReview(FakeService()).review_forest("FM_Forest_001")
    by_name = {item["name"]: item for item in result["candidates"]}

    assert by_name["geomtex"]["domain"] == "material"
    assert by_name["geomtex"]["value"] == "value:geomtex"
    assert by_name["geomtex"]["value_class"] == "Bitmaptexture"
    assert by_name["geomtex"]["write_mode"] == "read_only"
    assert by_name["geomtex"]["recommended_policy"] == "semantic_read_only_candidate"
