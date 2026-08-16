from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import ForestSemanticField, find_semantic_field, semantic_domains
from .service import ForestControlError, ForestPackControlService

EXPLICIT_RUNTIME_READ_ONLY = {"geomtexid", "fastopac", "renderid", "divtmap", "geomtex"}
DIRECT_SCALAR_ACCESS = {"scalar", "scalar_group", "mixed_group", "scalar_color_group"}


@dataclass(frozen=True)
class SemanticControlDescriptor:
    domain: str
    control: str
    raw_property: str
    access: str
    route: str
    writable: bool


class SemanticForestControlAPI:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def list_domains(self) -> tuple[str, ...]:
        return tuple(domain.name for domain in semantic_domains())

    def describe(self, domain: str, control: str, raw_property: str) -> SemanticControlDescriptor:
        field = find_semantic_field(domain, control)
        if raw_property not in field.raw_properties:
            raise ForestControlError(
                f"Property {raw_property} is not part of semantic control {domain}.{control}."
            )
        route = self._route_for(field, raw_property)
        writable = route in {
            "scalar_direct",
            "geometry_adapter",
            "area_adapter",
            "array_adapter",
            "reference_adapter",
            "time_typed",
            "color_typed",
        }
        if route == "scalar_direct" and not callable(getattr(self.service, "set_property", None)):
            writable = False
        return SemanticControlDescriptor(domain, control, raw_property, field.access, route, writable)

    def _route_for(self, field: ForestSemanticField, raw_property: str) -> str:
        if raw_property in EXPLICIT_RUNTIME_READ_ONLY:
            return "read_only"
        access = field.access
        if access in {"read_only", "read_only_opaque"}:
            return "read_only"
        if access in {"atomic_adapter_required", "geometry_source_record"}:
            return "geometry_adapter"
        if access in {"area_record", "area_record_adapter"}:
            return "area_adapter"
        if access in {"array_group", "synchronized_array_group"}:
            return "array_adapter"
        if access in {"node_reference_group", "material_reference_group", "bitmap_reference_group"}:
            return "reference_adapter"
        if access == "time_group":
            return "time_typed"
        if access in DIRECT_SCALAR_ACCESS:
            return "scalar_direct"
        if "color" in access:
            return "color_typed"
        return "read_only"

    def _inventory_property(self, forest_name: str, raw_property: str) -> dict[str, Any]:
        payload = self.service.inventory(forest_name)
        rows = payload.get("properties") or payload.get("inventory") or payload.get("items") or []
        if isinstance(rows, dict):
            rows = rows.values()
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("property_name")
            if str(name or "") == raw_property:
                return row
        raise ForestControlError(f"Forest property not found in inventory: {forest_name}.{raw_property}")

    def get(self, forest_name: str, domain: str, control: str, raw_property: str) -> dict[str, Any]:
        descriptor = self.describe(domain, control, raw_property)
        prop = self._inventory_property(forest_name, raw_property)
        return {
            "descriptor": {
                "domain": descriptor.domain,
                "control": descriptor.control,
                "raw_property": descriptor.raw_property,
                "access": descriptor.access,
                "route": descriptor.route,
                "writable": descriptor.writable,
            },
            "value": prop.get("value"),
            "value_class": prop.get("value_class"),
        }

    def set_scalar(
        self,
        forest_name: str,
        domain: str,
        control: str,
        raw_property: str,
        value: bool | int | float | str,
    ) -> dict[str, Any]:
        descriptor = self.describe(domain, control, raw_property)
        if descriptor.route != "scalar_direct":
            raise ForestControlError(
                f"Semantic control is not direct-scalar writable: {domain}.{control}.{raw_property} route={descriptor.route}"
            )
        setter = getattr(self.service, "set_property", None)
        if not callable(setter):
            raise ForestControlError("ForestPackControlService has no set_property runtime endpoint")
        return setter(forest_name, raw_property, value)

    def rollback(self) -> list[dict[str, Any]]:
        rollback = getattr(self.service, "rollback", None)
        if not callable(rollback):
            return []
        result = rollback()
        return list(result or [])
