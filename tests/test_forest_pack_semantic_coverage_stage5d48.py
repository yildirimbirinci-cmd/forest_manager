from forest_manager.forest_control.coverage_audit import (
    SemanticCoverageAudit,
    _inventory_rows,
    classify_inventory,
)


def test_inventory_rows_accepts_supported_payload_shapes():
    rows = [{"name": "a"}, {"name": "b"}]
    assert _inventory_rows({"properties": rows}) == rows
    assert _inventory_rows({"inventory": {"a": rows[0], "b": rows[1]}}) == rows
    assert _inventory_rows({"items": rows}) == rows


def test_classify_inventory_matches_runtime_metadata_contract():
    rows = [
        {"name": "a", "write_mode": "scalar"},
        {"name": "b", "write_mode": "read_only"},
        {"name": "c", "write_mode": "primitive_array"},
        {"name": "d", "value_class": "Color"},
        {"name": "e", "value_class": "ReferenceTarget"},
    ]
    assert classify_inventory(rows) == {
        "writable_scalar": 1,
        "readonly": 1,
        "array": 1,
        "color": 1,
        "complex": 1,
    }


def test_audit_forest_counts_declared_and_undeclared(monkeypatch):
    class Service:
        def inventory(self, forest_name):
            return {
                "properties": [
                    {"name": "known", "write_mode": "scalar"},
                    {"name": "unknown", "write_mode": "read_only"},
                ]
            }

    monkeypatch.setattr(
        "forest_manager.forest_control.coverage_audit.declared_raw_properties",
        lambda: {"known"},
    )
    summary = SemanticCoverageAudit(Service()).audit_forest("Forest")
    assert summary.property_count == 2
    assert summary.declared_count == 1
    assert summary.undeclared_count == 1
    assert summary.undeclared == ("unknown",)
    assert summary.writable_scalar_count == 1
    assert summary.readonly_count == 1
