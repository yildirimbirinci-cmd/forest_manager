from __future__ import annotations

from pathlib import Path

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, project_root, send_command
from forest_manager.placement.species_mask_generator import generate_species_masks


EXPECTED_LAYER_NAMES = (
    "FM_Layer_01_foreground_mass",
    "FM_Layer_02_mid_accent",
    "FM_Layer_03_structural_shrub",
)
MASK_NAMES = (
    "FM_Mask_01_foreground_mass.png",
    "FM_Mask_02_mid_accent.png",
    "FM_Mask_03_structural_shrub.png",
)
DENSITY_METERS = 75.0
TOLERANCE = 0.001


def _require_ok(response: dict, step: str) -> dict:
    if not response.get("ok"):
        error = str(response.get("error") or "unknown bridge error")
        raise RuntimeError(f"{step} failed: {error}")
    return response.get("data") or {}


def _density_is_75(layer: dict) -> bool:
    return (
        abs(float(layer.get("density_meters_x", 0.0)) - DENSITY_METERS) <= TOLERANCE
        and abs(float(layer.get("density_meters_y", 0.0)) - DENSITY_METERS) <= TOLERANCE
    )


def _layers_are_preview_ready() -> bool:
    try:
        data = _require_ok(send_command("GET_LAYER_MAP_BINDING_CONTRACT"), "Layer contract probe")
    except Exception:
        return False

    layers = data.get("layers") or []
    if len(layers) != 3:
        return False

    for expected_name, layer in zip(EXPECTED_LAYER_NAMES, layers):
        if layer.get("forest_name") != expected_name:
            return False
        if not _density_is_75(layer):
            return False

        properties = {str(item.get("name") or "").lower(): item for item in layer.get("candidate_properties") or []}
        # The contract probe is intentionally read-only. If it exposes the
        # relevant properties, require the distribution map contract to be set.
        density_map = properties.get("densitymap")
        distmap = properties.get("distmap")
        distmode = properties.get("distmode")
        if density_map is not None and "true" not in str(density_map.get("value") or density_map.get("preview") or "").lower():
            return False
        if distmap is not None and not str(distmap.get("value") or distmap.get("preview") or "").strip():
            return False
        if distmode is not None:
            raw = str(distmode.get("value") or distmode.get("preview") or "").strip()
            if raw and raw not in {"0", "0.0"}:
                return False
    return True


def _require_three_species_baseline() -> dict:
    response = send_command("GET_SPECIES_LAYER_CONTEXT")
    data = _require_ok(response, "Three-species baseline probe")
    names = list(data.get("geometry_names") or [])
    if len(names) != 3:
        raise RuntimeError(
            "Restart bootstrap requires the saved FM_Forest_001 three-species baseline. "
            f"Current geometry count is {len(names)}. Open the Forest Manager scene that contains "
            "FM_Forest_001, or rebuild the three-species baseline once before previewing."
        )
    return data


def ensure_species_preview_ready() -> dict:
    """Repair restart-sensitive Stage 5D preview prerequisites idempotently.

    This never creates a Forest from an arbitrary user selection and never
    deletes unrelated scene nodes. It only repairs the existing managed
    three-species FM_Forest_001 baseline and its Forest Manager-owned layers.
    """
    ensure_current_bridge()

    baseline = _require_three_species_baseline()
    if _layers_are_preview_ready():
        return {"verified": True, "changed": False, "baseline": baseline}

    density_x = float(baseline.get("density_meters_x") or 0.0)
    density_y = float(baseline.get("density_meters_y") or 0.0)
    if abs(density_x - DENSITY_METERS) > TOLERANCE or abs(density_y - DENSITY_METERS) > TOLERANCE:
        _require_ok(
            send_command(f"SET_DENSITY_METERS|{DENSITY_METERS:.6f}"),
            "75.0 m density restore",
        )

    prepared = _require_ok(send_command("PREPARE_SPECIES_LAYER_FORESTS"), "Species layer preparation")
    layers = prepared.get("layers") or []
    if len(layers) != 3 or any(not _density_is_75(layer) for layer in layers):
        raise RuntimeError("Species layer preparation did not preserve the protected 75.0 m density contract.")

    mask_dir = project_root() / "resources" / "generated_masks" / "stage5d18"
    report = generate_species_masks(mask_dir)
    if not report.get("verified") or len(report.get("layers") or []) != 3:
        raise RuntimeError("Deterministic species mask generation did not verify.")

    mask_paths = [mask_dir / name for name in MASK_NAMES]
    missing = [str(path) for path in mask_paths if not path.is_file()]
    if missing:
        raise RuntimeError("Species mask generation did not create required files: " + ", ".join(missing))
    if any("|" in str(path) for path in mask_paths):
        raise RuntimeError("Species mask path contains unsupported '|' character.")

    command = "BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(str(path) for path in mask_paths)
    bound = _require_ok(send_command(command), "Species distribution mask binding")
    if not bound.get("verified") or not bound.get("density_units_preserved"):
        raise RuntimeError("Species distribution mask binding did not verify.")

    return {"verified": True, "changed": True, "baseline": baseline, "binding": bound}
