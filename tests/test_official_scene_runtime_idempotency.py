from __future__ import annotations

from forest_manager.forest_control import scene_runtime as runtime_module
from forest_manager.forest_control.scene_runtime import ForestSceneRuntime
from forest_manager.forest_control.service import ForestControlError


class _FakeService:
    def __init__(self, counts):
        self.counts = list(counts)
        self.calls = 0

    def inventory(self, forest_name, *, preflight=True):
        index = min(self.calls, len(self.counts) - 1)
        count = self.counts[index]
        self.calls += 1
        return {
            "forest_name": forest_name,
            "properties": [
                {
                    "name": "cobjlist",
                    "array_metadata": {"count": count},
                }
            ],
        }


def test_official_manifest_runtime_preserves_geometry_source_count(monkeypatch):
    service = _FakeService([5, 5])
    runtime = ForestSceneRuntime(service=service)

    monkeypatch.setattr(
        runtime_module,
        "execute_plant_group_manifest",
        lambda manifest, *, service, strict_acceptance: {
            "forest_name": "FM_Forest_001",
            "verified": True,
        },
    )

    result = runtime.execute_manifest(
        {"primary_forest": "FM_Forest_001", "groups": [{"group_id": "a"}]}
    )

    assert result["verified"] is True
    assert service.calls == 2


def test_official_manifest_runtime_rejects_geometry_source_growth(monkeypatch):
    service = _FakeService([5, 6])
    runtime = ForestSceneRuntime(service=service)

    monkeypatch.setattr(
        runtime_module,
        "execute_plant_group_manifest",
        lambda manifest, *, service, strict_acceptance: {
            "forest_name": "FM_Forest_001",
            "verified": True,
        },
    )

    try:
        runtime.execute_manifest(
            {"primary_forest": "FM_Forest_001", "groups": [{"group_id": "a"}]}
        )
    except ForestControlError as exc:
        message = str(exc)
        assert "changed the Geometry source count" in message
        assert "before=5" in message
        assert "after=6" in message
    else:
        raise AssertionError("Geometry source growth was not rejected.")


def test_manifest_runtime_does_not_own_source_merge_or_delete():
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "src"
        / "forest_manager"
        / "forest_control"
        / "scene_runtime.py"
    ).read_text(encoding="utf-8")

    assert "merge_t2_asset(" not in source
    assert "add_geometry_source_by_name(" not in source
    assert "remove_geometry_source_tail(" not in source
    assert "delete_managed_forest(" not in source
