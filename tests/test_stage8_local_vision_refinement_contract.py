from __future__ import annotations

import inspect

from forest_manager.site_model.local_vision_provider import LocalVisionProvider


def test_analyze_has_exactly_one_first_pass_and_one_refinement_request():
    source = inspect.getsource(LocalVisionProvider.analyze)
    assert source.count("self._request_groups(") == 2
    assert "self._refinement_prompt(first_groups)" in source
    assert "self._audit_refined_groups(refined_groups)" in source


def test_refinement_stays_loopback_and_read_only_provider_layer():
    source = inspect.getsource(LocalVisionProvider)
    assert "send_command(" not in source
    assert "execute_manifest" not in source
    assert "merge_t2_asset" not in source


def test_refinement_audit_is_nonblocking_and_leaves_exclusion_to_t2_resolution():
    source = inspect.getsource(LocalVisionProvider._audit_refined_groups)
    assert "raise LocalVisionProviderError" not in source
    assert "no_species_candidates" in source
