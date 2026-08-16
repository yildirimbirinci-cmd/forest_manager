from forest_manager.site_model import CadParserAdapter, ProjectSource, ProjectSourceKind, SemanticRole


def test_cad_parser_adapter_normalizes_dxf_style_payload():
    source = ProjectSource("cad-main", ProjectSourceKind.CAD, "site.dxf")
    batch = CadParserAdapter().adapt(
        source,
        [
            {
                "handle": "A7",
                "type": "LWPOLYLINE",
                "vertices": [(0, 0), (8, 0), (8, 3)],
                "layer": "FRONT_EDGE",
                "semantic_role": "front_boundary",
                "semantic_confidence": 0.92,
            }
        ],
    )
    entity = batch.entities[0]
    assert entity.locator.entity_id == "A7"
    assert entity.locator.layer == "FRONT_EDGE"
    assert entity.kind.value == "polyline"
    assert entity.semantic_role is SemanticRole.FRONT_BOUNDARY
    assert entity.metadata["parser_primitive_type"] == "LWPOLYLINE"
