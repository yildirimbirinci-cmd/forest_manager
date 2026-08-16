from __future__ import annotations

from forest_manager.app import forest_pack_reference_adapters_stage5d35 as stage5d35


def _arrays():
    return [
        {"name": "coloridlist", "metadata": {"count": 2, "element_classes": ["Point3"]}},
        {"name": "cobjlist", "metadata": {"count": 1, "element_classes": ["CProxy"]}},
        {"name": "arnodelist", "metadata": {"count": 2, "element_classes": ["UndefinedClass", "line"]}},
        {"name": "matlist", "metadata": {"count": 1, "element_classes": ["Multimaterial"]}},
        {"name": "distrefnodes", "metadata": {"count": 0, "element_classes": []}},
        {"name": "problist", "metadata": {"count": 2, "element_classes": ["Float"]}},
    ]


def test_stage5d35_node_reference_allowlist_contract():
    assert stage5d35.NODE_REFERENCE_PROPERTIES == {
        "arnodelist",
        "cobjlist",
        "distpathnodes",
        "distpflownodes",
        "distrefnodes",
        "efpainode",
        "efpaspline",
        "surflist",
    }


def test_stage5d35_main_classifies_reference_arrays(monkeypatch, capsys):
    class FakeService:
        def list_forests(self):
            return ("FM_Test",)

        def capability_matrix(self, forest_name):
            return {"forest_name": forest_name, "arrays": _arrays()}

    monkeypatch.setattr(stage5d35, "ForestPackControlService", FakeService)
    assert stage5d35.main() == 0
    output = capsys.readouterr().out
    assert '"point3_array_instances": 1' in output
    assert '"node_reference_array_instances": 2' in output
    assert '"material_array_instances": 1' in output
    assert '"material_reference_write": false' in output
    assert '"array_resize": false' in output
    assert "Stage 5D.35 reference array adapter discovery passed." in output


def test_stage5d35_empty_reference_array_is_not_writable_candidate(monkeypatch, capsys):
    class FakeService:
        def list_forests(self):
            return ("FM_Test",)

        def capability_matrix(self, forest_name):
            return {
                "forest_name": forest_name,
                "arrays": [
                    {"name": "distrefnodes", "metadata": {"count": 0, "element_classes": []}},
                ],
            }

    monkeypatch.setattr(stage5d35, "ForestPackControlService", FakeService)
    assert stage5d35.main() == 0
    output = capsys.readouterr().out
    assert '"node_reference_array_instances": 0' in output


def test_stage5d35_main_reports_failure(monkeypatch, capsys):
    class BrokenService:
        def list_forests(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(stage5d35, "ForestPackControlService", BrokenService)
    assert stage5d35.main() == 2
    output = capsys.readouterr().out
    assert '"ok": false' in output
    assert '"verified": false' in output
    assert "RuntimeError: boom" in output
