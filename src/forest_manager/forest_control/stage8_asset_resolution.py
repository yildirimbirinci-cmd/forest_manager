from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from forest_manager.forest_control.service import ForestControlError, ForestPackControlService
from forest_manager.site_model import PlantingGroupIntent, PlantingPlan
from forest_manager.t2_bridge.catalog import T2AssetCatalog, T2AssetRecord


_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "foreground_mass": ("Lavandula", "Hidcote", "Lavender"),
    "mid_accent": ("Butomus", "Flowering rush"),
    "structural_shrub": ("Bush_Berberis", "Berberis"),
}


class Stage8AssetResolutionError(RuntimeError):
    pass




def _norm(value: str) -> str:
    return "".join(ch.casefold() for ch in str(value) if ch.isalnum())


def _candidate_score(record: T2AssetRecord, requested_name: str, aliases: Iterable[str]) -> tuple[int, int, str]:
    requested = _norm(requested_name)
    record_name = _norm(record.name)
    stem = _norm(record.file_path.stem)
    full = _norm(str(record.file_path))
    score = 0
    if record_name == requested or stem == requested:
        score += 10000
    if requested and requested in record_name:
        score += 5000
    if requested and requested in stem:
        score += 5000
    for position, alias in enumerate(aliases):
        token = _norm(alias)
        if not token:
            continue
        weight = max(100, 1200 - position * 100)
        if record_name == token or stem == token:
            score += weight * 4
        elif token in record_name or token in stem:
            score += weight * 2
        elif token in full:
            score += weight
    # Prefer database records over fallback scans when otherwise equivalent.
    if record.source == "database":
        score += 20
    return score, -len(str(record.file_path)), str(record.file_path).casefold()


class Stage8T2AssetResolver:
    """Resolve PlantingPlan species to existing T2 .max assets and merge them into Max."""

    def __init__(
        self,
        catalog: T2AssetCatalog | None = None,
        *,
        control_service: ForestPackControlService | None = None,
    ) -> None:
        self.catalog = catalog or T2AssetCatalog()
        self.control_service = control_service or ForestPackControlService()

    def _search_terms(self, requested_name: str, semantic_role: str) -> list[str]:
        aliases = list(_ROLE_ALIASES.get(semantic_role, ()))
        terms = [requested_name]
        terms.extend(aliases)
        # Stable dedupe while preserving the strongest exact query first.
        result: list[str] = []
        seen: set[str] = set()
        for value in terms:
            value = str(value or "").strip()
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                result.append(value)
        return result

    def resolve_asset(self, requested_name: str, semantic_role: str) -> T2AssetRecord:
        aliases = _ROLE_ALIASES.get(semantic_role, ())
        candidates: dict[str, T2AssetRecord] = {}
        for term in self._search_terms(requested_name, semantic_role):
            for record in self.catalog.search_max_assets(term, limit=100, require_existing_file=True):
                key = str(record.file_path).casefold()
                candidates.setdefault(key, record)
        if not candidates:
            diagnostics = self.catalog.diagnostics()
            roots = diagnostics.get("library_roots") or []
            raise Stage8AssetResolutionError(
                "No T2 .max asset found for species "
                f"'{requested_name}' (role={semantic_role}). "
                f"T2 database={diagnostics.get('database')}; library_roots={roots}"
            )
        ranked = sorted(
            candidates.values(),
            key=lambda record: _candidate_score(record, requested_name, aliases),
            reverse=True,
        )
        best = ranked[0]
        if _candidate_score(best, requested_name, aliases)[0] <= 0:
            raise Stage8AssetResolutionError(
                f"T2 candidates were found for '{requested_name}', but none matched the requested species strongly enough."
            )
        return best

    def _invoke_merge(self, asset_path: Path, *, append: bool) -> dict[str, Any]:
        try:
            return self.control_service.merge_t2_asset(
                str(asset_path),
                append=append,
                scale_percent=100.0,
                timeout=30.0,
                preflight=False,
            )
        except ForestControlError as exc:
            raise Stage8AssetResolutionError(
                f"T2 asset merge failed for {asset_path}: {exc}"
            ) from exc

    def merge_missing_source(
        self,
        requested_name: str,
        semantic_role: str,
        *,
        geometry_count: int,
    ) -> dict[str, Any]:
        record = self.resolve_asset(requested_name, semantic_role)
        data = self._invoke_merge(record.file_path, append=geometry_count > 0)
        return {
            "requested_name": requested_name,
            "semantic_role": semantic_role,
            "asset_name": record.name,
            "asset_path": str(record.file_path),
            "catalog_source": record.source,
            "source_name": str(data.get("source_name") or ""),
            "geometry_index": int(data.get("geometry_index") or (geometry_count + 1)),
            "merge": data,
            "verified": True,
        }

    @staticmethod
    def remap_plan(plan: PlantingPlan, source_name_map: dict[str, str]) -> PlantingPlan:
        groups: list[PlantingGroupIntent] = []
        for group in plan.groups:
            names = tuple(source_name_map.get(name, name) for name in group.source_names)
            groups.append(replace(group, source_names=names))
        return replace(plan, groups=tuple(groups))
