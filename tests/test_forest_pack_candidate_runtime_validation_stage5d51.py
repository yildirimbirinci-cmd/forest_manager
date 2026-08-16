from forest_manager.forest_control.candidate_runtime_validation import (
    CandidateRuntimeValidator,
    READ_ONLY_CANDIDATES,
    SCALAR_CANDIDATES,
)


class FakeService:
    def __init__(self):
        self.rows = []
        for name in sorted(set(SCALAR_CANDIDATES) | READ_ONLY_CANDIDATES):
            self.rows.append(
                {
                    "name": name,
                    "value": None if name in READ_ONLY_CANDIDATES else 1,
                    "value_class": "UndefinedClass" if name in READ_ONLY_CANDIDATES else "Integer",
                    "write_mode": "read_only" if name in READ_ONLY_CANDIDATES else "scalar",
                }
            )

    def inventory(self, forest_name):
        return {"properties": [dict(row) for row in self.rows]}


def test_candidate_runtime_contract_counts_40_candidates():
    assert len(SCALAR_CANDIDATES) == 38
    assert READ_ONLY_CANDIDATES == {"divtmap", "geomtex"}


def test_validator_reports_runtime_boundary_without_write_endpoint():
    result = CandidateRuntimeValidator(FakeService()).validate_forest("FM_Forest_001")
    assert result["candidate_count"] == 40
    assert result["scalar_candidate_count"] == 38
    assert result["declared_read_only_candidate_count"] == 2
    assert result["successful_write_count"] == 0
    assert result["status_counts"] == {
        "declared_read_only_candidate": 2,
        "runtime_probe_blocked": 38,
    }
    assert result["write_preserved"] is True
    assert result["rollback_preserved"] is True
    assert result["runtime_write_endpoint"] is False
    assert result["runtime_rollback_endpoint"] is False


def test_validator_uses_inventory_values_and_domains():
    result = CandidateRuntimeValidator(FakeService()).validate_forest("FM_Forest_001")
    by_name = {item["name"]: item for item in result["results"]}
    assert by_name["distmode"]["domain"] == "distribution"
    assert by_name["divtmap"]["status"] == "declared_read_only_candidate"
    assert by_name["geomtex"]["status"] == "declared_read_only_candidate"
