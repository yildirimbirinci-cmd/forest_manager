from __future__ import annotations

import pytest

from forest_manager.forest_control.areas import AREA_RECORD_ARRAYS, AreaRecordsAdapter
from forest_manager.forest_control.service import ForestControlError


class FakeService:
    def inventory(self, forest_name: str):
        values = {
            "aridlist": "7", "pf_aractivelist": "true", "arnamelist": "Area A",
            "arnodelist": "$SplineShape:AreaSpline @ [1.0,2.0,3.0]", "arnodenamelist": "AreaSpline",
            "artypelist": "2", "arincexclist": "1", "arresollist": "5", "arslicelist": "false",
            "arslicetoplist": "10.5", "arwidthlist": "2.5", "arforceopenlist": "true",
            "armaplist": "undefined", "arscalelist": "100.0", "arthresholdlist": "0.25",
            "arsurfidlist": "surface-1", "arflafdenslist": "1.5", "arflafscalist": "2.5",
            "arflinvlist": "false", "arselspeclist": "true", "arspeclist": "1,2",
            "arpaintlist": "undefined", "arboundchecklist": "3", "arprojectlist": "4",
            "arshapelist": "5", "arobscalelist": "6.5", "arlinkidlist": "8",
            "arscalemin": "90", "arscalemax": "110", "arzoffset": "0.75",
        }
        return {"properties": [{"name": name, "array_metadata": {"count": 1, "elements": [{"preview": values[name]}]}} for name in AREA_RECORD_ARRAYS]}


def test_read_record_matches_recovered_contract():
    record = AreaRecordsAdapter(FakeService()).read_record("Forest", 1)
    assert record.area_id == 7
    assert record.active is True
    assert record.name == "Area A"
    assert record.node_name == "AreaSpline"
    assert record.width == 2.5
    assert record.scale == 100.0
    assert record.z_offset == 0.75


def test_no_op_plan_preserves_writable_record_values():
    adapter = AreaRecordsAdapter(FakeService())
    record = adapter.read_record("Forest", 1)
    patch = adapter.no_op_roundtrip_plan("Forest", 1)
    assert patch.name == record.name
    assert patch.node_name == record.node_name
    assert patch.scale == record.scale
    assert patch.z_offset == record.z_offset


def test_write_boundary_rejects_updates():
    adapter = AreaRecordsAdapter(FakeService())
    with pytest.raises(ForestControlError, match="unavailable"):
        adapter.update_existing("Forest", 1, adapter.no_op_roundtrip_plan("Forest", 1))


def test_read_only_arrays_remain_in_record_contract():
    assert "armaplist" in AREA_RECORD_ARRAYS
    assert "arpaintlist" in AREA_RECORD_ARRAYS
