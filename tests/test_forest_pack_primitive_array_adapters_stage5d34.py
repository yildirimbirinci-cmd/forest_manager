from __future__ import annotations

from forest_manager.forest_control.service import (
    ForestControlError,
    ForestPackControlService,
    ForestSnapshot,
)
from forest_manager.app import forest_pack_primitive_array_adapters_stage5d34 as stage5d34


def _snapshot(name: str = "FM_Test") -> ForestSnapshot:
    return ForestSnapshot(
        forest_name=name,
        property_count=2,
        write_mode_counts={"read_only": 1, "scalar": 1, "color": 0},
        properties=(),
        arrays=(
            {
                "name": "problist",
                "metadata": {
                    "count": 2,
                    "element_classes": ["Float"],
                },
            },
            {
                "name": "cobjlist",
                "metadata": {
                    "count": 1,
                    "element_classes": ["CProxy"],
                },
            },
            {
                "name": "distpathnodes",
                "metadata": {
                    "count": 0,
                    "element_classes": [],
                },
            },
        ),
    )


def test_stage5d34_primitive_class_contract():
    assert stage5d34.PRIMITIVE_CLASSES == {"BooleanClass", "Float", "Integer", "String"}


def test_forest_pack_service_facade_uses_discovery(monkeypatch):
    service = ForestPackControlService()
    snapshot = _snapshot()
    monkeypatch.setattr(service, "discover", lambda **kwargs: (snapshot,))

    assert service.list_forests() == ("FM_Test",)
    matrix = service.capability_matrix("FM_Test")
    assert matrix["forest_name"] == "FM_Test"
    assert matrix["arrays"][0]["name"] == "problist"


def test_forest_pack_service_facade_rejects_unknown_forest(monkeypatch):
    service = ForestPackControlService()
    monkeypatch.setattr(service, "discover", lambda **kwargs: (_snapshot(),))

    try:
        service.capability_matrix("Missing")
    except ForestControlError as exc:
        assert "Missing" in str(exc)
    else:
        raise AssertionError("Expected ForestControlError")


def test_stage5d34_main_classifies_primitive_and_blocked_arrays(monkeypatch, capsys):
    class FakeService:
        def list_forests(self):
            return ("FM_Test",)

        def capability_matrix(self, forest_name):
            snapshot = _snapshot(forest_name)
            return {
                "forest_name": snapshot.forest_name,
                "arrays": list(snapshot.arrays),
            }

    monkeypatch.setattr(stage5d34, "ForestPackControlService", FakeService)
    assert stage5d34.main() == 0
    output = capsys.readouterr().out
    assert '"primitive_array_instances": 1' in output
    assert '"blocked_array_instances": 2' in output
    assert '"write_mode": "indexed_primitive_transactional"' in output
    assert "Stage 5D.34 primitive array adapter discovery passed." in output
