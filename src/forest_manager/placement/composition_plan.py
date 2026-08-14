from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class CompositionItem:
    query: str
    weight: float

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("Composition item query must not be empty.")
        if float(self.weight) <= 0:
            raise ValueError("Composition item weight must be greater than zero.")


@dataclass(frozen=True)
class CompositionPlan:
    name: str
    items: tuple[CompositionItem, ...]

    @classmethod
    def from_dict(cls, payload: dict) -> "CompositionPlan":
        raw_items = payload.get("items") or []
        if not raw_items:
            raise ValueError("Composition plan requires at least one item.")

        items = tuple(
            CompositionItem(
                query=str(item["query"]).strip(),
                weight=float(item["weight"]),
            )
            for item in raw_items
        )
        return cls(
            name=str(payload.get("name") or "Untitled composition").strip(),
            items=items,
        )

    @classmethod
    def from_json_file(cls, path: Path | str) -> "CompositionPlan":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @property
    def normalized_probabilities(self) -> list[float]:
        total = sum(float(item.weight) for item in self.items)
        return [(float(item.weight) / total) * 100.0 for item in self.items]
