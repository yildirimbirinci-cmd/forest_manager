from forest_manager.forest_control.candidate_review import CANDIDATE_DOMAIN_MAP
from forest_manager.forest_control.schema import semantic_fields
from forest_manager.forest_control.undeclared_classification import USER_CONTROL_CANDIDATES


def _raw_access_map():
    result = {}
    for field in semantic_fields():
        for raw in field.raw_properties:
            result[raw] = field.access
    return result


def test_all_40_candidates_are_declared_in_semantic_schema():
    raw_access = _raw_access_map()
    assert len(USER_CONTROL_CANDIDATES) == 40
    assert set(CANDIDATE_DOMAIN_MAP) == set(USER_CONTROL_CANDIDATES)
    assert set(USER_CONTROL_CANDIDATES) <= set(raw_access)


def test_candidate_promotion_contract_is_36_writable_and_4_read_only():
    raw_access = _raw_access_map()
    read_only = {name for name in USER_CONTROL_CANDIDATES if raw_access[name] == "read_only"}
    assert read_only == {"divtmap", "geomtex", "fastopac", "renderid"}
    assert len(USER_CONTROL_CANDIDATES - read_only) == 36


def test_candidate_domains_match_promoted_schema_domains():
    raw_domain = {}
    for field in semantic_fields():
        for raw in field.raw_properties:
            raw_domain[raw] = field.domain
    normalized = {"render": "display"}
    for name, candidate_domain in CANDIDATE_DOMAIN_MAP.items():
        expected = normalized.get(candidate_domain, candidate_domain)
        assert raw_domain[name] == expected
