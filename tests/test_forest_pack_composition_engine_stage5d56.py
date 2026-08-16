from pathlib import Path

import pytest

from forest_manager.forest_control.composition import (
    CompositionControlError,
    CompositionControlService,
    EXPECTED_LAYERS,
    validate_three_layer_composition,
)


def _masks(tmp_path: Path):
    layers = []
    for index, name in enumerate(EXPECTED_LAYERS, start=1):
        path = tmp_path / f"mask_{index}.png"
        path.write_bytes(b"mask")
        layers.append({"forest_name": name, "soft_mask": str(path)})
    return {
        "verified": True,
        "policy": "deterministic_species_cluster_masks_v2",
        "layers": layers,
    }


def _composition():
    return {
        "legacy_forest_disabled": True,
        "all_species_layers_active": True,
        "layers": [
            {
                "forest_name": name,
                "active": True,
                "generated_items": 10 + index,
                "density_meters_x": 75.0,
                "density_meters_y": 75.0,
            }
            for index, name in enumerate(EXPECTED_LAYERS)
        ],
    }


def test_validate_three_layer_composition_preserves_75m_and_order():
    validate_three_layer_composition(_composition())
    broken = _composition()
    broken["layers"][0]["density_meters_x"] = 74.0
    with pytest.raises(CompositionControlError):
        validate_three_layer_composition(broken)


def test_apply_clustered_three_layer_preserves_command_order(tmp_path):
    commands = []

    def send(command):
        commands.append(command)
        if command == "PREPARE_SPECIES_LAYER_FORESTS":
            data = {"prepared_layers_disabled": True}
        elif command.startswith("BIND_SPECIES_DISTRIBUTION_MASKS|"):
            data = {"verified": True}
        elif command == "CONFIGURE_SPECIES_MAP_PROJECTION":
            data = {"projection": "forest_xy_tiled_75m"}
        elif command == "ACTIVATE_ALL_SPECIES_LAYERS":
            data = _composition()
        elif command == "SET_ALL_FOREST_POINT_CLOUD":
            data = {"vmesh": 3, "render_settings_changed": False}
        else:
            raise AssertionError(command)
        return {"ok": True, "data": data}

    service = CompositionControlService(
        command_sender=send,
        bridge_ensurer=lambda: {"ok": True, "data": {"bridge_version": "test"}},
        mask_generator=lambda _: _masks(tmp_path),
    )
    result = service.apply_clustered_three_layer(tmp_path)

    assert commands[0] == "PREPARE_SPECIES_LAYER_FORESTS"
    assert commands[1].startswith("BIND_SPECIES_DISTRIBUTION_MASKS|")
    assert commands[2:] == [
        "CONFIGURE_SPECIES_MAP_PROJECTION",
        "ACTIVATE_ALL_SPECIES_LAYERS",
        "SET_ALL_FOREST_POINT_CLOUD",
    ]
    assert result.projection["projection"] == "forest_xy_tiled_75m"
    assert result.point_cloud == {"vmesh": 3, "render_settings_changed": False}


def test_prepare_must_disable_layers_before_binding(tmp_path):
    def send(command):
        if command == "PREPARE_SPECIES_LAYER_FORESTS":
            return {"ok": True, "data": {"prepared_layers_disabled": False}}
        raise AssertionError("binding must not run after failed prepare")

    service = CompositionControlService(
        command_sender=send,
        bridge_ensurer=lambda: {"ok": True, "data": {}},
        mask_generator=lambda _: _masks(tmp_path),
    )
    with pytest.raises(CompositionControlError):
        service.apply_clustered_three_layer(tmp_path)
