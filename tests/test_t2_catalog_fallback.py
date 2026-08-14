import json, sqlite3
from forest_manager.t2_bridge import T2AssetCatalog

def make_db(path):
    conn=sqlite3.connect(path); conn.execute('CREATE TABLE assets (id INTEGER PRIMARY KEY,name TEXT,file_path TEXT,folder_path TEXT,extension TEXT,category TEXT,missing INTEGER DEFAULT 0)'); conn.commit(); conn.close()

def test_falls_back_to_configured_library_when_database_has_no_max(tmp_path):
    db=tmp_path/'assets.db'; make_db(db)
    lib=tmp_path/'LIBRARY'; lib.mkdir(); asset=lib/'Oak.max'; asset.write_text('x')
    settings=tmp_path/'settings.json'; settings.write_text(json.dumps({'library_path':str(lib)}))
    records=T2AssetCatalog(db,settings).search_max_assets()
    assert len(records)==1 and records[0].file_path==asset and records[0].source=='library_scan'

def test_database_still_has_priority(tmp_path):
    db=tmp_path/'assets.db'; lib=tmp_path/'LIBRARY'; lib.mkdir(); asset=lib/'Oak.max'; asset.write_text('x')
    conn=sqlite3.connect(db); conn.execute('CREATE TABLE assets (id INTEGER PRIMARY KEY,name TEXT,file_path TEXT,folder_path TEXT,extension TEXT,category TEXT,missing INTEGER DEFAULT 0)'); conn.execute('INSERT INTO assets VALUES (1,?,?,?,?,?,0)',('Oak',str(asset),str(lib),'.max','Trees')); conn.commit(); conn.close()
    settings=tmp_path/'settings.json'; settings.write_text(json.dumps({'library_path':str(lib)}))
    records=T2AssetCatalog(db,settings).search_max_assets()
    assert records[0].source=='database'
