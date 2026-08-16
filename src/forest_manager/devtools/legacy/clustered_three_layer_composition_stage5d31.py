from __future__ import annotations
import argparse,json
from pathlib import Path
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command
from forest_manager.placement.species_mask_generator import generate_species_cluster_masks

def _require_ok(command: str) -> dict:
    response=send_command(command)
    if not response.get("ok"): raise RuntimeError(f"{command} failed: {response.get('error') or response}")
    data=response.get("data") or {}
    if not data.get("verified"): raise RuntimeError(f"{command} did not verify.")
    return data

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output-dir",default="resources/generated_masks/stage5d31"); args=parser.parse_args()
    print("Forest Manager Stage 5D.31 Clustered Three-Layer Composition:")
    ensure_current_bridge()
    _require_ok("ROLLBACK_SPECIES_LAYER_PREVIEW")
    report=generate_species_cluster_masks(Path(args.output_dir).resolve())
    if not report.get("verified") or report.get("policy")!="deterministic_species_cluster_masks_v2": raise RuntimeError("Clustered species masks did not verify.")
    layers=report.get("layers") or []
    if len(layers)!=3: raise RuntimeError("Exactly three clustered species masks are required.")
    paths=[str(Path(layer["soft_mask"]).resolve()) for layer in layers]
    binding=_require_ok("BIND_SPECIES_DISTRIBUTION_MASKS|"+"|".join(paths))
    projection=_require_ok("CONFIGURE_SPECIES_MAP_PROJECTION")
    composition=_require_ok("ACTIVATE_ALL_SPECIES_LAYERS")
    viewport=_require_ok("SET_ALL_FOREST_POINT_CLOUD")
    active=composition.get("layers") or []
    if len(active)!=3 or any(not x.get("active") for x in active): raise RuntimeError("Three active species layers are required.")
    if any(abs(float(x.get("density_meters_x",0.0))-75.0)>0.001 for x in active): raise RuntimeError("Density Units X changed from 75.0 m.")
    if any(abs(float(x.get("density_meters_y",0.0))-75.0)>0.001 for x in active): raise RuntimeError("Density Units Y changed from 75.0 m.")
    result={"ok":True,"mask_policy":report["policy"],"mask_verified":True,"binding_verified":bool(binding.get("verified")),"projection":projection.get("projection"),"legacy_forest_disabled":bool(composition.get("legacy_forest_disabled")),"all_species_layers_active":bool(composition.get("all_species_layers_active")),"layer_count":len(active),"point_cloud_vmesh":int(viewport.get("vmesh",-1)),"render_settings_changed":viewport.get("render_settings_changed"),"command_order":["ROLLBACK_SPECIES_LAYER_PREVIEW","BIND_SPECIES_DISTRIBUTION_MASKS","CONFIGURE_SPECIES_MAP_PROJECTION","ACTIVATE_ALL_SPECIES_LAYERS","SET_ALL_FOREST_POINT_CLOUD"],"verified":True}
    print(json.dumps(result,indent=2,ensure_ascii=False)); print("Stage 5D.31 clustered three-layer composition passed."); return 0

if __name__ == "__main__": raise SystemExit(main())
