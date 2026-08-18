from forest_manager.forest_control import vector_area_binding as module


def test_semantic_groups_are_routed_to_real_vector_helper_roles(monkeypatch):
    monkeypatch.setattr(
        module,
        "_source_species_map",
        lambda forest_name, service: {
            "Lavender": 1,
            "Rose": 2,
            "Carex": 3,
            "Ilex": 4,
            "Oak": 5,
        },
    )
    groups = [
        {"group_id": "g1", "semantic_role": "foreground_mass", "source_names": ["Lavender"]},
        {"group_id": "g2", "semantic_role": "flower_accent", "source_names": ["Rose"]},
        {"group_id": "g3", "semantic_role": "mid_accent", "source_names": ["Carex"]},
        {"group_id": "g4", "semantic_role": "structural_shrub", "source_names": ["Ilex"]},
        {"group_id": "g5", "semantic_role": "tree_canopy", "source_names": ["Oak"]},
    ]
    helpers = [
        "FM_Region_Line001_Wall_001",
        "FM_Region_Line001_Walkway_001",
        "FM_Region_Line001_Walkway_002",
        "FM_Region_Line001_Walkway_003",
        "FM_Region_Line001_Interior_001",
    ]
    result = module.build_vector_area_species_bindings(
        forest_name="FM_Forest_001",
        source_node_name="Line001",
        helper_names=helpers,
        plant_groups=groups,
        service=object(),
    )
    by_helper = {item["helper_name"]: item for item in result}
    assert by_helper["FM_Region_Line001_Wall_001"]["species_ids"] == [4, 5]
    assert by_helper["FM_Region_Line001_Walkway_001"]["species_ids"] == [1, 2]
    assert by_helper["FM_Region_Line001_Walkway_003"]["species_ids"] == [1, 2]
    assert by_helper["FM_Region_Line001_Interior_001"]["species_ids"] == [3]


def test_interior_falls_back_to_resolved_flowering_species_when_no_mid_role(monkeypatch):
    monkeypatch.setattr(
        module,
        "_source_species_map",
        lambda forest_name, service: {
            "Salvia": 1,
            "Rose": 2,
            "Berberis": 3,
            "Acer": 4,
        },
    )
    groups = [
        {"group_id": "plant_group:1:flower_accent", "semantic_role": "flower_accent", "source_names": ["Salvia"]},
        {"group_id": "plant_group:2:flower_accent", "semantic_role": "flower_accent", "source_names": ["Rose"]},
        {"group_id": "plant_group:4:structural_shrub", "semantic_role": "structural_shrub", "source_names": ["Berberis"]},
        {"group_id": "plant_group:5:tree_canopy", "semantic_role": "tree_canopy", "source_names": ["Acer"]},
    ]
    helpers = [
        "FM_Region_Line001_Wall_001",
        "FM_Region_Line001_Walkway_001",
        "FM_Region_Line001_Interior_001",
    ]

    result = module.build_vector_area_species_bindings(
        forest_name="FM_Forest_001",
        source_node_name="Line001",
        helper_names=helpers,
        plant_groups=groups,
        service=object(),
    )

    by_helper = {item["helper_name"]: item for item in result}
    assert by_helper["FM_Region_Line001_Wall_001"]["species_ids"] == [3, 4]
    assert by_helper["FM_Region_Line001_Walkway_001"]["species_ids"] == [1, 2]
    assert by_helper["FM_Region_Line001_Interior_001"]["species_ids"] == [1, 2]


def test_region_footprint_guard_excludes_oversized_wall_tree(monkeypatch):
    monkeypatch.setattr(
        module,
        "_source_species_map",
        lambda forest_name, service: {"Ilex": 7, "Oak": 8, "Lavender": 1, "Rose": 5},
    )
    monkeypatch.setattr(
        module,
        "get_geometry_source_world_diagnostic",
        lambda forest_name, species_ids, preflight=False: {
            "scene_units": {"one_meter_system_units": 100.0},
            "items": [
                {"species_id": 7, "source_node": "Ilex", "bounds_ok": True, "width_system": 98.0, "depth_system": 103.0},
                {"species_id": 8, "source_node": "Oak", "bounds_ok": True, "width_system": 1989.6, "depth_system": 2084.77},
                {"species_id": 1, "source_node": "Lavender", "bounds_ok": True, "width_system": 163.0, "depth_system": 136.0},
                {"species_id": 5, "source_node": "Rose", "bounds_ok": True, "width_system": 119.0, "depth_system": 123.0},
            ],
            "verified": True,
        },
    )
    groups = [
        {"semantic_role": "structural_shrub", "source_names": ["Ilex"]},
        {"semantic_role": "tree_canopy", "source_names": ["Oak"]},
        {"semantic_role": "flower_accent", "source_names": ["Lavender", "Rose"]},
    ]
    helpers = [
        "FM_Region_Line001_Wall_001",
        "FM_Region_Line001_Walkway_001",
        "FM_Region_Line001_Interior_001",
    ]
    result = module.build_vector_area_species_bindings(
        forest_name="FM_Forest_001",
        source_node_name="Line001",
        helper_names=helpers,
        plant_groups=groups,
        service=object(),
        wall_band_meters=1.2,
        walkway_band_meters=0.6,
    )
    by_helper = {item["helper_name"]: item for item in result}
    wall = by_helper["FM_Region_Line001_Wall_001"]
    assert wall["species_ids"] == [7]
    assert wall["excluded_species"][0]["species_id"] == 8
    assert wall["excluded_species"][0]["source_node"] == "Oak"
    assert by_helper["FM_Region_Line001_Walkway_001"]["species_ids"] == [1, 5]
