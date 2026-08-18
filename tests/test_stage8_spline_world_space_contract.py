from __future__ import annotations

from pathlib import Path
import importlib.util


def _load_updater():
    path = Path(__file__).resolve().parents[1] / "tools" / "apply_stage8_spline_world_space_update.py"
    spec = importlib.util.spec_from_file_location("stage8_world_update", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_updater_requires_exact_old_bridge_identity():
    module = _load_updater()
    source = (
        '        ",\\"bridge_version\\":\\"0.9.79\\"" +\n'
        '        ",\\"bridge_build_id\\":\\"stage8-world-map-projection-20260818q\\"}"\n'
        '    fn getSelectionData obj =\n'
        '        if matchPattern command pattern:"MERGE_T2_ASSET|*" ignoreCase:true then\n'
    )
    updated = module.update_maxscript(source)

    assert r'\"bridge_version\":\"0.9.80\"' in updated
    assert r'\"bridge_build_id\":\"stage8-spline-world-space-read-20260818a\"' in updated
    assert "getSelectionSplineWorldSpaceJson" in updated
    assert "GET_SELECTION_SPLINE_WORLD_SPACE" in updated
    assert "in coordsys world" in updated
    assert "getKnotPoint" in updated
    assert "interpCurve3D" in updated


def test_updater_rejects_unknown_bridge_baseline():
    module = _load_updater()
    try:
        module.update_maxscript(r'\"bridge_version\":\"9.9.9\"')
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unknown bridge baseline must be rejected.")


def test_runtime_bridge_identity_update_is_exact():
    module = _load_updater()
    source = (
        'EXPECTED_BRIDGE_VERSION = "0.9.79"\n'
        'EXPECTED_BRIDGE_BUILD_ID = "stage8-world-map-projection-20260818q"\n'
        'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_79.ms"\n'
    )
    updated = module.update_runtime_bridge(source)

    assert 'EXPECTED_BRIDGE_VERSION = "0.9.80"' in updated
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-spline-world-space-read-20260818a"' in updated
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_80.ms"' in updated
