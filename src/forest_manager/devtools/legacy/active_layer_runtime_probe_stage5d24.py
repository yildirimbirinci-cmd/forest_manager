from __future__ import annotations

import json

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command

TARGET = "FM_Layer_01_foreground_mass"


def _target_layer(data: dict) -> dict:
    for layer in data.get("layers") or []:
        if layer.get("forest_name") == TARGET:
            return layer
    return {}


def _probe(command: str) -> dict:
    response = send_command(command)
    if not response.get("ok"):
        error = str(response.get("error") or "")
        blocked = "must remain disabled" in error.lower()
        return {
            "ok": False,
            "command": command,
            "blocked_by_prepared_layer_contract": blocked,
            "error": error,
        }

    data = response.get("data") or {}
    return {
        "ok": True,
        "command": command,
        "target": _target_layer(data),
        "spline": data.get("spline"),
        "layer_count": data.get("layer_count"),
        "raw_keys": sorted(data.keys()),
    }


def main() -> None:
    bridge = ensure_current_bridge()
    identity = bridge.get("data") or {}

    commands = [
        "GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT",
        "GET_LAYER_MAP_BINDING_CONTRACT",
        "GET_SPECIES_MASK_SPATIAL_ALIGNMENT_CONTRACT",
        "GET_SPECIES_MASK_DEEP_UVGEN_CONTRACT",
    ]

    contracts = {command: _probe(command) for command in commands}

    report = {
        "bridge": {
            "max_year": identity.get("max_year"),
            "bridge_version": identity.get("bridge_version"),
            "bridge_build_id": identity.get("bridge_build_id"),
        },
        "target_forest": TARGET,
        "note": (
            "Deep/prepared-layer contracts may reject the active foreground layer by design; "
            "those failures are reported without aborting the probe."
        ),
        "contracts": contracts,
    }

    print("Forest Manager Stage 5D.24 Active Layer Runtime Probe v2:")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
