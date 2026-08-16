from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "composition_stage5d1.py"


def test_apply_uses_existing_probability_bridge_command():
    source = APP.read_text(encoding="utf-8")
    assert 'send_command("SET_GEOMETRY_PROBABILITIES|" + values)' in source


def test_apply_verifies_density_did_not_change():
    source = APP.read_text(encoding="utf-8")
    assert "Density changed while applying semantic probabilities (X)." in source
    assert "Density changed while applying semantic probabilities (Y)." in source


def test_default_semantic_text_matches_current_reference_observation():
    source = APP.read_text(encoding="utf-8")
    assert 'DEFAULT_TEXT = "PLANTS: lavender purple white lillies flowers shrubs plants."' in source


def test_preview_is_default_and_apply_is_explicit():
    source = APP.read_text(encoding="utf-8")
    assert 'parser.add_argument("--apply", action="store_true")' in source
    assert '"mode": "apply" if args.apply else "preview"' in source
