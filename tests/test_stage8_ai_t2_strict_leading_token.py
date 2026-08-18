from pathlib import Path
from types import SimpleNamespace

from forest_manager.forest_control.stage8_asset_resolution import _strict_candidate_score


def _record(name: str):
    return SimpleNamespace(
        name=name,
        file_path=Path("C:/T2/02_Plants") / name / f"{name}.max",
        source="library_scan",
    )


def test_prunus_nigra_does_not_match_carex_nigra_by_epithet_only():
    assert _strict_candidate_score(_record("Carex nigra (Sedge)"), "Prunus 'Nigra'") == 0


def test_salvia_genus_fallback_remains_valid():
    assert _strict_candidate_score(_record("Salvia 'Little Spire' (Sage)"), "Salvia nemorosa") > 0


def test_rosa_genus_fallback_remains_valid():
    assert _strict_candidate_score(_record("Rosa canina (Dog rose)"), "Rosa 'Knock Out'") > 0


def test_carex_genus_fallback_remains_valid():
    assert _strict_candidate_score(_record("Carex nigra (Sedge)"), "Carex vulpinoidea") > 0


def test_multiword_common_hypothesis_cannot_match_only_trailing_word():
    assert _strict_candidate_score(_record("Rudbeckia 'Goldsturm' (Coneflower)"), "purple coneflower") == 0
