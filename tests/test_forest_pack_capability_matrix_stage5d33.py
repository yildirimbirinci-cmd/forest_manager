from forest_manager.forest_control.service import ForestProperty, ForestSnapshot, aggregate_capability_matrix


def snap(name):
    return ForestSnapshot(
        name,
        4,
        {"read_only": 1, "scalar": 2, "color": 1},
        (
            ForestProperty("a", "Float", "scalar", True, 1.0),
            ForestProperty("b", "BooleanClass", "scalar", True, False),
            ForestProperty("c", "Color", "color", True, "[0,0,0]"),
            ForestProperty(
                "d",
                "ArrayParameter",
                "read_only",
                True,
                array_metadata={"count": 1},
            ),
        ),
        (
            {
                "name": "d",
                "metadata": {
                    "count": 1,
                    "preview_count": 1,
                    "element_classes": ["Float"],
                    "elements": [{"value_class": "Float", "preview": "1.0"}],
                },
            },
        ),
    )


def test_matrix():
    matrix = aggregate_capability_matrix(tuple(snap(f"FM_{i}") for i in range(4)))

    assert matrix["forest_count"] == 4
    assert matrix["aggregate_write_mode_counts"] == {"read_only": 4, "scalar": 8, "color": 4}
    assert matrix["array_element_class_signatures"]["Float"] == 4

    # Stage 5D.33 introduced the discovery matrix, but later verified stages promoted
    # supported array families to transactional element-write paths. Keep this
    # historical regression test aligned with the current promoted contract.
    assert matrix["policy"]["array_parameter"] == "primitive_scalar_and_point3_element_write"
    assert matrix["policy"]["node_reference_arrays"] == "arnodelist_transactional"
    assert matrix["policy"]["material_reference_arrays"] == "matlist_transactional"
    assert matrix["policy"]["cproxy_reference_arrays"] == "cobjlist_transactional"
    assert matrix["verified"] is True
