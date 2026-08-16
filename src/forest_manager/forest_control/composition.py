from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command
from forest_manager.placement.species_mask_generator import generate_species_cluster_masks

EXPECTED_DENSITY_METERS = 75.0
EXPECTED_LAYERS = (
    "FM_Layer_01_foreground_mass",
    "FM_Layer_02_mid_accent",
    "FM_Layer_03_structural_shrub",
)
DEFAULT_MASK_OUTPUT_DIR = Path("resources/generated_masks/stage5d18")


@dataclass(frozen=True)
class CompositionRuntimeResult:
    bridge: dict[str, Any]
    masks: dict[str, Any]
    prepared: dict[str, Any]
    binding: dict[str, Any]
    projection: dict[str, Any]
    composition: dict[str, Any]
    point_cloud: dict[str, Any]


class CompositionControlError(RuntimeError):
    pass


def _require_ok(response: dict[str, Any], command: str) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise CompositionControlError(f"{command} failed: {response!r}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise CompositionControlError(f"{command} returned invalid data: {response!r}")
    return data


def validate_three_layer_composition(data: dict[str, Any]) -> None:
    if data.get("legacy_forest_disabled") is not True:
        raise CompositionControlError("Legacy Forest must remain disabled.")
    if data.get("all_species_layers_active") is not True:
        raise CompositionControlError("All three species layers must be active.")

    layers = data.get("layers") or []
    if len(layers) != 3:
        raise CompositionControlError("Exactly three species layers are required.")

    names = tuple(str(layer.get("forest_name") or "") for layer in layers)
    if names != EXPECTED_LAYERS:
        raise CompositionControlError(f"Unexpected species layer order: {names}")

    for layer in layers:
        if layer.get("active") is not True:
            raise CompositionControlError(f"Inactive species layer: {layer.get('forest_name')}")
        if int(layer.get("generated_items") or 0) <= 0:
            raise CompositionControlError(f"Zero generated items: {layer.get('forest_name')}")
        if abs(float(layer.get("density_meters_x", 0.0)) - EXPECTED_DENSITY_METERS) > 0.001:
            raise CompositionControlError(f"Density X changed: {layer.get('forest_name')}")
        if abs(float(layer.get("density_meters_y", 0.0)) - EXPECTED_DENSITY_METERS) > 0.001:
            raise CompositionControlError(f"Density Y changed: {layer.get('forest_name')}")


class CompositionControlService:
    """Known-good Stage 5D.31 composition workflow behind one service."""

    def __init__(
        self,
        command_sender: Callable[[str], dict[str, Any]] = send_command,
        bridge_ensurer: Callable[[], dict[str, Any]] = ensure_current_bridge,
        mask_generator: Callable[[Path], dict[str, Any]] = generate_species_cluster_masks,
    ) -> None:
        self._send = command_sender
        self._ensure_bridge = bridge_ensurer
        self._generate_masks = mask_generator

    def apply_clustered_three_layer(
        self,
        mask_output_dir: Path = DEFAULT_MASK_OUTPUT_DIR,
    ) -> CompositionRuntimeResult:
        bridge = self._ensure_bridge()
        masks = self._generate_masks(mask_output_dir.resolve())

        if masks.get("verified") is not True:
            raise CompositionControlError("Cluster mask generation failed verification.")
        if masks.get("policy") != "deterministic_species_cluster_masks_v2":
            raise CompositionControlError(
                f"Unexpected cluster mask policy: {masks.get('policy')}"
            )

        mask_paths = [str(Path(layer["soft_mask"]).resolve()) for layer in masks["layers"]]
        if len(mask_paths) != 3:
            raise CompositionControlError(
                f"Expected 3 generated mask paths, got {len(mask_paths)}"
            )

        prepared = _require_ok(
            self._send("PREPARE_SPECIES_LAYER_FORESTS"),
            "PREPARE_SPECIES_LAYER_FORESTS",
        )
        if prepared.get("prepared_layers_disabled") is not True:
            raise CompositionControlError(
                "Species layers were not disabled before mask binding."
            )

        binding = _require_ok(
            self._send("BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(mask_paths)),
            "BIND_SPECIES_DISTRIBUTION_MASKS",
        )
        if binding.get("verified") is not True:
            raise CompositionControlError(
                "Species distribution mask binding was not verified."
            )

        projection = _require_ok(
            self._send("CONFIGURE_SPECIES_MAP_PROJECTION"),
            "CONFIGURE_SPECIES_MAP_PROJECTION",
        )
        if projection.get("projection") != "forest_xy_tiled_75m":
            raise CompositionControlError(
                f"Unexpected projection: {projection.get('projection')}"
            )

        composition = _require_ok(
            self._send("ACTIVATE_ALL_SPECIES_LAYERS"),
            "ACTIVATE_ALL_SPECIES_LAYERS",
        )
        validate_three_layer_composition(composition)

        point_cloud = _require_ok(
            self._send("SET_ALL_FOREST_POINT_CLOUD"),
            "SET_ALL_FOREST_POINT_CLOUD",
        )
        if int(point_cloud.get("vmesh", -1)) != 3:
            raise CompositionControlError("Forest viewport is not Points Cloud.")
        if point_cloud.get("render_settings_changed") is not False:
            raise CompositionControlError("Render settings changed unexpectedly.")

        bridge_data = (
            bridge.get("data")
            if isinstance(bridge, dict) and isinstance(bridge.get("data"), dict)
            else {}
        )
        return CompositionRuntimeResult(
            bridge=bridge_data,
            masks=masks,
            prepared=prepared,
            binding=binding,
            projection=projection,
            composition=composition,
            point_cloud=point_cloud,
        )
