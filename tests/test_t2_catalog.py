from pathlib import Path
import sqlite3

from forest_manager.t2_bridge import T2AssetCatalog


def _make_db(tmp_path):
    db = tmp_path / "assets.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            folder_path TEXT,
            extension TEXT,
            category TEXT,
            missing INTEGER DEFAULT 0
        )
    """)
    return db, conn


def test_search_max_assets_filters_missing_and_non_max(tmp_path):
    tree = tmp_path / "Oak.max"
    tree.write_text("x", encoding="utf-8")
    image = tmp_path / "Oak.jpg"
    image.write_text("x", encoding="utf-8")
    missing = tmp_path / "Missing.max"

    db, conn = _make_db(tmp_path)
    conn.executemany(
        "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "Oak", str(tree), str(tmp_path), ".max", "Vegetation", 0),
            (2, "Oak Preview", str(image), str(tmp_path), ".jpg", "Vegetation", 0),
            (3, "Missing Oak", str(missing), str(tmp_path), ".max", "Vegetation", 1),
        ],
    )
    conn.commit()
    conn.close()

    records = T2AssetCatalog(db).search_max_assets("Oak")
    assert [record.name for record in records] == ["Oak"]
    assert records[0].file_path == tree


def test_search_matches_category_and_folder(tmp_path):
    asset_dir = tmp_path / "Vegetation" / "Trees"
    asset_dir.mkdir(parents=True)
    asset = asset_dir / "Pine.max"
    asset.write_text("x", encoding="utf-8")

    db, conn = _make_db(tmp_path)
    conn.execute(
        "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "Pine", str(asset), str(asset_dir), ".max", "Trees", 0),
    )
    conn.commit()
    conn.close()

    assert len(T2AssetCatalog(db).search_max_assets("Vegetation")) == 1
