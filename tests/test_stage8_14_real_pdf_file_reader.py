from __future__ import annotations

import pytest

from forest_manager.site_model import PdfFileReader, ProjectSourceKind


def test_real_pdf_reader_extracts_vector_drawings(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "plan.pdf"
    document = fitz.open()
    page = document.new_page(width=200, height=200)
    shape = page.new_shape()
    shape.draw_line((10, 10), (100, 10))
    shape.draw_rect((20, 20, 80, 80))
    shape.finish()
    shape.commit()
    document.save(path)
    document.close()

    batch = PdfFileReader().read(path, source_id="pdf-1")

    assert batch.source.kind is ProjectSourceKind.PDF
    assert batch.source.page_count == 1
    assert batch.source.metadata["reader_backend"] == "PyMuPDF"
    assert batch.entities
    assert all(entity.locator.page_index == 0 for entity in batch.entities)
    assert all(entity.metadata["pdf_drawing_index"] >= 0 for entity in batch.entities)
