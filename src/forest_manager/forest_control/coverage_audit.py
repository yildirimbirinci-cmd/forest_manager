from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .schema import semantic_fields
from .service import ForestPackControlService


@dataclass(frozen=True)
class CoverageSummary:
    forest_name: str
    property_count: int
    declared_count: int
    undeclared_count: int
    writable_scalar_count: int
    readonly_count: int
    array_count: int
    color_count: int
    complex_count: int
    undeclared: tuple[str, ...]


def _inventory_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("properties", "inventory", "items"):
        rows = payload.get(key)
        if rows is None:
            continue
        if isinstance(rows, dict):
            rows = list(rows.values())
        return [row for row in rows if isinstance(row, dict)]
    return []


def declared_raw_properties() -> set[str]:
    result: set[str] = set()
    for field in semantic_fields():
        raw = getattr(field, "raw_properties", None)
        if raw is None:
            raw = getattr(field, "raw_property", None)
        if raw is None:
            continue
        if isinstance(raw, str):
            result.add(raw)
        else:
            result.update(str(item) for item in raw)
    return result


def classify_inventory(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "writable_scalar": 0,
        "readonly": 0,
        "array": 0,
        "color": 0,
        "complex": 0,
    }
    for row in rows:
        value_class = str(row.get("value_class") or "")
        mode = str(row.get("write_mode") or row.get("mode") or "").lower()
        writable = row.get("writable")

        if value_class == "Color":
            counts["color"] += 1
        elif "array" in mode or row.get("array_metadata"):
            counts["array"] += 1
        elif mode in ("scalar", "scalar_writable", "scalar-writable") or writable is True:
            counts["writable_scalar"] += 1
        elif mode in ("read_only", "readonly", "read-only") or writable is False:
            counts["readonly"] += 1
        else:
            counts["complex"] += 1
    return counts


class SemanticCoverageAudit:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def audit_forest(self, forest_name: str) -> CoverageSummary:
        payload = self.service.inventory(forest_name)
        rows = _inventory_rows(payload)
        names = tuple(
            str(row.get("name") or row.get("property_name"))
            for row in rows
            if row.get("name") or row.get("property_name")
        )
        declared = declared_raw_properties()
        undeclared = tuple(sorted(name for name in names if name not in declared))
        classes = classify_inventory(rows)
        return CoverageSummary(
            forest_name=forest_name,
            property_count=len(names),
            declared_count=len(names) - len(undeclared),
            undeclared_count=len(undeclared),
            writable_scalar_count=classes["writable_scalar"],
            readonly_count=classes["readonly"],
            array_count=classes["array"],
            color_count=classes["color"],
            complex_count=classes["complex"],
            undeclared=undeclared,
        )
