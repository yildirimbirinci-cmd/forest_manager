import inspect

import forest_manager.forest_control.stage8_asset_resolution as module


def test_strict_score_requires_leading_token_for_multiword_hypotheses():
    source = inspect.getsource(module._strict_candidate_score)
    assert "len(requested_words) >= 2" in source
    assert "requested_words[0] not in record_words" in source
    assert "return 0" in source


def test_semantic_asset_bucket_filter_still_exists():
    source = inspect.getsource(module.Stage8T2AssetResolver.resolve_asset_strict)
    assert "_asset_matches_semantic_role" in source
