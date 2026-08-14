import json
import socket
import threading

from forest_manager.core.config import MaxBridgeConfig
from forest_manager.max_bridge.client import MaxBridgeClient


def _serve_once(listener, expected_command, response):
    conn, _ = listener.accept()
    with conn:
        reader = conn.makefile("rb")
        command = reader.readline().decode("ascii").strip()
        assert command == expected_command
        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))


def _round_trip(expected_command, response, method_name):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    thread = threading.Thread(
        target=_serve_once,
        args=(listener, expected_command, response),
        daemon=True,
    )
    thread.start()

    client = MaxBridgeClient(
        MaxBridgeConfig(host="127.0.0.1", port=port, timeout_seconds=1.0)
    )
    result = getattr(client, method_name)()

    thread.join(timeout=2.0)
    listener.close()
    return result


def test_ping_round_trip():
    result = _round_trip(
        "PING",
        {
            "ok": True,
            "command": "PING",
            "data": {"max_year": 2020, "bridge_version": "0.2.0"},
            "error": "",
        },
        "ping",
    )
    assert result.ok is True
    assert result.data["max_year"] == 2020


def test_forestpack_info_round_trip():
    result = _round_trip(
        "GET_FORESTPACK_INFO",
        {
            "ok": True,
            "command": "GET_FORESTPACK_INFO",
            "data": {"available": True, "class_name": "::Forest_Pro", "forest_count": 0},
            "error": "",
        },
        "get_forestpack_info",
    )
    assert result.ok is True
    assert result.data["available"] is True


def test_create_forest_round_trip():
    result = _round_trip(
        "CREATE_FOREST_FROM_SELECTION",
        {
            "ok": True,
            "command": "CREATE_FOREST_FROM_SELECTION",
            "data": {
                "forest_name": "FM_Forest_001",
                "area_count": 1,
                "area_node": "Line001",
                "include": True,
                "verified": True,
            },
            "error": "",
        },
        "create_forest_from_selection",
    )
    assert result.ok is True
    assert result.data["verified"] is True


def test_geometry_contract_round_trip():
    result = _round_trip(
        "GET_FOREST_GEOMETRY_CONTRACT",
        {
            "ok": True,
            "command": "GET_FOREST_GEOMETRY_CONTRACT",
            "data": {
                "forest_name": "FM_Forest_001",
                "property_count": 400,
                "geometry_candidates": ["namelist", "matlist"],
            },
            "error": "",
        },
        "get_forest_geometry_contract",
    )
    assert result.ok is True
    assert "namelist" in result.data["geometry_candidates"]


def test_geometry_contract_details_round_trip():
    result = _round_trip(
        "GET_FOREST_GEOMETRY_CONTRACT_DETAILS",
        {
            "ok": True,
            "command": "GET_FOREST_GEOMETRY_CONTRACT_DETAILS",
            "data": {
                "forest_name": "FM_Forest_001",
                "properties": [
                    {
                        "name": "geomlist",
                        "exists": True,
                        "value_class": "ArrayParameter",
                        "count": 1,
                        "first_class": "undefined",
                        "first_value": "undefined",
                    }
                ],
            },
            "error": "",
        },
        "get_forest_geometry_contract_details",
    )
    assert result.ok is True
    assert result.data["properties"][0]["name"] == "geomlist"


def test_add_selected_geometry_round_trip():
    result = _round_trip(
        "ADD_SELECTED_GEOMETRY_TO_FOREST",
        {
            "ok": True,
            "command": "ADD_SELECTED_GEOMETRY_TO_FOREST",
            "data": {
                "forest_name": "FM_Forest_001",
                "source_name": "Box001",
                "geometry_count": 1,
                "geometry_index": 1,
                "probability": 100.0,
                "verified": True,
            },
            "error": "",
        },
        "add_selected_geometry_to_forest",
    )
    assert result.ok is True
    assert result.data["source_name"] == "Box001"
    assert result.data["geometry_count"] == 1
    assert result.data["verified"] is True


