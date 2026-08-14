from __future__ import annotations

import argparse
import json
import sys

from forest_manager.t2_bridge import T2AssetCatalog, T2AssetCatalogError


def _record_json(record):
    return {
        "id": record.id,
        "name": record.name,
        "file_path": str(record.file_path),
        "folder_path": str(record.folder_path),
        "extension": record.extension,
        "category": record.category,
        "missing": record.missing,
        "exists": record.exists,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only T2 Asset Manager .max asset lookup."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Optional asset/category/folder search text.",
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    catalog = T2AssetCatalog()

    try:
        records = catalog.search_max_assets(
            args.query,
            limit=args.limit,
            require_existing_file=True,
        )
    except T2AssetCatalogError as exc:
        print("T2 catalog error: " + str(exc))
        return 1

    payload = {
        "database": str(catalog.db_path),
        "query": args.query,
        "count": len(records),
        "assets": [_record_json(record) for record in records],
    }

    print("T2 MAX Assets:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))

    if not records:
        print("Stage 4A failed: no existing .max assets matched the query.")
        return 2

    print("Stage 4A T2 catalog acceptance passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
