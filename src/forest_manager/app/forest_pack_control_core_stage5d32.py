from __future__ import annotations
import json
from forest_manager.forest_control import ForestControlService

def main() -> int:
    print("Forest Manager Stage 5D.32 Forest Pack Control Core:")
    snapshots=ForestControlService().discover()
    if len(snapshots)!=4: raise RuntimeError(f"Expected four Forest objects, got {len(snapshots)}.")
    rows=[]
    for snapshot in snapshots:
        if snapshot.property_count<=0: raise RuntimeError(f"No Forest properties discovered on {snapshot.forest_name}.")
        if sum(snapshot.write_mode_counts.values())!=snapshot.property_count: raise RuntimeError(f"Write-mode classification mismatch on {snapshot.forest_name}.")
        rows.append({"forest_name":snapshot.forest_name,"property_count":snapshot.property_count,"write_mode_counts":snapshot.write_mode_counts,"array_count":len(snapshot.arrays)})
    result={"ok":True,"forest_count":len(snapshots),"forests":rows,"policy":{"read_only_discovery":True,"runtime_property_introspection":True,"write_mode_classification":True,"typed_array_metadata":True,"scene_write":False},"verified":True}
    print(json.dumps(result,indent=2,ensure_ascii=False)); print("Stage 5D.32 Forest Pack control core passed."); return 0

if __name__ == "__main__": raise SystemExit(main())