def test_distribution_contract_round_trip():
    result = _round_trip(
        "GET_FOREST_DISTRIBUTION_CONTRACT",
        {
            "ok": True,
            "command": "GET_FOREST_DISTRIBUTION_CONTRACT",
            "data": {
                "forest_name": "FM_Forest_001",
                "property_count": 341,
                "properties": [
                    {"name": "density", "value_class": "Float", "value": "100.0"}
                ],
            },
            "error": "",
        },
        "get_forest_distribution_contract",
    )
    assert result.ok is True
    assert result.data["forest_name"] == "FM_Forest_001"


def test_distribution_units_round_trip():
    result = _round_trip(
        "GET_FOREST_DISTRIBUTION_UNITS",
        {
            "ok": True,
            "command": "GET_FOREST_DISTRIBUTION_UNITS",
            "data": {
                "forest_name": "FM_Forest_001",
                "properties": [
                    {"name": "units", "value_class": "Float", "value": "1000.0"}
                ],
            },
            "error": "",
        },
        "get_forest_distribution_units",
    )
    assert result.ok is True
    assert result.data["forest_name"] == "FM_Forest_001"


def test_adaptive_distribution_round_trip():
    result = _round_trip(
        "CONFIGURE_ADAPTIVE_DISTRIBUTION",
        {
            "ok": True,
            "command": "CONFIGURE_ADAPTIVE_DISTRIBUTION",
            "data": {
                "forest_name": "FM_Forest_001",
                "area_node": "Line001",
                "area_size_x": 500.0,
                "area_size_y": 400.0,
                "previous_units_x": 10000.0,
                "previous_units_y": 10000.0,
                "units_x": 20.0,
                "units_y": 20.0,
                "distmode": 0,
                "verified": True,
            },
            "error": "",
        },
        "configure_adaptive_distribution",
    )
    assert result.ok is True
    assert result.data["previous_units_x"] == 10000.0
    assert result.data["units_x"] == 20.0
    assert result.data["verified"] is True


def test_normalize_forest_build_state_round_trip():
    result = _round_trip(
        "NORMALIZE_FOREST_BUILD_STATE",
        {
            "ok": True,
            "command": "NORMALIZE_FOREST_BUILD_STATE",
            "data": {
                "forest_name": "FM_Forest_001",
                "previous_disabled": True,
                "disabled": False,
                "manualupdate": False,
                "units_x": 25.0,
                "units_y": 25.0,
                "verified": True,
            },
            "error": "",
        },
        "normalize_forest_build_state",
    )
    assert result.ok is True
    assert result.data["disabled"] is False
    assert result.data["verified"] is True


def test_full_runtime_contract_round_trip():
    result = _round_trip(
        "GET_FOREST_FULL_RUNTIME_CONTRACT",
        {
            "ok": True,
            "command": "GET_FOREST_FULL_RUNTIME_CONTRACT",
            "data": {
                "forest_name": "FM_Forest_001",
                "array_properties": [{"name": "cobjlist", "count": 1, "first_class": "Box", "first_value": "$Box:Box001"}],
                "state_properties": [{"name": "disabled", "value_class": "BooleanClass", "value": "false"}],
                "geometry_count": 1,
                "source_name": "Box001",
            },
            "error": "",
        },
        "get_forest_full_runtime_contract",
    )
    assert result.ok is True
    assert result.data["geometry_count"] == 1
    assert result.data["source_name"] == "Box001"


def test_normalize_geometry_item_round_trip():
    result = _round_trip(
        "NORMALIZE_GEOMETRY_ITEM",
        {
            "ok": True,
            "command": "NORMALIZE_GEOMETRY_ITEM",
            "data": {
                "forest_name": "FM_Forest_001",
                "source_name": "Box001",
                "geometry_mode": 2,
                "temp_name": "Box001",
                "width": 50.0,
                "depth": 50.0,
                "height": 50.0,
                "generated_items_before": 0,
                "generated_items_after": 25,
                "verified": True,
            },
            "error": "",
        },
        "normalize_geometry_item",
    )
    assert result.ok is True
    assert result.data["geometry_mode"] == 2
    assert result.data["temp_name"] == "Box001"
    assert result.data["verified"] is True


