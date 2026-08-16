from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .candidate_review import CANDIDATE_DOMAIN_MAP
from .service import ForestPackControlService
from .undeclared_classification import USER_CONTROL_CANDIDATES

READ_ONLY_CANDIDATES = {"divtmap", "geomtex"}
SCALAR_CANDIDATES = tuple(sorted(set(USER_CONTROL_CANDIDATES) - READ_ONLY_CANDIDATES))


@dataclass(frozen=True)
class CandidateRuntimeResult:
    name: str
    domain: str
    status: str
    value: Any
    value_class: str | None
    error: str | None


class CandidateRuntimeValidator:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

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

    def validate_forest(self, forest_name: str) -> dict[str, Any]:
        inventory = self._inventory_map(forest_name)
        full_before = {name: inventory.get(name, {}).get("value") for name in USER_CONTROL_CANDIDATES}

        has_set_property = callable(getattr(self.service, "set_property", None))
        has_rollback = callable(getattr(self.service, "rollback", None))
        results: list[CandidateRuntimeResult] = []
        successful_writes = 0
        rollback_results: list[Any] = []

        for name in SCALAR_CANDIDATES:
            metadata = inventory.get(name, {})
            value = metadata.get("value")
            value_class = metadata.get("value_class")
            write_mode = metadata.get("write_mode") or metadata.get("mode")

            if has_set_property:
                try:
                    self.service.set_property(forest_name, name, value)
                    successful_writes += 1
                    status = "runtime_writable"
                    error = None
                except Exception as exc:
                    message = str(exc)
                    if (
                        "Attempt to set read-only property" in message
                        or "Property is not scalar-writable" in message
                    ):
                        status = "runtime_read_only"
                        error = message
                    else:
                        raise
            else:
                if write_mode == "scalar":
                    status = "runtime_probe_blocked"
                    error = "ForestPackControlService has no set_property runtime endpoint"
                else:
                    status = "runtime_read_only"
                    error = None

            results.append(
                CandidateRuntimeResult(
                    name=name,
                    domain=CANDIDATE_DOMAIN_MAP[name],
                    status=status,
                    value=value,
                    value_class=value_class,
                    error=error,
                )
            )

        after_write_inventory = self._inventory_map(forest_name)
        after_write = {
            name: after_write_inventory.get(name, {}).get("value") for name in USER_CONTROL_CANDIDATES
        }
        if full_before != after_write:
            raise RuntimeError(f"Candidate no-op validation changed state: {forest_name}")

        if has_rollback:
            rollback_results = self.service.rollback()

        after_rollback_inventory = self._inventory_map(forest_name)
        after_rollback = {
            name: after_rollback_inventory.get(name, {}).get("value") for name in USER_CONTROL_CANDIDATES
        }
        if full_before != after_rollback:
            raise RuntimeError(f"Candidate rollback did not restore state: {forest_name}")

        for name in sorted(READ_ONLY_CANDIDATES):
            metadata = inventory.get(name, {})
            results.append(
                CandidateRuntimeResult(
                    name=name,
                    domain=CANDIDATE_DOMAIN_MAP[name],
                    status="declared_read_only_candidate",
                    value=metadata.get("value"),
                    value_class=metadata.get("value_class"),
                    error=None,
                )
            )

        status_counts: dict[str, int] = {}
        domain_writable_counts: dict[str, int] = {}
        for item in results:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            if item.status == "runtime_writable":
                domain_writable_counts[item.domain] = domain_writable_counts.get(item.domain, 0) + 1

        return {
            "forest_name": forest_name,
            "candidate_count": len(results),
            "scalar_candidate_count": len(SCALAR_CANDIDATES),
            "declared_read_only_candidate_count": len(READ_ONLY_CANDIDATES),
            "successful_write_count": successful_writes,
            "rollback_step_count": len(rollback_results),
            "status_counts": dict(sorted(status_counts.items())),
            "domain_writable_counts": dict(sorted(domain_writable_counts.items())),
            "results": [
                {
                    "name": item.name,
                    "domain": item.domain,
                    "status": item.status,
                    "value": item.value,
                    "value_class": item.value_class,
                    "error": item.error,
                }
                for item in sorted(results, key=lambda x: x.name)
            ],
            "write_preserved": True,
            "rollback_preserved": True,
            "runtime_write_endpoint": has_set_property,
            "runtime_rollback_endpoint": has_rollback,
        }
