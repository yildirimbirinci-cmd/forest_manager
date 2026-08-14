from __future__ import annotations
import argparse, json, sys
from forest_manager.t2_bridge import T2AssetCatalog, T2AssetCatalogError

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('query',nargs='?',default=''); parser.add_argument('--limit',type=int,default=20); args=parser.parse_args()
    catalog=T2AssetCatalog()
    try:
        records=catalog.search_max_assets(args.query,limit=args.limit,require_existing_file=True)
        payload={"diagnostics":catalog.diagnostics(),"query":args.query,"count":len(records),"assets":[{
            "id":r.id,"name":r.name,"file_path":str(r.file_path),"category":r.category,"source":r.source,"exists":r.exists
        } for r in records]}
    except T2AssetCatalogError as exc:
        print('T2 catalog error: '+str(exc)); return 1
    print('T2 MAX Assets:'); print(json.dumps(payload,indent=2,ensure_ascii=True))
    if not records:
        print('Stage 4B failed: no existing .max assets found in the T2 database or configured T2 library roots.'); return 2
    print('Stage 4B T2 catalog fallback acceptance passed.'); return 0
if __name__=='__main__': raise SystemExit(main())
