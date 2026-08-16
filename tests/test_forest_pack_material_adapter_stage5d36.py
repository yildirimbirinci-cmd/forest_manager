from __future__ import annotations

import importlib
import json


class FakeService:
    def list_forests(self):
        return ["FM_Forest_001", "FM_Layer_01"]

    def capability_matrix(self, forest_name):
        count = 3 if forest_name == "FM_Forest_001" else 1
        return {
            "arrays": [
                {
                    "name": "matlist",
                    "metadata": {
                        "count": count,
                        "element_classes": ["Multimaterial"],
                    },
                },
                {
                    "name": "coloridlist",
                    "metadata": {
                        "count": count,
                        "element_classes": ["Point3"],
                    },
                },
            ]
        }


def _run(monkeypatch, capsys):
    mod = importlib.import_module(
        "forest_manager.app.forest_pack_material_adapter_stage5d36"
    )
    monkeypatch.setattr(mod, "ForestPackControlService", FakeService)
    rc = mod.main()
    out = capsys.readouterr().out
    start = out.index("{")
    end = out.rindex("}") + 1
    return rc, json.loads(out[start:end]), out


def test_material_adapter_contract(monkeypatch, capsys):
    rc, data, _ = _run(monkeypatch, capsys)
    assert rc == 0
    assert data["ok"] is True
    assert data["forest_count"] == 2
    assert data["material_slot_count"] == 4
    assert data["verified"] is True


def test_matlist_is_existing_reference_transactional(monkeypatch, capsys):
    _, data, _ = _run(monkeypatch, capsys)
    rows = [item for forest in data["forests"] for item in forest["material_arrays"]]
    assert rows
    assert all(item["name"].lower() == "matlist" for item in rows)
    assert all(item["element_classes"] == ["Multimaterial"] for item in rows)
    assert all(item["write_mode"] == "existing_scene_material_reference_transactional" for item in rows)


def test_material_policy_is_conservative(monkeypatch, capsys):
    _, data, _ = _run(monkeypatch, capsys)
    policy = data["policy"]
    assert policy["matlist_existing_reference_write"] is True
    assert policy["material_creation"] is False
    assert policy["submaterial_edit"] is False
    assert policy["array_resize"] is False
    assert policy["transaction_journal"] is True
    assert policy["rollback"] is True


def test_success_message(monkeypatch, capsys):
    _, _, out = _run(monkeypatch, capsys)
    assert "Stage 5D.36 material reference adapter discovery passed." in out
