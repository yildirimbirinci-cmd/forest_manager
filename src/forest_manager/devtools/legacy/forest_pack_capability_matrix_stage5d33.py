from __future__ import annotations
import json
from forest_manager.forest_control import ForestControlService, aggregate_capability_matrix

def main() -> int:
    print("Forest Manager Stage 5D.33 Forest Pack Capability Matrix:")
    matrix=aggregate_capability_matrix(ForestControlService().discover())
    if matrix["forest_count"]!=4: raise RuntimeError("Stage 5D.33 requires exactly four Forest objects.")
    counts={row["property_count"] for row in matrix["forests"]}
    if len(counts)!=1: raise RuntimeError("Forest property counts are inconsistent across the four Forest objects.")
    property_count=next(iter(counts))
    if property_count<300: raise RuntimeError(f"Forest Pack capability discovery is unexpectedly incomplete: {property_count} properties.")
    for row in matrix["forests"]:
        if sum(row["write_mode_counts"].values())!=row["property_count"]: raise RuntimeError("Write-mode counts do not cover every discovered Forest property.")
    matrix["ok"]=True; matrix["verified"]=True
    print(json.dumps(matrix,indent=2,ensure_ascii=False)); print("Stage 5D.33 Forest Pack capability matrix passed."); return 0

if __name__ == "__main__": raise SystemExit(main())
