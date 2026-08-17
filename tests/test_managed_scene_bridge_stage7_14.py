from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / 'maxscripts' / 'ForestManager_Bridge.ms').read_text(encoding='utf-8')
RUNTIME = (ROOT / 'src' / 'forest_manager' / 'max_bridge' / 'runtime_bridge.py').read_text(encoding='utf-8')


def test_bridge_identity_matches_runtime():
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in RUNTIME
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-versioned-bridge-no-watcher-20260817a"' in RUNTIME
    assert r'\"bridge_version\":\"0.9.79\"' in BRIDGE
    assert r'\"bridge_build_id\":\"stage8-versioned-bridge-no-watcher-20260817a\"' in BRIDGE


def test_managed_layer_contract_exists():
    for token in (
        'FM_MANAGED',
        'fn ensureManagedSceneJson',
        'fn protectAllManagedNodes',
        'setLayerProtectionState forestsLayer true true true',
        'setLayerProtectionState referencesLayer true true false',
        'ForestManagerOwned',
    ):
        assert token in BRIDGE


def test_managed_forest_endpoints_exist():
    for token in (
        'FM_MANAGED_ENSURE',
        'FM_MANAGED_PROTECT_ALL',
        'FM_MANAGED_STATUS',
        'FM_MANAGED_CREATE_FOREST',
        'FM_MANAGED_DELETE_FOREST',
    ):
        assert token in BRIDGE
    assert 'FM_Forest_001 is the primary managed Forest and cannot be deleted' in BRIDGE
    assert 'Managed Forest names must use the FM_ prefix.' in BRIDGE


def test_runtime_preflight_enforces_managed_policy():
    assert 'send_command("FM_MANAGED_ENSURE", timeout=5.0)' in RUNTIME
    for fn in ('ensure_managed_scene', 'protect_managed_scene', 'create_managed_forest', 'delete_managed_forest', 'managed_scene_status'):
        assert f'def {fn}(' in RUNTIME
