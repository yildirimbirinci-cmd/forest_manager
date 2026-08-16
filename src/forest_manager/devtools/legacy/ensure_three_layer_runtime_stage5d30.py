from __future__ import annotations
import json
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command

def _require_ok(command: str) -> dict:
    response=send_command(command)
    if not response.get("ok"):
        raise RuntimeError(f"{command} failed: {response.get('error') or response}")
    data=response.get("data") or {}
    if not data.get("verified"):
        raise RuntimeError(f"{command} did not verify.")
    return data

def main() -> int:
    print("Forest Manager Stage 5D.30 Ensure Three-Layer Runtime:")
    ensure_current_bridge()
    rollback=_require_ok("ROLLBACK_SPECIES_LAYER_PREVIEW")
    projection=_require_ok("CONFIGURE_SPECIES_MAP_PROJECTION")
    composition=_require_ok("ACTIVATE_ALL_SPECIES_LAYERS")
    viewport=_require_ok("SET_ALL_FOREST_POINT_CLOUD")
    layers=composition.get("layers") or []
    if len(layers)!=3: raise RuntimeError("Exactly three species layers are required.")
    for layer in layers:
        if not layer.get("active"): raise RuntimeError("All species layers must be active.")
        if abs(float(layer.get("density_meters_x",0.0))-75.0)>0.001: raise RuntimeError("Density Units X changed from 75.0 m.")
        if abs(float(layer.get("density_meters_y",0.0))-75.0)>0.001: raise RuntimeError("Density Units Y changed from 75.0 m.")
    result={"ok":True,"rollback_verified":bool(rollback.get("verified")),"projection":projection.get("projection"),"legacy_forest_disabled":bool(composition.get("legacy_forest_disabled")),"all_species_layers_active":bool(composition.get("all_species_layers_active")),"layer_count":len(layers),"point_cloud_vmesh":int(viewport.get("vmesh",-1)),"render_settings_changed":viewport.get("render_settings_changed"),"verified":True}
    print(json.dumps(result,indent=2,ensure_ascii=False))
    print("Stage 5D.30 three-layer runtime is ready.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
