from dataclasses import asdict

from forest_manager.forest_control.areas import AreaRecordsAdapter
from test_forest_pack_area_records_stage5d42 import FakeService


def test_no_op_roundtrip_normalization_matches_patch():
    adapter = AreaRecordsAdapter(FakeService())
    record = asdict(adapter.read_record("Forest", 1))
    record.pop("raw", None)
    record.pop("index", None)
    record.pop("area_id", None)
    patch = asdict(adapter.no_op_roundtrip_plan("Forest", 1))
    assert record == patch


def test_roundtrip_is_plan_only_on_verified_bridge_boundary():
    adapter = AreaRecordsAdapter(FakeService())
    patch = adapter.no_op_roundtrip_plan("Forest", 1)
    assert patch.name == "Area A"
    assert patch.node_name == "AreaSpline"
