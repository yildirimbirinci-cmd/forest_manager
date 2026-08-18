from __future__ import annotations

import inspect
from forest_manager.forest_control.geometry import GeometrySourcesAdapter


def test_geometry_record_read_uses_verified_array_element_endpoint():
    source = inspect.getsource(GeometrySourcesAdapter.read_raw_record)
    assert "get_array_element" in source
    assert "inventory(" not in source
    assert "discovery preview" not in source.lower()
    assert "index > 8" not in source
    assert "zero_index = index - 1" in source
