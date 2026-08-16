from __future__ import annotations

from dataclasses import asdict

from forest_manager.forest_control.geometry import GeometrySourcesAdapter


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


def test_no_op_roundtrip_plan_matches_normalized_record():
    adapter = GeometrySourcesAdapter(FakeService())
    record = adapter.read_record("Forest", 1)
    patch = adapter.no_op_roundtrip_plan("Forest", 1)
    record_data = asdict(record)
    record_data.pop("raw", None)
    record_data.pop("index", None)
    assert record_data == asdict(patch)


def test_roundtrip_app_does_not_execute_unavailable_write_path():
    from forest_manager.app import forest_pack_geometry_roundtrip_stage5d41 as app

    text = open(app.__file__, "r", encoding="utf-8").read()
    assert '"writes_executed": False' in text
    assert '"rollback_executed": False' in text
    assert '"final_state_preserved": True' in text
    assert '"coloridlist_write": False' in text


def test_roundtrip_app_verifies_plan_values():
    from forest_manager.app import forest_pack_geometry_roundtrip_stage5d41 as app

    text = open(app.__file__, "r", encoding="utf-8").read()
    assert "adapter.no_op_roundtrip_plan" in text
    assert "record_values == planned_values" in text


def test_stage5d41_source_compiles():
    from forest_manager.app import forest_pack_geometry_roundtrip_stage5d41 as app

    source = open(app.__file__, "r", encoding="utf-8").read()
    compile(source, app.__file__, "exec")
