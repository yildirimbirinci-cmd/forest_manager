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

_PLANT_ROLES = {
    "foreground_mass",
    "mid_accent",
    "purple_accent",
    "flower_accent",
    "structural_shrub",
    "ornamental_grass",
    "groundcover",
}
_TREE_ROLES = {"tree_canopy"}


def _asset_bucket(record: T2AssetRecord) -> str:
    parts = {part.casefold() for part in record.file_path.parts}
    if "01_trees" in parts:
        return "trees"
    if "02_plants" in parts:
        return "plants"
    return "unknown"


def _asset_matches_semantic_role(record: T2AssetRecord, semantic_role: str) -> bool:
    role = str(semantic_role or "").casefold().strip()
    bucket = _asset_bucket(record)
    if bucket == "unknown":
        return True
    if role in _PLANT_ROLES:
        return bucket == "plants"
    if role in _TREE_ROLES:
        return bucket == "trees"
    return True


class Stage8AssetResolutionError(RuntimeError):
    pass


def _norm(value: str) -> str:
    return "".join(ch.casefold() for ch in str(value) if ch.isalnum())


def _words(value: str) -> tuple[str, ...]:
    text = "".join(ch.casefold() if ch.isalnum() else " " for ch in str(value))
    return tuple(part for part in text.split() if part)


def _singular_word(value: str) -> str:
    word = str(value).casefold().strip()
    if word == "species":
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("sses", "shes", "ches", "xes", "zes")):
        return word[:-2]
    if len(word) > 4 and word.endswith("ises"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _strict_search_terms(requested_name: str) -> list[str]:
    requested_name = str(requested_name or "").strip()
    terms: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = str(value or "").strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            terms.append(value)

    add(requested_name)
    words = _words(requested_name)
    singular_words = tuple(_singular_word(word) for word in words)
    if singular_words and singular_words != words:
        add(" ".join(singular_words))
    for word in reversed(singular_words):
        if len(word) >= 4:
            add(word)
    return terms


def _strict_candidate_score(record: T2AssetRecord, requested_name: str) -> int:
    requested_norm = _norm(requested_name)
    record_name_norm = _norm(record.name)
    stem_norm = _norm(record.file_path.stem)
    if requested_norm and (record_name_norm == requested_norm or stem_norm == requested_norm):
        return 100000
    if requested_norm and (requested_norm in record_name_norm or requested_norm in stem_norm):
        return 50000

    requested_words = tuple(_singular_word(word) for word in _words(requested_name))
    record_words = set(_words(record.name)) | set(_words(record.file_path.stem))
    matched = sum(1 for word in requested_words if word and word in record_words)
    if matched <= 0:
        return 0
    score = matched * 5000
    if requested_words and requested_words[-1] in record_words:
        score += 3000
    if record.source == "database":
        score += 20
    return score


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

    def resolve_asset_strict(self, requested_name: str, semantic_role: str) -> T2AssetRecord:
        """Resolve an AI species hypothesis without semantic-role substitution."""
        candidates: list[T2AssetRecord] = []
        seen: set[str] = set()
        for term in _strict_search_terms(requested_name):
            for record in self.catalog.search_max_assets(term, limit=100, require_existing_file=True):
                key = str(record.file_path).casefold()
                if key not in seen:
                    seen.add(key)
                    candidates.append(record)
        if not candidates:
            diagnostics = self.catalog.diagnostics()
            roots = diagnostics.get("library_roots") or []
            raise Stage8AssetResolutionError(
                "No strict T2 .max asset found for AI species "
                f"'{requested_name}' (role={semantic_role}). "
                f"T2 database={diagnostics.get('database')}; library_roots={roots}"
            )

        scored = [
            (_strict_candidate_score(record, requested_name), record)
            for record in candidates
            if _asset_matches_semantic_role(record, semantic_role)
        ]
        if not scored:
            buckets = sorted({_asset_bucket(record) for record in candidates})
            raise Stage8AssetResolutionError(
                f"T2 candidates for AI species '{requested_name}' were rejected by semantic asset category "
                f"compatibility (role={semantic_role}, candidate_categories={buckets})."
            )
        best_score = max(score for score, _record in scored)
        if best_score <= 0:
            raise Stage8AssetResolutionError(
                f"T2 candidates were found for AI species '{requested_name}', "
                "but none had a lexical species/name match."
            )
        for score, record in scored:
            if score == best_score:
                return record
        raise AssertionError("strict asset ranking produced no winner")

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

    def list_geometry_source_names(
        self,
        forest_name: str,
        *,
        preflight: bool = True,
        max_items: int = 256,
    ) -> tuple[str, ...]:
        """Return current Forest Geometry source names without mutating the scene."""
        names: list[str] = []
        for index in range(1, int(max_items) + 1):
            try:
                row = self.control_service.get_array_element(
                    forest_name,
                    "namelist",
                    index,
                    preflight=preflight if index == 1 else False,
                )
            except Exception:
                break
            value = str((row or {}).get("value") or "").strip()
            if not value:
                break
            names.append(value)
        return tuple(names)

    def merge_resolved_asset(
        self,
        *,
        asset_path: str | Path,
        requested_name: str,
        semantic_role: str,
        geometry_count: int,
    ) -> dict[str, Any]:
        """Merge an already-resolved T2 asset exactly once when it is missing."""
        path = Path(asset_path)
        data = self._invoke_merge(path, append=int(geometry_count) > 0)
        return {
            "requested_name": str(requested_name),
            "semantic_role": str(semantic_role),
            "asset_path": str(path),
            "source_name": str(data.get("source_name") or ""),
            "geometry_index": int(data.get("geometry_index") or (int(geometry_count) + 1)),
            "merge": data,
            "verified": True,
        }
