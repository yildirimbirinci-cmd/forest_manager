from __future__ import annotations

import base64

from dataclasses import dataclass
import math
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
    """Forest Pack discovery plus verified scalar/color/array/reference/texture write and rollback endpoints."""

    EXPLICIT_RUNTIME_READ_ONLY = {"geomtexid", "fastopac", "renderid", "divtmap", "geomtex"}
    NODE_REFERENCE_ARRAY_PROPERTIES = {"arnodelist"}
    MATERIAL_REFERENCE_ARRAY_PROPERTIES = {"matlist"}
    CPROXY_REFERENCE_ARRAY_PROPERTIES = {"cobjlist"}
    TEXTURE_REFERENCE_PROPERTIES = {"distmap"}
    SCALAR_CLASS_FAMILIES = {
        "BooleanClass": "bool",
        "Integer": "int",
        "Integer64": "int",
        "Float": "float",
        "Double": "float",
        "String": "string",
    }

    def __init__(self) -> None:
        self._rollback_journal: list[dict[str, Any]] = []

    @staticmethod
    def _token(value: str) -> str:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    @classmethod
    def _scalar_type_for(cls, value_class: str, value: Any) -> tuple[str, str]:
        scalar_type = cls.SCALAR_CLASS_FAMILIES.get(value_class, "")
        if not scalar_type:
            raise ForestControlError(f"Unsupported scalar value class: {value_class}")
        if scalar_type == "bool":
            if not isinstance(value, bool):
                raise ForestControlError(f"Boolean property requires bool, got {type(value).__name__}")
            return scalar_type, "true" if value else "false"
        if scalar_type == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ForestControlError(f"Integer property requires int, got {type(value).__name__}")
            return scalar_type, str(value)
        if scalar_type == "float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ForestControlError(f"Float property requires numeric value, got {type(value).__name__}")
            return scalar_type, repr(float(value))
        if not isinstance(value, str):
            raise ForestControlError(f"String property requires str, got {type(value).__name__}")
        return scalar_type, value

    @staticmethod
    def _values_match(actual: Any, expected: Any, scalar_type: str) -> bool:
        if scalar_type == "float":
            try:
                return abs(float(actual) - float(expected)) <= 1e-6
            except (TypeError, ValueError):
                return False
        return type(actual) is type(expected) and actual == expected

    @staticmethod
    def _normalize_color(value: Any) -> tuple[float, float, float]:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ForestControlError("Color property requires an RGB list/tuple with exactly 3 numeric channels.")
        channels: list[float] = []
        for channel in value:
            if isinstance(channel, bool) or not isinstance(channel, (int, float)):
                raise ForestControlError("Color property requires numeric RGB channels.")
            numeric = float(channel)
            if numeric < 0.0 or numeric > 255.0:
                raise ForestControlError("Color channels must be within 0..255.")
            channels.append(numeric)
        return tuple(channels)

    @classmethod
    def _colors_match(cls, actual: Any, expected: Any) -> bool:
        try:
            actual_rgb = cls._normalize_color(actual)
            expected_rgb = cls._normalize_color(expected)
        except ForestControlError:
            return False
        return all(abs(a - b) <= 1e-4 for a, b in zip(actual_rgb, expected_rgb))

    @staticmethod
    def _normalize_point3(value: Any) -> tuple[float, float, float]:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ForestControlError("Point3 array element requires a list/tuple with exactly 3 numeric components.")
        components: list[float] = []
        for component in value:
            if isinstance(component, bool) or not isinstance(component, (int, float)):
                raise ForestControlError("Point3 array element requires numeric components.")
            numeric = float(component)
            if not math.isfinite(numeric):
                raise ForestControlError("Point3 array element components must be finite numbers.")
            components.append(numeric)
        return tuple(components)

    @classmethod
    def _point3_match(cls, actual: Any, expected: Any) -> bool:
        try:
            actual_xyz = cls._normalize_point3(actual)
            expected_xyz = cls._normalize_point3(expected)
        except ForestControlError:
            return False
        return all(abs(a - b) <= 1e-5 for a, b in zip(actual_xyz, expected_xyz))

    def get_property(self, forest_name: str, property_name: str, *, preflight: bool = True) -> dict[str, Any]:
        if preflight:
            ensure_current_bridge()
        command = "FOREST_CONTROL_GET_PROPERTY|" + self._token(forest_name) + "|" + self._token(property_name)
        data = _require_ok(send_command(command), "FOREST_CONTROL_GET_PROPERTY")
        prop = data.get("property")
        if not isinstance(prop, dict):
            raise ForestControlError("FOREST_CONTROL_GET_PROPERTY returned invalid property data.")
        if str(data.get("forest_name") or "") != forest_name or str(prop.get("name") or "") != property_name:
            raise ForestControlError("FOREST_CONTROL_GET_PROPERTY identity mismatch.")
        if prop.get("readable") is not True:
            raise ForestControlError(f"Forest property is not readable: {forest_name}.{property_name}")
        return prop

    def _send_scalar(
        self,
        forest_name: str,
        property_name: str,
        value: bool | int | float | str,
        *,
        value_class: str,
        preflight: bool,
    ) -> dict[str, Any]:
        if preflight:
            ensure_current_bridge()
        scalar_type, encoded_text = self._scalar_type_for(value_class, value)
        command = "|".join((
            "FOREST_CONTROL_SET_SCALAR",
            self._token(forest_name),
            self._token(property_name),
            scalar_type,
            self._token(encoded_text),
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_SCALAR")
        if data.get("verified") is not True:
            raise ForestControlError(f"Forest scalar write was not verified: {forest_name}.{property_name}")
        readback = self.get_property(forest_name, property_name, preflight=False)
        if not self._values_match(readback.get("value"), value, scalar_type):
            raise ForestControlError(f"Forest scalar readback mismatch: {forest_name}.{property_name}")
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "value_class": value_class,
            "scalar_type": scalar_type,
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }

    def _send_color(
        self,
        forest_name: str,
        property_name: str,
        value: list[float] | tuple[float, float, float],
        *,
        preflight: bool,
    ) -> dict[str, Any]:
        if preflight:
            ensure_current_bridge()
        rgb = self._normalize_color(value)
        command = "|".join((
            "FOREST_CONTROL_SET_COLOR",
            self._token(forest_name),
            self._token(property_name),
            repr(rgb[0]),
            repr(rgb[1]),
            repr(rgb[2]),
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_COLOR")
        if data.get("verified") is not True:
            raise ForestControlError(f"Forest color write was not verified: {forest_name}.{property_name}")
        readback = self.get_property(forest_name, property_name, preflight=False)
        if not self._colors_match(readback.get("value"), rgb):
            raise ForestControlError(f"Forest color readback mismatch: {forest_name}.{property_name}")
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "value_class": "Color",
            "color_type": "rgb_0_255",
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }


    def get_array_element(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        *,
        preflight: bool = True,
    ) -> dict[str, Any]:
        if isinstance(index, bool) or not isinstance(index, int):
            raise ForestControlError("Array element index must be an integer.")
        if index < 0:
            raise ForestControlError("Array element index must be zero or greater.")
        if preflight:
            ensure_current_bridge()
        command = "|".join((
            "FOREST_CONTROL_GET_ARRAY_ELEMENT",
            self._token(forest_name),
            self._token(property_name),
            str(index),
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_GET_ARRAY_ELEMENT")
        if str(data.get("forest_name") or "") != forest_name:
            raise ForestControlError("FOREST_CONTROL_GET_ARRAY_ELEMENT forest identity mismatch.")
        if str(data.get("property_name") or "") != property_name:
            raise ForestControlError("FOREST_CONTROL_GET_ARRAY_ELEMENT property identity mismatch.")
        if int(data.get("index", -1)) != index:
            raise ForestControlError("FOREST_CONTROL_GET_ARRAY_ELEMENT index mismatch.")
        if data.get("verified") is not True:
            raise ForestControlError(f"Forest array element read was not verified: {forest_name}.{property_name}[{index}]")
        return data

    def _send_array_scalar(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        value: bool | int | float | str,
        *,
        value_class: str,
        preflight: bool,
    ) -> dict[str, Any]:
        if preflight:
            ensure_current_bridge()
        scalar_type, encoded_text = self._scalar_type_for(value_class, value)
        command = "|".join((
            "FOREST_CONTROL_SET_ARRAY_SCALAR",
            self._token(forest_name),
            self._token(property_name),
            str(index),
            scalar_type,
            self._token(encoded_text),
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_ARRAY_SCALAR")
        if data.get("verified") is not True:
            raise ForestControlError(
                f"Forest array scalar write was not verified: {forest_name}.{property_name}[{index}]"
            )
        readback = self.get_array_element(forest_name, property_name, index, preflight=False)
        if str(readback.get("value_class") or "") != value_class:
            raise ForestControlError(
                f"Forest array scalar readback class mismatch: {forest_name}.{property_name}[{index}]"
            )
        if not self._values_match(readback.get("value"), value, scalar_type):
            raise ForestControlError(
                f"Forest array scalar readback mismatch: {forest_name}.{property_name}[{index}]"
            )
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": value_class,
            "scalar_type": scalar_type,
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }

    def _send_array_point3(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        value: Any,
        *,
        preflight: bool,
    ) -> dict[str, Any]:
        if preflight:
            ensure_current_bridge()
        xyz = self._normalize_point3(value)
        command = "|".join((
            "FOREST_CONTROL_SET_ARRAY_POINT3",
            self._token(forest_name),
            self._token(property_name),
            str(index),
            repr(xyz[0]),
            repr(xyz[1]),
            repr(xyz[2]),
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_ARRAY_POINT3")
        if data.get("verified") is not True:
            raise ForestControlError(
                f"Forest array Point3 write was not verified: {forest_name}.{property_name}[{index}]"
            )
        readback = self.get_array_element(forest_name, property_name, index, preflight=False)
        if str(readback.get("value_class") or "") != "Point3":
            raise ForestControlError(
                f"Forest array Point3 readback class mismatch: {forest_name}.{property_name}[{index}]"
            )
        if not self._point3_match(readback.get("value"), xyz):
            raise ForestControlError(
                f"Forest array Point3 readback mismatch: {forest_name}.{property_name}[{index}]"
            )
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": "Point3",
            "vector_type": "point3",
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }


    @staticmethod
    def _normalize_node_reference(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ForestControlError("Node reference array element requires a non-empty scene node name or None.")
        return value.strip()

    def _send_array_node_reference(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        value: str | None,
        *,
        preflight: bool,
    ) -> dict[str, Any]:
        if property_name.lower() not in self.NODE_REFERENCE_ARRAY_PROPERTIES:
            raise ForestControlError(f"Node reference array writes are not enabled for: {property_name}")
        if preflight:
            ensure_current_bridge()
        node_name = self._normalize_node_reference(value)
        mode = "null" if node_name is None else "node"
        token = self._token(node_name) if node_name is not None else "NONE"
        command = "|".join((
            "FOREST_CONTROL_SET_ARRAY_NODE_REF",
            self._token(forest_name),
            self._token(property_name),
            str(index),
            mode,
            token,
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_ARRAY_NODE_REF")
        if data.get("verified") is not True:
            raise ForestControlError(
                f"Forest array node reference write was not verified: {forest_name}.{property_name}[{index}]"
            )
        readback = self.get_array_element(forest_name, property_name, index, preflight=False)
        if str(readback.get("reference_type") or "") != "node":
            raise ForestControlError(
                f"Forest array node reference readback type mismatch: {forest_name}.{property_name}[{index}]"
            )
        if readback.get("value") != node_name:
            raise ForestControlError(
                f"Forest array node reference readback mismatch: {forest_name}.{property_name}[{index}]"
            )
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": str(readback.get("value_class") or ""),
            "reference_type": "node",
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }

    @staticmethod
    def _normalize_material_reference(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ForestControlError("Material reference array element requires a non-empty scene material name or None.")
        return value.strip()

    def _send_array_material_reference(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        value: str | None,
        *,
        preflight: bool,
    ) -> dict[str, Any]:
        if property_name.lower() not in self.MATERIAL_REFERENCE_ARRAY_PROPERTIES:
            raise ForestControlError(f"Material reference array writes are not enabled for: {property_name}")
        if preflight:
            ensure_current_bridge()
        material_name = self._normalize_material_reference(value)
        mode = "null" if material_name is None else "material"
        token = self._token(material_name) if material_name is not None else "NONE"
        command = "|".join((
            "FOREST_CONTROL_SET_ARRAY_MATERIAL_REF",
            self._token(forest_name),
            self._token(property_name),
            str(index),
            mode,
            token,
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_ARRAY_MATERIAL_REF")
        if data.get("verified") is not True:
            raise ForestControlError(
                f"Forest array material reference write was not verified: {forest_name}.{property_name}[{index}]"
            )
        readback = self.get_array_element(forest_name, property_name, index, preflight=False)
        if str(readback.get("reference_type") or "") != "material":
            raise ForestControlError(
                f"Forest array material reference readback type mismatch: {forest_name}.{property_name}[{index}]"
            )
        if readback.get("value") != material_name:
            raise ForestControlError(
                f"Forest array material reference readback mismatch: {forest_name}.{property_name}[{index}]"
            )
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": str(readback.get("value_class") or ""),
            "reference_type": "material",
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }


    @staticmethod
    def _normalize_cproxy_reference(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ForestControlError("CProxy reference array element requires a non-empty scene node name or None.")
        return value.strip()

    def _send_array_cproxy_reference(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        value: str | None,
        *,
        preflight: bool,
    ) -> dict[str, Any]:
        if property_name.lower() not in self.CPROXY_REFERENCE_ARRAY_PROPERTIES:
            raise ForestControlError(f"CProxy reference array writes are not enabled for: {property_name}")
        if preflight:
            ensure_current_bridge()
        node_name = self._normalize_cproxy_reference(value)
        mode = "null" if node_name is None else "cproxy"
        token = self._token(node_name) if node_name is not None else "NONE"
        command = "|".join((
            "FOREST_CONTROL_SET_ARRAY_CPROXY_REF",
            self._token(forest_name),
            self._token(property_name),
            str(index),
            mode,
            token,
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_ARRAY_CPROXY_REF")
        if data.get("verified") is not True:
            raise ForestControlError(
                f"Forest array CProxy reference write was not verified: {forest_name}.{property_name}[{index}]"
            )
        readback = self.get_array_element(forest_name, property_name, index, preflight=False)
        if str(readback.get("reference_type") or "") != "cproxy":
            raise ForestControlError(
                f"Forest array CProxy reference readback type mismatch: {forest_name}.{property_name}[{index}]"
            )
        if readback.get("value") != node_name:
            raise ForestControlError(
                f"Forest array CProxy reference readback mismatch: {forest_name}.{property_name}[{index}]"
            )
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": str(readback.get("value_class") or ""),
            "reference_type": "cproxy",
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }

    @staticmethod
    def _normalize_texture_reference(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ForestControlError("Texture reference property requires a non-empty AnimHandle or bitmap filename token, or None.")
        return value.strip()

    def get_texture_reference(
        self,
        forest_name: str,
        property_name: str = "distmap",
        *,
        preflight: bool = True,
    ) -> dict[str, Any]:
        if property_name.lower() not in self.TEXTURE_REFERENCE_PROPERTIES:
            raise ForestControlError(f"Texture reference writes are not enabled for: {property_name}")
        if preflight:
            ensure_current_bridge()
        command = "|".join((
            "FOREST_CONTROL_GET_TEXTURE_REF",
            self._token(forest_name),
            self._token(property_name),
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_GET_TEXTURE_REF")
        if data.get("verified") is not True:
            raise ForestControlError(f"Forest texture reference read was not verified: {forest_name}.{property_name}")
        if str(data.get("forest_name") or "") != forest_name or str(data.get("property_name") or "") != property_name:
            raise ForestControlError("FOREST_CONTROL_GET_TEXTURE_REF identity mismatch.")
        if str(data.get("reference_type") or "") != "texture":
            raise ForestControlError(f"Forest texture reference type mismatch: {forest_name}.{property_name}")
        return data

    def _send_texture_reference(
        self,
        forest_name: str,
        property_name: str,
        value: str | None,
        *,
        preflight: bool,
    ) -> dict[str, Any]:
        if property_name.lower() not in self.TEXTURE_REFERENCE_PROPERTIES:
            raise ForestControlError(f"Texture reference writes are not enabled for: {property_name}")
        if preflight:
            ensure_current_bridge()
        reference = self._normalize_texture_reference(value)
        if reference is None:
            mode = "null"
            token = "NONE"
        elif reference.lower().startswith("anim:"):
            handle_text = reference[5:].strip()
            if handle_text[-1:].lower() in {"p", "l"}:
                handle_text = handle_text[:-1]
            if not handle_text.isdigit() or int(handle_text) <= 0:
                raise ForestControlError(f"Invalid texture AnimHandle token: {reference}")
            reference = f"anim:{int(handle_text)}"
            mode = "anim"
            token = self._token(reference)
        else:
            mode = "bitmap"
            token = self._token(reference)
        command = "|".join((
            "FOREST_CONTROL_SET_TEXTURE_REF",
            self._token(forest_name),
            self._token(property_name),
            mode,
            token,
        ))
        data = _require_ok(send_command(command), "FOREST_CONTROL_SET_TEXTURE_REF")
        if data.get("verified") is not True:
            raise ForestControlError(f"Forest texture reference write was not verified: {forest_name}.{property_name}")
        readback = self.get_texture_reference(forest_name, property_name, preflight=False)
        if mode == "bitmap":
            matches = readback.get("filename") == reference
        else:
            matches = readback.get("value") == reference
        if not matches:
            raise ForestControlError(f"Forest texture reference readback mismatch: {forest_name}.{property_name}")
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "value_class": str(readback.get("value_class") or ""),
            "reference_type": "texture",
            "before_value": data.get("before_value"),
            "after_value": readback.get("value"),
            "verified": True,
        }

    def set_array_element(
        self,
        forest_name: str,
        property_name: str,
        index: int,
        value: Any,
        *,
        preflight: bool = True,
    ) -> dict[str, Any]:
        before = self.get_array_element(forest_name, property_name, index, preflight=preflight)
        value_class = str(before.get("value_class") or "")
        reference_type = str(before.get("reference_type") or "")
        if reference_type == "node" and property_name.lower() in self.NODE_REFERENCE_ARRAY_PROPERTIES:
            self._normalize_node_reference(value)
            result = self._send_array_node_reference(
                forest_name, property_name, index, value, preflight=False
            )
            write_mode = "array_node_ref"
        elif reference_type == "material" and property_name.lower() in self.MATERIAL_REFERENCE_ARRAY_PROPERTIES:
            self._normalize_material_reference(value)
            result = self._send_array_material_reference(
                forest_name, property_name, index, value, preflight=False
            )
            write_mode = "array_material_ref"
        elif reference_type == "cproxy" and property_name.lower() in self.CPROXY_REFERENCE_ARRAY_PROPERTIES:
            self._normalize_cproxy_reference(value)
            result = self._send_array_cproxy_reference(
                forest_name, property_name, index, value, preflight=False
            )
            write_mode = "array_cproxy_ref"
        elif value_class == "Point3":
            self._normalize_point3(value)
            result = self._send_array_point3(
                forest_name, property_name, index, value, preflight=False
            )
            write_mode = "array_point3"
        else:
            self._scalar_type_for(value_class, value)
            result = self._send_array_scalar(
                forest_name,
                property_name,
                index,
                value,
                value_class=value_class,
                preflight=False,
            )
            write_mode = "array_scalar"
        self._rollback_journal.append({
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": value_class,
            "write_mode": write_mode,
            "value": before.get("value"),
        })
        return result

    def set_property(
        self,
        forest_name: str,
        property_name: str,
        value: Any,
        *,
        preflight: bool = True,
    ) -> dict[str, Any]:
        if property_name.lower() in self.EXPLICIT_RUNTIME_READ_ONLY:
            raise ForestControlError(f"Forest property is explicitly read-only: {property_name}")
        if property_name.lower() in self.TEXTURE_REFERENCE_PROPERTIES:
            before_texture = self.get_texture_reference(forest_name, property_name, preflight=preflight)
            self._normalize_texture_reference(value)
            result = self._send_texture_reference(forest_name, property_name, value, preflight=False)
            self._rollback_journal.append({
                "forest_name": forest_name,
                "property_name": property_name,
                "value_class": str(before_texture.get("value_class") or ""),
                "write_mode": "texture_ref",
                "value": before_texture.get("value"),
            })
            return result
        before = self.get_property(forest_name, property_name, preflight=preflight)
        write_mode = str(before.get("write_mode") or "")
        value_class = str(before.get("value_class") or "")
        if write_mode == "scalar":
            self._scalar_type_for(value_class, value)
            result = self._send_scalar(
                forest_name, property_name, value, value_class=value_class, preflight=False
            )
        elif write_mode == "color" and value_class == "Color":
            self._normalize_color(value)
            result = self._send_color(forest_name, property_name, value, preflight=False)
        else:
            raise ForestControlError(
                f"Forest property is not writable by a verified endpoint: {forest_name}.{property_name} "
                f"class={value_class} mode={write_mode}"
            )
        self._rollback_journal.append({
            "forest_name": forest_name,
            "property_name": property_name,
            "value_class": value_class,
            "write_mode": write_mode,
            "value": before.get("value"),
        })
        return result

    def rollback_marker(self) -> int:
        """Return a stable journal boundary for scoped transaction rollback."""
        return len(self._rollback_journal)

    def rollback_to(self, marker: int) -> list[dict[str, Any]]:
        if isinstance(marker, bool) or not isinstance(marker, int):
            raise ForestControlError("Rollback marker must be an integer.")
        if marker < 0 or marker > len(self._rollback_journal):
            raise ForestControlError(
                f"Rollback marker is outside the current journal: {marker}/{len(self._rollback_journal)}"
            )
        if marker == len(self._rollback_journal):
            return []
        results: list[dict[str, Any]] = []
        pending = list(reversed(self._rollback_journal[marker:]))
        restored = 0
        try:
            for entry in pending:
                write_mode = str(entry.get("write_mode") or "scalar")
                if write_mode == "texture_ref":
                    result = self._send_texture_reference(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        entry["value"],
                        preflight=(restored == 0),
                    )
                elif write_mode == "color":
                    result = self._send_color(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        entry["value"],
                        preflight=(restored == 0),
                    )
                elif write_mode == "array_scalar":
                    result = self._send_array_scalar(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        int(entry["index"]),
                        entry["value"],
                        value_class=str(entry["value_class"]),
                        preflight=(restored == 0),
                    )
                elif write_mode == "array_point3":
                    result = self._send_array_point3(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        int(entry["index"]),
                        entry["value"],
                        preflight=(restored == 0),
                    )
                elif write_mode == "array_node_ref":
                    result = self._send_array_node_reference(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        int(entry["index"]),
                        entry["value"],
                        preflight=(restored == 0),
                    )
                elif write_mode == "array_material_ref":
                    result = self._send_array_material_reference(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        int(entry["index"]),
                        entry["value"],
                        preflight=(restored == 0),
                    )
                elif write_mode == "array_cproxy_ref":
                    result = self._send_array_cproxy_reference(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        int(entry["index"]),
                        entry["value"],
                        preflight=(restored == 0),
                    )
                else:
                    result = self._send_scalar(
                        str(entry["forest_name"]),
                        str(entry["property_name"]),
                        entry["value"],
                        value_class=str(entry["value_class"]),
                        preflight=(restored == 0),
                    )
                step = {
                    "forest_name": entry["forest_name"],
                    "property_name": entry["property_name"],
                    "restored": entry["value"],
                    "verified": bool(result.get("verified")),
                }
                if write_mode in {"array_scalar", "array_point3", "array_node_ref", "array_material_ref", "array_cproxy_ref"}:
                    step["index"] = int(entry["index"])
                results.append(step)
                restored += 1
        except Exception:
            remaining_original_order = list(reversed(pending[restored:]))
            self._rollback_journal = self._rollback_journal[:marker] + remaining_original_order
            raise
        del self._rollback_journal[marker:]
        return results

    def rollback(self) -> list[dict[str, Any]]:
        return self.rollback_to(0)

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

    def curve_points(self, forest_name: str, property_name: str, *, preflight: bool = True) -> dict[str, Any]:
        metadata = self.curve_metadata(forest_name, property_name, preflight=preflight)
        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "value_class": "CurveControl",
            "readable": bool(metadata.get("readable")),
            "curve_count": 0,
            "curves": [],
            "point_api_supported": False,
            "point_read_supported": False,
            "point_write_supported": False,
            "point_count_change_supported": False,
            "reason": "Forest Pack CurveControl is opaque in the verified runtime; direct point/controller API is not exposed.",
            "verified": True,
        }


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
            "array_parameter": "primitive_scalar_and_point3_element_write",
            "node_reference_arrays": "arnodelist_transactional",
            "material_reference_arrays": "matlist_transactional",
            "cproxy_reference_arrays": "cobjlist_transactional",
            "bitmap_reference_arrays": "read_only_until_specialized_adapter",
            "curve_control": "read_only_verified_runtime_boundary",
        },
        "verified": bool(snapshots),
    }
