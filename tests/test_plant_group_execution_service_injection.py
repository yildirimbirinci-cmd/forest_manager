from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "forest_manager" / "forest_control" / "plant_group_execution.py"


def test_area_helpers_receive_explicit_service_dependency():
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, "plant_group_execution.py", "exec")

    assert """def _normalize_requested_spline_areas(
    forest_name: str,
    requested_zero_indices: list[int],
    *,
    service: ForestPackControlService,
)""" in source

    assert """_set_array_bool(
            forest_name,
            "pf_aractivelist",
            zero_index,
            zero_index in requested,
            service=service,
        )""" in source

    assert """area_normalization = _normalize_requested_spline_areas(
        forest_name,
        requested_base_area_indices,
        service=svc,
    )""" in source
