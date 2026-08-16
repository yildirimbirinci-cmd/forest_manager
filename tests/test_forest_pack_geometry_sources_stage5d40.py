from __future__ import annotations

import pytest

from forest_manager.forest_control.geometry import GeometrySourcePatch, GeometrySourcesAdapter
from forest_manager.forest_control.service import ForestControlError


class FakeService:
    def inventory(self, forest_name: str):
        names = {
            "cobjlist": "$Editable_Poly:Plant_A @ [0,0,0]",
            "matlist": "#Multi/Sub-Object:PlantMat(1)",
            "namelist": "Plant_A",
            "coloridlist": "1",
            "geomlist": "3",
            "tempidlist": "4",
            "tempnamelist": "Tmp",
            "widthlist": "1.25",
            "heightlist": "2.5",
            "ScaleList": "1.0",
            "zoffsetlist": "0.1",
            "centerlist": "0",
            "radiuslist": "1",
            "specidlist": "9",
            "usemeshdimlist": "true",
            "conamelist": "Plant_A",
            "includechildlist": "false",
            "keepgrouplist": "true",
            "nongeomlist": "false",
            "old_problist": "100",
            "problist": "100.0",
        }
        return {
            "properties": [
                {
                    "name": name,
                    "array_metadata": {"count": 1, "elements": [{"preview": value}]},
                }
                for name, value in names.items()
            ]
        }


def test_read_record_maps_geometry_arrays():
    record = GeometrySourcesAdapter(FakeService()).read_record("Forest", 1)
    assert record.index == 1
    assert record.name == "Plant_A"
    assert record.geometry_id == 3
    assert record.width == 1.25
    assert record.use_mesh_dimensions is True
    assert record.keep_group is True


def test_indices_are_one_based():
    with pytest.raises(ForestControlError, match="1-based"):
        GeometrySourcesAdapter(FakeService()).read_record("Forest", 0)


def test_write_path_is_explicitly_blocked_without_bridge_endpoint():
    with pytest.raises(ForestControlError, match="atomic writes are unavailable"):
        GeometrySourcesAdapter(FakeService()).update_existing("Forest", 1, GeometrySourcePatch(name="X"))


def test_app_policy_does_not_claim_unavailable_writes():
    from forest_manager.app import forest_pack_geometry_sources_stage5d40 as app
    source = app.__file__
    assert source
    text = open(source, "r", encoding="utf-8").read()
    assert '"atomic_update_api": False' in text
    assert '"rollback_on_failure": False' in text
    assert '"coloridlist_write": False' in text
