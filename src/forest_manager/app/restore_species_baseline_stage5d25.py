from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, project_root, send_command
from forest_manager.placement.species_mask_generator import generate_species_masks
from forest_manager.t2_bridge import T2AssetCatalog


SPECIES = (
    ("Lavandula angustifolia 'Hidcote' (Lavender)", "foreground_mass"),
    ("Butomus umbellatus (Flowering rush )", "mid_accent"),
    ("Bush_Berberis", "structural_shrub"),
)

PROBABILITIES = (42.8571, 28.57145, 28.57145)
DENSITY_METERS = 75.0
MASK_NAMES = (
    "FM_Mask_01_foreground_mass.png",
    "FM_Mask_02_mid_accent.png",
    "FM_Mask_03_structural_shrub.png",
)


def _require_ok(response: dict, label: str) -> dict:
    if not response.get("ok"):
        raise RuntimeError(label + " failed: " + str(response.get("error") or response))
    return response.get("data") or {}


def _encode_path(path: Path) -> str:
    return base64.b64encode(str(path).encode("utf-8")).decode("ascii")


def _resolve_assets() -> list[Path]:
    catalog = T2AssetCatalog()
    resolved: list[Path] = []

    for expected_name, _role in SPECIES:
        matches = catalog.search_max_assets(expected_name, limit=20, require_existing_file=True)
        exact = [item for item in matches if item.name.strip().casefold() == expected_name.casefold()]
        if len(exact) != 1:
            raise RuntimeError(
                "Expected exactly one real T2 asset for " + expected_name + ", found " + str(len(exact))
            )
        path = Path(exact[0].file_path)
        if not path.is_file() or path.suffix.casefold() != ".max":
            raise RuntimeError("Resolved T2 asset is not an existing .max file: " + str(path))
        resolved.append(path)

    return resolved


def main() -> int:
    print("Forest Manager Stage 5D.25 Verified Species Baseline Recovery:")
    try:
        ensure_current_bridge()

        selection = _require_ok(send_command("GET_SELECTION_SPLINE_AREA"), "Spline selection preflight")
        if not selection.get("verified"):
            raise RuntimeError("Selected spline area preflight was not verified.")
        if int(selection.get("spline_count") or 0) != 1:
            raise RuntimeError("Select exactly one closed spline before running Stage 5D.25.")
        if not bool(selection.get("all_splines_closed")):
            raise RuntimeError("Select exactly one closed spline before running Stage 5D.25.")
        if not str(selection.get("node_name") or "").strip():
            raise RuntimeError("Selected spline node name is unavailable.")

        assets = _resolve_assets()

        reset = _require_ok(
            send_command("RESET_MANAGED_FOREST_FROM_SELECTION"),
            "Managed Forest reset",
        )

        first = _require_ok(
            send_command("MERGE_T2_ASSET|" + _encode_path(assets[0])),
            "Lavandula merge",
        )
        second = _require_ok(
            send_command("APPEND_T2_ASSET|" + _encode_path(assets[1]) + "|28.57145"),
            "Butomus append",
        )
        third = _require_ok(
            send_command("APPEND_T2_ASSET|" + _encode_path(assets[2]) + "|28.57145"),
            "Berberis append",
        )

        probabilities = _require_ok(
            send_command("SET_GEOMETRY_PROBABILITIES|42.8571,28.57145,28.57145"),
            "Species probability restore",
        )
        density = _require_ok(
            send_command("SET_DENSITY_METERS|75.0"),
            "75.0 m density restore",
        )

        geometry_names = list(probabilities.get("geometry_names") or [])
        expected_names = [item[0] for item in SPECIES]
        if geometry_names != expected_names:
            raise RuntimeError(
                "Recovered Forest geometry order is wrong. Expected "
                + repr(expected_names)
                + ", got "
                + repr(geometry_names)
            )

        recovered_probabilities = [float(value) for value in probabilities.get("probabilities") or []]
        if len(recovered_probabilities) != 3:
            raise RuntimeError("Recovered probability count is not 3.")
        for actual, expected in zip(recovered_probabilities, PROBABILITIES):
            if abs(actual - expected) > 0.01:
                raise RuntimeError("Recovered species probabilities do not match the verified baseline.")

        if abs(float(density.get("meters_x") or density.get("density_meters_x") or 0.0) - DENSITY_METERS) > 0.001:
            raise RuntimeError("Recovered Density Units X is not 75.0 m.")
        if abs(float(density.get("meters_y") or density.get("density_meters_y") or 0.0) - DENSITY_METERS) > 0.001:
            raise RuntimeError("Recovered Density Units Y is not 75.0 m.")

        layers = _require_ok(
            send_command("PREPARE_SPECIES_LAYER_FORESTS"),
            "Species layer preparation",
        )
        layer_rows = list(layers.get("layers") or [])
        if len(layer_rows) != 3:
            raise RuntimeError("Species layer preparation did not create exactly three layers.")

        for index, (row, expected) in enumerate(zip(layer_rows, SPECIES), start=1):
            expected_name, _role = expected
            if str(row.get("source_name") or "") != expected_name:
                raise RuntimeError("Layer " + str(index) + " source mismatch: " + str(row.get("source_name")))
            if abs(float(row.get("density_meters_x") or 0.0) - DENSITY_METERS) > 0.001:
                raise RuntimeError("Layer " + str(index) + " Density Units X is not 75.0 m.")
            if abs(float(row.get("density_meters_y") or 0.0) - DENSITY_METERS) > 0.001:
                raise RuntimeError("Layer " + str(index) + " Density Units Y is not 75.0 m.")

        mask_dir = project_root() / "resources" / "generated_masks" / "stage5d18"
        mask_report = generate_species_masks(mask_dir)
        if not mask_report.get("verified") or not mask_report.get("exclusive_primary_ownership"):
            raise RuntimeError("Species mask generation verification failed.")

        mask_paths = [mask_dir / name for name in MASK_NAMES]
        missing = [str(path) for path in mask_paths if not path.is_file()]
        if missing:
            raise RuntimeError("Generated species masks are missing: " + ", ".join(missing))
        if any("|" in str(path) for path in mask_paths):
            raise RuntimeError("Generated mask path contains unsupported '|' character.")

        binding = _require_ok(
            send_command("BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(str(path) for path in mask_paths)),
            "Species mask binding",
        )
        if not binding.get("verified") or not binding.get("density_units_preserved"):
            raise RuntimeError("Species distribution mask binding verification failed.")

        report = {
            "ok": True,
            "spline": selection.get("node_name") or reset.get("area_node"),
            "forest_name": reset.get("forest_name", "FM_Forest_001"),
            "species": [
                {
                    "index": index + 1,
                    "name": name,
                    "role": role,
                    "asset_path": str(assets[index]),
                    "probability": PROBABILITIES[index],
                }
                for index, (name, role) in enumerate(SPECIES)
            ],
            "density_meters_x": DENSITY_METERS,
            "density_meters_y": DENSITY_METERS,
            "layer_count": len(layer_rows),
            "masks_bound": True,
            "legacy_forest_active": bool(binding.get("legacy_forest_active")),
            "prepared_layers_disabled": bool(binding.get("prepared_layers_disabled")),
            "verified": True,
            "next_step": "Run Stage 5D.23 visual preview before any UV clamp experiment.",
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("Stage 5D.25 verified Lavandula / Butomus / Berberis baseline recovery passed.")
        return 0
    except Exception as exc:
        print("Stage 5D.25 error: " + type(exc).__name__ + ": " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
