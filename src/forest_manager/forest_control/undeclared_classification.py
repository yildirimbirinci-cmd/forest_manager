from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coverage_audit import SemanticCoverageAudit
from .service import ForestPackControlService

INTERNAL_RUNTIME_FIELDS = {
    "Collision", "Disabled", "autothreads", "dispflags", "manualupdate", "savedversion", "threads",
}

LEGACY_PLUGIN_FIELDS = {
    "consgeom", "consmat", "custshadow", "distpflowallevents", "distpfloweventslist",
    "distpflowgetrot", "distpflowgetscale", "distpflownodes", "hshadow", "hsoffset",
    "hsplanes", "hsscale", "irradiance", "light", "selfillum", "selfshadow",
    "tracedepth", "usefakeshadows", "vshadow",
}

USER_CONTROL_CANDIDATES = {
    "camdensact", "camdensear", "camdensfar", "camscaact", "collheight", "collpreview",
    "divers", "divmapchan", "divmapnoise", "divtmap", "drotation", "fastopac", "geomtex",
    "hidecustom", "iconSize", "maxdensity", "mirror", "mode", "offset_X", "offset_Y",
    "opaclevel", "pf_efonlyrender", "radius", "randstacked", "renderid", "scalelope",
    "sdgizmo", "seed", "seedtype", "sepsubsplines", "spdensact", "spdensexc", "spdensinc",
    "spscalact", "spscalexc", "spscalinc", "spscalz", "ssitself", "threshold",
}

READ_ONLY_SYSTEM_FIELDS = {"geomtexid"}


@dataclass(frozen=True)
class ClassifiedProperty:
    name: str
    category: str
    reason: str
    value_class: str | None
    write_mode: str | None
    writable: bool | None


class UndeclaredPropertyClassifier:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()
        self.audit = SemanticCoverageAudit(self.service)

    def _inventory_map(self, forest_name: str) -> dict[str, dict[str, Any]]:
        payload = self.service.inventory(forest_name)
        rows = payload.get("properties") or payload.get("inventory") or payload.get("items") or []
        if isinstance(rows, dict):
            rows = rows.values()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("property_name")
            if name:
                result[str(name)] = row
        return result

    def classify_name(self, name: str, metadata: dict[str, Any]) -> ClassifiedProperty:
        lowered = name.lower()
        if lowered.startswith("reserved"):
            category = "reserved"
            reason = "Forest Pack reserved/internal slot"
        elif name in INTERNAL_RUNTIME_FIELDS:
            category = "internal_runtime"
            reason = "runtime, versioning, threading or update-control field"
        elif name in LEGACY_PLUGIN_FIELDS:
            category = "legacy_plugin"
            reason = "legacy/specialized compatibility, particle-flow or lighting control"
        elif name in READ_ONLY_SYSTEM_FIELDS:
            category = "read_only_system"
            reason = "runtime-verified read-only/system-owned field"
        elif name in USER_CONTROL_CANDIDATES:
            category = "user_control_candidate"
            reason = "appears to represent a meaningful Forest user-facing control"
        else:
            category = "needs_review"
            reason = "not safely classifiable from current semantic contract alone"

        return ClassifiedProperty(
            name=name,
            category=category,
            reason=reason,
            value_class=metadata.get("value_class"),
            write_mode=metadata.get("write_mode") or metadata.get("mode"),
            writable=metadata.get("writable"),
        )

    def classify_forest(self, forest_name: str) -> dict[str, Any]:
        audit = self.audit.audit_forest(forest_name)
        inventory = self._inventory_map(forest_name)
        classified = [
            self.classify_name(name, inventory.get(name, {}))
            for name in audit.undeclared
        ]
        counts: dict[str, int] = {}
        for item in classified:
            counts[item.category] = counts.get(item.category, 0) + 1
        return {
            "forest_name": forest_name,
            "property_count": audit.property_count,
            "declared_count": audit.declared_count,
            "undeclared_count": audit.undeclared_count,
            "category_counts": counts,
            "properties": [
                {
                    "name": item.name,
                    "category": item.category,
                    "reason": item.reason,
                    "value_class": item.value_class,
                    "write_mode": item.write_mode,
                    "writable": item.writable,
                }
                for item in classified
            ],
        }
