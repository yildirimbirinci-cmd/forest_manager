from __future__ import annotations

from dataclasses import dataclass

from forest_manager.forest_control.undeclared_classification import (
    UndeclaredPropertyClassifier,
)


@dataclass(frozen=True)
class Audit:
    property_count: int = 341
    declared_count: int = 281
    undeclared_count: int = 6
    undeclared: tuple[str, ...] = (
        "reserved1",
        "threads",
        "distpflownodes",
        "geomtexid",
        "seed",
        "mystery",
    )


class Service:
    def inventory(self, forest_name: str):
        return {
            "properties": [
                {"name": "reserved1", "value_class": "Integer", "write_mode": "readonly", "writable": False},
                {"name": "threads", "value_class": "Integer", "write_mode": "scalar", "writable": True},
                {"name": "distpflownodes", "value_class": "NodeArray", "write_mode": "array", "writable": False},
                {"name": "geomtexid", "value_class": "Integer", "write_mode": "readonly", "writable": False},
                {"name": "seed", "value_class": "Integer", "write_mode": "scalar", "writable": True},
                {"name": "mystery", "value_class": "Float", "mode": "readonly", "writable": False},
            ]
        }


class AuditStub:
    def audit_forest(self, forest_name: str):
        return Audit()


def make_classifier():
    obj = UndeclaredPropertyClassifier(Service())
    obj.audit = AuditStub()
    return obj


def test_classify_name_categories():
    c = make_classifier()
    assert c.classify_name("reserved7", {}).category == "reserved"
    assert c.classify_name("threads", {}).category == "internal_runtime"
    assert c.classify_name("distpflownodes", {}).category == "legacy_plugin"
    assert c.classify_name("geomtexid", {}).category == "read_only_system"
    assert c.classify_name("seed", {}).category == "user_control_candidate"
    assert c.classify_name("unknown", {}).category == "needs_review"


def test_metadata_is_preserved():
    c = make_classifier()
    item = c.classify_name("unknown", {"value_class": "Float", "mode": "readonly", "writable": False})
    assert item.value_class == "Float"
    assert item.write_mode == "readonly"
    assert item.writable is False


def test_classify_forest_counts_and_shape():
    report = make_classifier().classify_forest("FM_Forest_001")
    assert report["property_count"] == 341
    assert report["declared_count"] == 281
    assert report["undeclared_count"] == 6
    assert report["category_counts"] == {
        "reserved": 1,
        "internal_runtime": 1,
        "legacy_plugin": 1,
        "read_only_system": 1,
        "user_control_candidate": 1,
        "needs_review": 1,
    }
    assert len(report["properties"]) == 6
