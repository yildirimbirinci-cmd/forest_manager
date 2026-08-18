from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from forest_manager.max_bridge.runtime_bridge import read_plant_group_manifest


class AIT2SceneRegionRuntimeError(RuntimeError):
    pass


_GROUP_LIST_KEYS = (
    "plant_groups",
    "groups",
    "resolved_groups",
    "manifest_groups",
)


def _decode_json_stdout(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        raise AIT2SceneRegionRuntimeError("AI/T2 resolution acceptance produced no JSON output.")

    starts = [index for index, char in enumerate(text) if char == "{"]
    for index in reversed(starts):
        candidate = text[index:]
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise AIT2SceneRegionRuntimeError("AI/T2 resolution acceptance output did not contain a JSON object.")


def run_ai_t2_resolution_acceptance(
    reference_image: str | Path,
    *,
    python_executable: str | None = None,
) -> dict[str, Any]:
    image = Path(reference_image).expanduser().resolve()
    if not image.is_file():
        raise AIT2SceneRegionRuntimeError(f"Reference image does not exist: {image}")

    command = [
        python_executable or sys.executable,
        "-m",
        "forest_manager.devtools.acceptance.stage8_ai_t2_resolution_acceptance",
        "--reference-image",
        str(image),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = _decode_json_stdout(completed.stdout)

    if completed.returncode != 0 or payload.get("ok") is not True:
        raise AIT2SceneRegionRuntimeError(
            "AI/T2 resolution acceptance failed: "
            + str(payload.get("error") or completed.stderr or payload)
        )
    if payload.get("mutated_scene") not in (None, False):
        raise AIT2SceneRegionRuntimeError(
            "AI/T2 resolution acceptance unexpectedly mutated the scene."
        )
    return payload


def _looks_like_group_list(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    dict_items = [item for item in value if isinstance(item, Mapping)]
    if not dict_items:
        return False
    return any(
        str(item.get("group_id") or item.get("id") or "").strip()
        and (
            item.get("source_names") is not None
            or item.get("resolved_source_names") is not None
            or item.get("source_name") is not None
            or item.get("resolved_source_name") is not None
        )
        for item in dict_items
    )


def _find_group_list(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, Mapping):
        for key in _GROUP_LIST_KEYS:
            candidate = value.get(key)
            if _looks_like_group_list(candidate):
                return [dict(item) for item in candidate if isinstance(item, Mapping)]
        for candidate in value.values():
            found = _find_group_list(candidate)
            if found:
                return found
    elif isinstance(value, list):
        if _looks_like_group_list(value):
            return [dict(item) for item in value if isinstance(item, Mapping)]
        for candidate in value:
            found = _find_group_list(candidate)
            if found:
                return found
    return None


def _manifest_groups() -> list[dict[str, Any]]:
    manifest = read_plant_group_manifest()
    groups = manifest.get("groups") if isinstance(manifest, Mapping) else None
    if not isinstance(groups, list):
        raise AIT2SceneRegionRuntimeError(
            "AI/T2 result did not expose groups and the live plant-group manifest is unavailable."
        )
    result = [dict(item) for item in groups if isinstance(item, Mapping)]
    if not result:
        raise AIT2SceneRegionRuntimeError("Live plant-group manifest contains no groups.")
    return result


def _source_names(group: Mapping[str, Any]) -> tuple[str, ...]:
    values = group.get("source_names")
    if isinstance(values, str):
        values = [values]
    if isinstance(values, (list, tuple)):
        result = tuple(str(value).strip() for value in values if str(value).strip())
        if result:
            return result

    for key in ("resolved_source_names",):
        values = group.get(key)
        if isinstance(values, (list, tuple)):
            result = tuple(str(value).strip() for value in values if str(value).strip())
            if result:
                return result

    for key in ("source_name", "resolved_source_name"):
        value = str(group.get(key) or "").strip()
        if value:
            return (value,)
    return ()


def _semantic_role(group: Mapping[str, Any]) -> str:
    for key in ("semantic_role", "role", "group_role", "planting_role"):
        value = str(group.get(key) or "").strip()
        if value:
            return value
    group_id = str(group.get("group_id") or group.get("id") or "").strip()
    if ":" in group_id:
        return group_id.rsplit(":", 1)[-1].strip()
    return ""


def normalize_runtime_groups(groups: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        group_id = str(group.get("group_id") or group.get("id") or "").strip()
        if not group_id:
            continue
        role = _semantic_role(group)
        sources = _source_names(group)
        if not sources:
            continue
        if not role:
            raise AIT2SceneRegionRuntimeError(
                f"Resolved runtime group has no semantic role: {group_id}"
            )
        normalized.append(
            {
                **dict(group),
                "group_id": group_id,
                "semantic_role": role,
                "source_names": list(sources),
            }
        )

    if not normalized:
        raise AIT2SceneRegionRuntimeError("AI/T2 runtime produced no resolved groups.")
    normalized.sort(key=lambda item: item["group_id"])
    return normalized


def resolve_ai_t2_runtime_groups(
    reference_image: str | Path,
    *,
    python_executable: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    payload = run_ai_t2_resolution_acceptance(
        reference_image,
        python_executable=python_executable,
    )
    groups = _find_group_list(payload)
    source = "ai_t2_acceptance_payload"
    if not groups:
        groups = _manifest_groups()
        source = "verified_live_plant_group_manifest_fallback"

    normalized = normalize_runtime_groups(groups)

    reported_count = payload.get("resolved_group_count")
    if reported_count is not None and int(reported_count) != len(normalized):
        raise AIT2SceneRegionRuntimeError(
            "AI/T2 resolved-group count does not match the groups available for binding: "
            + f"reported={reported_count}, available={len(normalized)}"
        )

    return payload, normalized, source
