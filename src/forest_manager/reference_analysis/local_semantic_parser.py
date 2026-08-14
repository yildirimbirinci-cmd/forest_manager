from __future__ import annotations

import json
import re
from typing import Any


class LocalSemanticParseError(RuntimeError):
    pass


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return cleaned


def _try_json(text: str) -> dict[str, Any] | None:
    cleaned = _strip_fence(text)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        return None

    try:
        payload = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _parse_plants(value: str) -> list[dict[str, Any]]:
    plants: list[dict[str, Any]] = []

    for part in value.split(";"):
        item = part.strip()
        if not item:
            continue

        if "|" in item:
            query, weight_text = item.rsplit("|", 1)
        elif "," in item:
            query, weight_text = item.rsplit(",", 1)
        else:
            query, weight_text = item, "1"

        query = query.strip()
        weight_text = weight_text.strip()

        try:
            weight = float(weight_text)
        except ValueError:
            weight = 1.0

        if query and weight > 0:
            plants.append({
                "query": query,
                "weight": weight,
            })

    return plants


def _try_line_format(text: str) -> dict[str, Any] | None:
    fields: dict[str, str] = {}

    aliases = {
        "STYLE": "style",
        "DENSITY": "density",
        "DIVERSITY": "diversity",
        "CANOPY": "canopy_bias",
        "CANOPY_BIAS": "canopy_bias",
        "NOTES": "composition_notes",
        "PLANTS": "plant_candidates",
        "PLANT_CANDIDATES": "plant_candidates",
        "CONFIDENCE": "confidence",
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        normalized = re.sub(r"[^A-Z_]", "", key.strip().upper().replace(" ", "_"))
        target = aliases.get(normalized)
        if target:
            fields[target] = value.strip()

    required = {
        "style",
        "density",
        "diversity",
        "canopy_bias",
        "plant_candidates",
        "confidence",
    }
    if not required.issubset(fields):
        return None

    try:
        confidence = float(fields["confidence"])
    except ValueError:
        return None

    notes_value = fields.get("composition_notes", "")
    notes = [
        item.strip()
        for item in notes_value.split(";")
        if item.strip()
    ]

    plants = _parse_plants(fields["plant_candidates"])
    if not plants:
        return None

    return {
        "style": fields["style"],
        "density": fields["density"],
        "diversity": fields["diversity"],
        "canopy_bias": fields["canopy_bias"],
        "composition_notes": notes,
        "plant_candidates": plants,
        "confidence": confidence,
    }


def parse_local_semantic_output(text: str) -> dict[str, Any]:
    payload = _try_json(text)
    if payload is not None:
        return payload

    payload = _try_line_format(text)
    if payload is not None:
        return payload

    preview = " ".join(text.strip().split())
    if len(preview) > 1200:
        preview = preview[:1200] + "..."

    raise LocalSemanticParseError(
        "Local vision output could not be parsed. Raw output: " + preview
    )
