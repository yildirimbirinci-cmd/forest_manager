from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .areas import AreaRecordsAdapter
from .geometry import GeometrySourcesAdapter
from .semantic_api import SemanticForestControlAPI
from .semantic_transaction import SemanticScalarChange, SemanticTransactionManager, SemanticTransactionResult
from .service import ForestPackControlService


@dataclass(frozen=True)
class ForestControlSnapshot:
    forest_name: str
    semantic_values: dict[str, Any]


class ForestControlEngine:
    """Unified Stage 5D.55 facade over the verified Forest control layers."""

    def __init__(
        self,
        service: ForestPackControlService | None = None,
        semantic: SemanticForestControlAPI | None = None,
        transactions: SemanticTransactionManager | None = None,
        geometry: GeometrySourcesAdapter | None = None,
        areas: AreaRecordsAdapter | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.semantic = semantic or SemanticForestControlAPI(self.service)
        self.transactions = transactions or SemanticTransactionManager(self.service, self.semantic)
        self.geometry = geometry or GeometrySourcesAdapter(self.service)
        self.areas = areas or AreaRecordsAdapter(self.service)

    def list_forests(self) -> tuple[str, ...]:
        return tuple(self.service.list_forests())

    def list_domains(self) -> tuple[str, ...]:
        return tuple(self.semantic.list_domains())

    def snapshot(
        self,
        forest_name: str,
        controls: Iterable[tuple[str, str, str]],
    ) -> ForestControlSnapshot:
        values: dict[str, Any] = {}
        for domain, control, raw_property in controls:
            data = self.semantic.get(forest_name, domain, control, raw_property)
            values[raw_property] = data.get("value")
        return ForestControlSnapshot(forest_name=forest_name, semantic_values=values)

    def apply_scalar_transaction(
        self,
        forest_name: str,
        changes: Iterable[SemanticScalarChange],
    ) -> SemanticTransactionResult:
        return self.transactions.apply_and_rollback(forest_name, changes)

    def geometry_source(self, forest_name: str, index: int):
        return self.geometry.read_record(forest_name, index)

    def area_record(self, forest_name: str, index: int):
        return self.areas.read_record(forest_name, index)

    def capability_summary(self, forest_name: str) -> dict[str, Any]:
        inventory = self.service.inventory(forest_name)
        rows = inventory.get("properties") or inventory.get("inventory") or inventory.get("items") or []
        if isinstance(rows, dict):
            rows = list(rows.values())
        rows = [row for row in rows if isinstance(row, dict)]
        by_name = {
            str(row.get("name") or row.get("property_name") or ""): row
            for row in rows
        }

        def array_count(name: str) -> int:
            metadata = (by_name.get(name) or {}).get("array_metadata")
            if not isinstance(metadata, dict):
                return 0
            try:
                return int(metadata.get("count") or 0)
            except (TypeError, ValueError):
                return 0

        return {
            "forest_name": forest_name,
            "domain_count": len(self.list_domains()),
            "raw_property_count": int(inventory.get("property_count") or len(rows)),
            "geometry_source_count": array_count("cobjlist"),
            "area_record_count": array_count("aridlist"),
            "runtime_write_endpoint": callable(getattr(self.service, "set_property", None)),
            "runtime_rollback_endpoint": callable(getattr(self.service, "rollback", None)),
        }
