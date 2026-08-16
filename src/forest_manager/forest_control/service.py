from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


class ForestControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForestProperty:
    name: str
    value_class: str
    write_mode: str
    readable: bool
    value: Any = None
    array_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ForestSnapshot:
    forest_name: str
    property_count: int
    write_mode_counts: dict[str, int]
    properties: tuple[ForestProperty, ...]
    arrays: tuple[dict[str, Any], ...]


def _require_ok(response: dict[str, Any], command: str) -> dict[str, Any]:
    if not response.get("ok"):
        raise ForestControlError(f"{command} failed: {response.get('error') or response}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise ForestControlError(f"{command} returned an invalid data payload.")
    return data


def _parse_forest_snapshot(raw: dict[str, Any]) -> ForestSnapshot:
    properties = []
    for item in raw.get("properties") or []:
        if not isinstance(item, dict):
            continue
        properties.append(
            ForestProperty(
                str(item.get("name") or ""),
                str(item.get("value_class") or ""),
                str(item.get("write_mode") or "read_only"),
                bool(item.get("readable")),
                item.get("value"),
                item.get("array_metadata") if isinstance(item.get("array_metadata"), dict) else None,
            )
        )
    counts = raw.get("write_mode_counts") or {}
    return ForestSnapshot(
        str(raw.get("forest_name") or ""),
        int(raw.get("property_count") or 0),
        {
            "read_only": int(counts.get("read_only") or 0),
            "scalar": int(counts.get("scalar") or 0),
            "color": int(counts.get("color") or 0),
        },
        tuple(properties),
        tuple(item for item in (raw.get("arrays") or []) if isinstance(item, dict)),
    )


class ForestControlService:
    def discover(self, *, preflight: bool = True) -> tuple[ForestSnapshot, ...]:
        if preflight:
            ensure_current_bridge()
        data = _require_ok(send_command("FOREST_CONTROL_DISCOVER"), "FOREST_CONTROL_DISCOVER")
        if data.get("read_only") is not True:
            raise ForestControlError("Stage 5D.32 discovery must remain read-only.")
        if not data.get("verified"):
            raise ForestControlError("Forest control discovery was not verified.")
        snapshots = tuple(
            _parse_forest_snapshot(item)
            for item in (data.get("forests") or [])
            if isinstance(item, dict)
        )
        if int(data.get("forest_count") or 0) != len(snapshots):
            raise ForestControlError("Forest count does not match discovery payload.")
        return snapshots


class ForestPackControlService(ForestControlService):
    """Stage 5D.34 compatibility facade over the verified read-only discovery core."""

    def list_forests(self, *, preflight: bool = True) -> tuple[str, ...]:
        return tuple(snapshot.forest_name for snapshot in self.discover(preflight=preflight))

    def capability_matrix(self, forest_name: str, *, preflight: bool = True) -> dict[str, Any]:
        snapshots = self.discover(preflight=preflight)
        for snapshot in snapshots:
            if snapshot.forest_name == forest_name:
                return {
                    "forest_name": snapshot.forest_name,
                    "property_count": snapshot.property_count,
                    "write_mode_counts": dict(snapshot.write_mode_counts),
                    "arrays": list(snapshot.arrays),
                }
        raise ForestControlError(f"Forest not found in discovery payload: {forest_name}")

    def inventory(self, forest_name: str, *, preflight: bool = True) -> dict[str, Any]:
        snapshots = self.discover(preflight=preflight)
        for snapshot in snapshots:
            if snapshot.forest_name == forest_name:
                return {
                    "forest_name": snapshot.forest_name,
                    "property_count": snapshot.property_count,
                    "properties": [
                        {
                            "name": prop.name,
                            "value_class": prop.value_class,
                            "write_mode": prop.write_mode,
                            "readable": prop.readable,
                            "value": prop.value,
                            "array_metadata": prop.array_metadata,
                        }
                        for prop in snapshot.properties
                    ],
                }
        raise ForestControlError(f"Forest not found in discovery payload: {forest_name}")

    def curve_metadata(self, forest_name: str, property_name: str, *, preflight: bool = True) -> dict[str, Any]:
        inventory = self.inventory(forest_name, preflight=preflight)
        for prop in inventory.get("properties") or []:
            if str(prop.get("name") or "") != property_name:
                continue
            if str(prop.get("value_class") or "") != "CurveControl":
                raise ForestControlError(
                    f"Forest property is not CurveControl: {forest_name}.{property_name}"
                )
            return {
                "name": property_name,
                "value_class": "CurveControl",
                "write_mode": "read_only",
                "readable": bool(prop.get("readable")),
                "value": prop.get("value"),
                "array_metadata": prop.get("array_metadata"),
            }
        raise ForestControlError(
            f"Forest property not found in discovery payload: {forest_name}.{property_name}"
        )


def aggregate_capability_matrix(snapshots: tuple[ForestSnapshot, ...]) -> dict[str, Any]:
    aggregate = {"read_only": 0, "scalar": 0, "color": 0}
    signatures = {}
    rows = []
    for snapshot in snapshots:
        for key in aggregate:
            aggregate[key] += int(snapshot.write_mode_counts.get(key, 0))
        for array in snapshot.arrays:
            metadata = array.get("metadata") if isinstance(array, dict) else None
            if not isinstance(metadata, dict):
                continue
            classes = metadata.get("element_classes") or []
            signature = ",".join(str(v) for v in classes) if classes else "<empty>"
            signatures[signature] = signatures.get(signature, 0) + 1
        rows.append(
            {
                "forest_name": snapshot.forest_name,
                "property_count": snapshot.property_count,
                "write_mode_counts": dict(snapshot.write_mode_counts),
                "arrays": list(snapshot.arrays),
            }
        )
    return {
        "forest_count": len(snapshots),
        "forests": rows,
        "aggregate_write_mode_counts": aggregate,
        "array_element_class_signatures": signatures,
        "policy": {
            "scalar": "read_write_transactional",
            "color": "read_write_transactional",
            "array_parameter": "typed_discovery_read_only",
            "node_material_reference_arrays": "read_only_until_specialized_adapter",
            "curve_control": "read_only_until_specialized_adapter",
        },
        "verified": bool(snapshots),
    }
