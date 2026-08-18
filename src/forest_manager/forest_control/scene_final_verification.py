from __future__ import annotations

from typing import Any, Mapping


def summarize_execution_lineage(result: Mapping[str, Any], expected_groups: int) -> dict[str, Any]:
    rows = [row for row in (result.get("execution_lineage") or []) if isinstance(row, Mapping)]
    execution_group_count = int(result.get("execution_group_count") or 0)
    execution_group_ids = [
        str(value) for value in (result.get("execution_group_ids") or []) if str(value)
    ]
    resolved_expected_groups = execution_group_count or len(execution_group_ids) or int(expected_groups or 0)
    group_ids = [str(row.get("group_id") or "") for row in rows]
    species_ids: list[int] = []
    color_ids: list[tuple[int, int, int]] = []
    generated_positive = 0
    all_verified = True

    for row in rows:
        row_verified = row.get("verified") is True
        all_verified = all_verified and row_verified
        generated_mode = str(row.get("generated_item_verification_mode") or "").strip()
        if int(row.get("generated_items") or 0) > 0 or (
            row_verified and generated_mode in {"single_forest_binding", "map_free_total_binding"}
        ):
            generated_positive += 1
        for value in row.get("species_ids") or []:
            species_ids.append(int(value))
        for value in row.get("color_ids") or []:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                color_ids.append((int(value[0]), int(value[1]), int(value[2])))

    unique_group_ids = len(set(group_ids)) == len(group_ids)
    unique_species = len(species_ids) == len(set(species_ids))
    unique_colors = len(color_ids) == len(set(color_ids))
    map_free_random = bool(rows) and all(str(row.get("diversity_binding_mode") or "") == "map_free_random" for row in rows)
    color_contract_ok = map_free_random or (len(color_ids) >= resolved_expected_groups and unique_colors)
    complete = (
        resolved_expected_groups > 0
        and len(rows) == resolved_expected_groups
        and len(group_ids) == resolved_expected_groups
        and unique_group_ids
        and all_verified
        and generated_positive == resolved_expected_groups
        and len(species_ids) >= resolved_expected_groups
        and unique_species
        and color_contract_ok
    )
    return {
        "verified": complete,
        "expected_group_count": resolved_expected_groups,
        "lineage_count": len(rows),
        "generated_positive_count": generated_positive,
        "unique_group_ids": unique_group_ids,
        "unique_species_ids": unique_species,
        "unique_color_ids": unique_colors,
        "diversity_binding_mode": "map_free_random" if map_free_random else "color_id_map",
        "color_contract_ok": color_contract_ok,
        "species_ids": species_ids,
        "color_ids": [list(value) for value in color_ids],
    }
