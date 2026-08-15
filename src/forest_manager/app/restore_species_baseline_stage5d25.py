from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
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


STATE_SCHEMA_VERSION = 1
STATE_FILENAME = "stage5d25_recovery.json"


def _state_path() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        root = Path(local_appdata) / "ForestManager" / "state"
    else:
        root = Path.home() / ".forest_manager" / "state"
    root.mkdir(parents=True, exist_ok=True)
    return root / STATE_FILENAME


def _load_state() -> dict:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_SCHEMA_VERSION:
        return {}
    return payload


def _save_state(status: str, step: str, **extra: object) -> None:
    payload = {
        "schema_version": STATE_SCHEMA_VERSION,
        "stage": "5D.25",
        "status": status,
        "last_step": step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(extra)
    path = _state_path()
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _clear_state() -> None:
    path = _state_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


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
        previous_state = _load_state()
        if previous_state and previous_state.get("status") != "completed":
            print("Stage 5D.25 recovery state detected; rebuilding the verified baseline idempotently from the saved checkpoint.")
        _save_state("running", "bridge_preflight")
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

        _save_state("running", "selection_verified", spline=selection.get("node_name"))
        assets = _resolve_assets()
        _save_state("running", "assets_resolved", spline=selection.get("node_name"), assets=[str(path) for path in assets])

        reset = _require_ok(
            send_command("RESET_MANAGED_FOREST_FROM_SELECTION"),
            "Managed Forest reset",
        )

        _save_state("running", "managed_reset_complete", spline=selection.get("node_name"))

        first = _require_ok(
            send_command("MERGE_T2_ASSET|" + _encode_path(assets[0])),
            "Lavandula merge",
        )
        _save_state("running", "lavandula_merge_complete", source=first.get("source_name"))
        second = _require_ok(
            send_command("APPEND_T2_ASSET|" + _encode_path(assets[1]) + "|28.57145"),
            "Butomus append",
        )
        _save_state("running", "butomus_append_complete", source=second.get("source_name"))
        third = _require_ok(
            send_command("APPEND_T2_ASSET|" + _encode_path(assets[2]) + "|28.57145"),
            "Berberis append",
        )

        _save_state("running", "berberis_append_complete", source=third.get("source_name"))
        probabilities = _require_ok(
            send_command("SET_GEOMETRY_PROBABILITIES|42.8571,28.57145,28.57145"),
            "Species probability restore",
        )
        _save_state("running", "probabilities_restored")
        density = _require_ok(
            send_command("SET_DENSITY_METERS|75.0"),
            "75.0 m density restore",
        )

        _save_state("running", "density_restored", density_meters=DENSITY_METERS)

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

        density_x = float(density.get("density_meters_x") or density.get("meters_x") or 0.0)
        density_y = float(density.get("density_meters_y") or density.get("meters_y") or 0.0)
        if abs(density_x - DENSITY_METERS) > 0.001:
            raise RuntimeError(
                "Recovered Density Units X is not 75.0 m. "
                + "Actual=" + str(density_x) + ", response=" + repr(density)
            )
        if abs(density_y - DENSITY_METERS) > 0.001:
            raise RuntimeError(
                "Recovered Density Units Y is not 75.0 m. "
                + "Actual=" + str(density_y) + ", response=" + repr(density)
            )

        _save_state("running", "baseline_verified")

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

        _save_state("running", "layers_prepared", layer_count=len(layer_rows))

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

        _save_state("running", "masks_generated", mask_dir=str(mask_dir))

        binding = _require_ok(
            send_command("BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(str(path) for path in mask_paths)),
            "Species mask binding",
        )
        if not binding.get("verified") or not binding.get("density_units_preserved"):
            raise RuntimeError("Species distribution mask binding verification failed.")

        _save_state("running", "masks_bound")

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
        _save_state("completed", "verified", report=report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("Stage 5D.25 verified Lavandula / Butomus / Berberis baseline recovery passed.")
        return 0
    except Exception as exc:
        try:
            current = _load_state()
            _save_state(
                "interrupted",
                str(current.get("last_step") or "unknown"),
                error=type(exc).__name__ + ": " + str(exc),
            )
        except Exception:
            pass
        print("Stage 5D.25 error: " + type(exc).__name__ + ": " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
