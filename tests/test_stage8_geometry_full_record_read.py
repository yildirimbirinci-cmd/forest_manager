from __future__ import annotations

from forest_manager.forest_control.geometry import (
    GEOMETRY_SOURCE_ARRAYS,
    GeometrySourcesAdapter,
)
from forest_manager.forest_control.service import ForestControlError


class FakeService:
    def __init__(self, *, count: int = 12, mismatched_property: str | None = None):
        self.count = count
        self.mismatched_property = mismatched_property
        self.calls: list[tuple[str, str, int, bool]] = []

    def get_array_element(self, forest_name, property_name, index, *, preflight=True):
        self.calls.append((forest_name, property_name, index, preflight))
        count = self.count - 1 if property_name == self.mismatched_property else self.count
        values = {
            "cobjlist": "Lavandula_Source",
            "matlist": "Lavandula_Material",
            "namelist": "Lavandula angustifolia 'Hidcote' (Lavender)",
            "geomlist": 101,
            "specidlist": 7,
            "problist": 0.75,
            "usemeshdimlist": True,
        }
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "count": count,
            "value": values.get(property_name, 0),
            "verified": True,
        }


def test_complete_record_read_uses_zero_based_verified_array_endpoint():
    service = FakeService(count=12)
    adapter = GeometrySourcesAdapter(service=service)

    record = adapter.read_record("FM_Forest_001", 9)

    assert record.index == 9
    assert record.source_node == "Lavandula_Source"
    assert record.name == "Lavandula angustifolia 'Hidcote' (Lavender)"
    assert record.geometry_id == 101
    assert record.species_id == 7
    assert record.probability == 0.75
    assert record.use_mesh_dimensions is True

    assert len(service.calls) == len(GEOMETRY_SOURCE_ARRAYS)
    assert service.calls[0] == ("FM_Forest_001", "cobjlist", 8, True)
    assert all(call[2] == 8 for call in service.calls)
    assert all(call[3] is False for call in service.calls[1:])


def test_preview_limit_no_longer_exists_for_records_after_index_eight():
    service = FakeService(count=20)
    adapter = GeometrySourcesAdapter(service=service)

    raw = adapter.read_raw_record("FM_Forest_001", 17)

    assert raw["namelist"] == "Lavandula angustifolia 'Hidcote' (Lavender)"
    assert all(call[2] == 16 for call in service.calls)


def test_geometry_array_count_mismatch_fails_closed():
    service = FakeService(count=5, mismatched_property="namelist")
    adapter = GeometrySourcesAdapter(service=service)

    try:
        adapter.read_raw_record("FM_Forest_001", 1)
    except ForestControlError as exc:
        assert "array count mismatch" in str(exc)
        assert "namelist" in str(exc)
    else:
        raise AssertionError("Expected mismatched geometry array counts to fail closed.")


def test_adapter_rejects_invalid_public_indices_before_bridge_call():
    service = FakeService()
    adapter = GeometrySourcesAdapter(service=service)

    for value in (0, -1, True, 1.5):
        try:
            adapter.read_raw_record("FM_Forest_001", value)
        except ForestControlError:
            pass
        else:
            raise AssertionError(f"Expected invalid index rejection: {value!r}")
    assert service.calls == []
