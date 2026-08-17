from __future__ import annotations

from forest_manager.forest_control.plant_group_execution import build_plant_group_area_plan


class FakeGeometry:
    pass


class FakeService:
    def inventory(self, forest_name, preflight=False):
        return {
            "properties": [
                {
                    "name": "cobjlist",
                    "array_metadata": {
                        "count": 3,
                        "elements": [
                            {"preview": "$CProxy:Lavender @ [0,0,0]"},
                            {"preview": "$CProxy:Butomus @ [0,0,0]"},
                            {"preview": "$CProxy:Berberis @ [0,0,0]"},
                        ],
                    },
                },
                {"name": "matlist", "array_metadata": {"elements": [{"preview": ""}] * 3}},
                {"name": "namelist", "array_metadata": {"elements": [{"preview": "Lavender"}, {"preview": "Butomus"}, {"preview": "Berberis"}]}},
                {"name": "geomlist", "array_metadata": {"elements": [{"preview": "2"}] * 3}},
                {"name": "tempidlist", "array_metadata": {"elements": [{"preview": "0"}] * 3}},
                {"name": "tempnamelist", "array_metadata": {"elements": [{"preview": ""}] * 3}},
                {"name": "widthlist", "array_metadata": {"elements": [{"preview": "1"}] * 3}},
                {"name": "heightlist", "array_metadata": {"elements": [{"preview": "1"}] * 3}},
                {"name": "ScaleList", "array_metadata": {"elements": [{"preview": "100"}] * 3}},
                {"name": "zoffsetlist", "array_metadata": {"elements": [{"preview": "0"}] * 3}},
                {"name": "centerlist", "array_metadata": {"elements": [{"preview": "50"}] * 3}},
                {"name": "radiuslist", "array_metadata": {"elements": [{"preview": "100"}] * 3}},
                {"name": "specidlist", "array_metadata": {"elements": [{"preview": "1"}, {"preview": "2"}, {"preview": "3"}]}},
                {"name": "usemeshdimlist", "array_metadata": {"elements": [{"preview": "false"}] * 3}},
                {"name": "conamelist", "array_metadata": {"elements": [{"preview": "Lavender"}, {"preview": "Butomus"}, {"preview": "Berberis"}]}},
                {"name": "includechildlist", "array_metadata": {"elements": [{"preview": "false"}] * 3}},
                {"name": "keepgrouplist", "array_metadata": {"elements": [{"preview": "false"}] * 3}},
                {"name": "nongeomlist", "array_metadata": {"elements": [{"preview": "false"}] * 3}},
                {"name": "old_problist", "array_metadata": {"elements": [{"preview": "33"}] * 3}},
                {"name": "problist", "array_metadata": {"elements": [{"preview": "33.33"}] * 3}},
            ]
        }

    def get_property(self, forest_name, property_name, preflight=True):
        count = 2
        return {"array_metadata": {"count": count}}

    def get_array_element(self, forest_name, property_name, index, preflight=True):
        table = {
            "aridlist": [1, 2],
            "pf_aractivelist": [False, True],
            "arnamelist": ["Surface Area", "Line001"],
            "arnodenamelist": ["", "Line001"],
            "artypelist": [3, 0],
            "arincexclist": [0, 0],
            "arwidthlist": [10.0, 10.0],
            "arthresholdlist": [100.0, 100.0],
            "arflafdenslist": [100.0, 100.0],
            "arflafscalist": [100.0, 100.0],
            "arboundchecklist": [0, 0],
            "arprojectlist": [2, 2],
            "arobscalelist": [100.0, 100.0],
            "arscalemin": [100.0, 100.0],
            "arscalemax": [100.0, 100.0],
            "arzoffset": [0.0, 0.0],
        }
        return {"value": table[property_name][index]}


def test_plan_uses_one_forest_area_scale_and_species_selection():
    manifest = {
        "primary_forest": "FM_Forest_001",
        "groups": [
            {"group_id": "foreground", "source_names": ["Lavender"], "spacing_system": [7500, 7500], "area_nodes": ["Line001"]},
            {"group_id": "mid", "source_names": ["Butomus"], "spacing_system": [7500, 7500], "area_nodes": ["Line001"]},
            {"group_id": "shrub", "source_names": ["Berberis"], "spacing_system": [2500, 2500], "area_nodes": ["Line001"]},
        ],
    }
    forest, base, plans = build_plant_group_area_plan(manifest, service=FakeService())
    assert forest == "FM_Forest_001"
    assert base == 2500.0
    assert [p.species_ids for p in plans] == [(1,), (2,), (3,)]
    assert [round(p.scale_percent, 4) for p in plans] == [300.0, 300.0, 100.0]
    assert {p.base_area_index for p in plans} == {1}