def test_merge_t2_asset_preserves_path_case_and_round_trips():
    import base64

    asset_path = r"C:\T2 Library\Acer Campestre\Acer campestre.max"
    encoded = base64.b64encode(asset_path.encode("utf-8")).decode("ascii")
    expected = "MERGE_T2_ASSET|" + encoded

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    response = {
        "ok": True,
        "command": "MERGE_T2_ASSET",
        "data": {
            "asset_path": asset_path,
            "forest_name": "FM_Forest_001",
            "merged_node_count": 3,
            "source_name": "Acer_Campestre",
            "geometry_count": 1,
            "geometry_mode": 2,
            "generated_items": 120,
            "verified": True,
        },
        "error": "",
    }

    thread = threading.Thread(
        target=_serve_once,
        args=(listener, expected, response),
        daemon=True,
    )
    thread.start()

    client = MaxBridgeClient(
        MaxBridgeConfig(host="127.0.0.1", port=port, timeout_seconds=1.0)
    )
    result = client.merge_t2_asset_and_bind(asset_path)

    thread.join(timeout=2.0)
    listener.close()

    assert result.ok is True
    assert result.data["asset_path"] == asset_path
    assert result.data["geometry_mode"] == 2
    assert result.data["verified"] is True


def test_asset_aware_density_round_trip():
    result = _round_trip(
        "CONFIGURE_ASSET_AWARE_DENSITY",
        {
            "ok": True,
            "command": "CONFIGURE_ASSET_AWARE_DENSITY",
            "data": {
                "forest_name": "FM_Forest_001",
                "source_name": "Acer campestre (Field maple)",
                "source_class": "CProxy",
                "source_footprint_x": 542.135,
                "source_footprint_y": 564.932,
                "area_size_x": 1000.0,
                "area_size_y": 900.0,
                "previous_units_x": 21.6697,
                "previous_units_y": 21.6697,
                "units_x": 569.24175,
                "units_y": 593.1786,
                "generated_items_before": 40893,
                "generated_items_after": 24,
                "verified": True,
            },
            "error": "",
        },
        "configure_asset_aware_density",
    )
    assert result.ok is True
    assert result.data["source_class"] == "CProxy"
    assert result.data["generated_items_after"] == 24
    assert result.data["verified"] is True


def test_target_item_density_round_trip():
    result = _round_trip(
        "CONFIGURE_TARGET_ITEM_DENSITY",
        {
            "ok": True,
            "command": "CONFIGURE_TARGET_ITEM_DENSITY",
            "data": {
                "forest_name": "FM_Forest_001",
                "area_node": "Line001",
                "area_size_x": 10000.0,
                "area_size_y": 9000.0,
                "bbox_area": 90000000.0,
                "target_items": 45000,
                "previous_units_x": 569.0,
                "previous_units_y": 593.0,
                "pass1_items": 35343,
                "pass2_items": 44920,
                "units_x": 39.7,
                "units_y": 44.72136,
                "generated_items_before": 1000,
                "generated_items_after": 45000,
                "verified": True,
            },
            "error": "",
        },
        "configure_target_item_density",
    )
    assert result.ok is True
    assert result.data["target_items"] == 45000
    assert result.data["generated_items_after"] == 45000
    assert result.data["verified"] is True


def test_fixed_distribution_units_round_trip():
    result = _round_trip(
        "CONFIGURE_FIXED_DISTRIBUTION_UNITS",
        {
            "ok": True,
            "command": "CONFIGURE_FIXED_DISTRIBUTION_UNITS",
            "data": {
                "forest_name": "FM_Forest_001",
                "target_units": 45000.0,
                "previous_units_x": 45000.0,
                "previous_units_y": 4333.948,
                "units_x": 45000.0,
                "units_y": 45000.0,
                "maxdensity": 10,
                "generated_items_before": 24,
                "generated_items_after": 1,
                "verified": True,
            },
            "error": "",
        },
        "configure_fixed_distribution_units",
    )
    assert result.ok is True
    assert result.data["units_x"] == 45000.0
    assert result.data["units_y"] == 45000.0
    assert result.data["maxdensity"] == 10
    assert result.data["verified"] is True
