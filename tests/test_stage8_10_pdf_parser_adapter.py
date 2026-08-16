import pytest

from forest_manager.site_model import ParserAdapterError, PdfParserAdapter, ProjectSource, ProjectSourceKind


def test_pdf_parser_adapter_preserves_page_and_promotes_closed_path_to_region():
    source = ProjectSource("pdf-main", ProjectSourceKind.PDF, "plan.pdf", page_count=2)
    batch = PdfParserAdapter().adapt(
        source,
        [{"id": "path-9", "type": "path", "points": [(0, 0), (5, 0), (5, 5)], "closed": True, "page_index": 1}],
    )
    entity = batch.entities[0]
    assert entity.locator.page_index == 1
    assert entity.kind.value == "region"
    assert entity.closed is True


def test_pdf_parser_adapter_rejects_page_outside_document():
    source = ProjectSource("pdf-main", ProjectSourceKind.PDF, "plan.pdf", page_count=1)
    with pytest.raises(ParserAdapterError, match="outside"):
        PdfParserAdapter().adapt(
            source,
            [{"id": "x", "type": "line", "points": [(0, 0), (1, 0)], "page_index": 1}],
        )
