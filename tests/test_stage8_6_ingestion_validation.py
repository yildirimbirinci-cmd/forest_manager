from __future__ import annotations

import pytest

from forest_manager.site_model import ImportBatch, ImportedEntity, ProjectSource, ProjectSourceKind


def test_import_batch_rejects_cross_source_entities():
    source = ProjectSource("cad-a", ProjectSourceKind.CAD, "a.dxf")
    entity = ImportedEntity.create(source_id="cad-b", entity_id="1", kind="line", points=[(0, 0), (1, 0)])
    with pytest.raises(ValueError, match="does not match"):
        ImportBatch(source, (entity,))


def test_import_batch_rejects_duplicate_stable_entity_identity():
    source = ProjectSource("pdf-a", ProjectSourceKind.PDF, "a.pdf")
    first = ImportedEntity.create(source_id="pdf-a", entity_id="9", kind="line", points=[(0, 0), (1, 0)], page_index=0)
    second = ImportedEntity.create(source_id="pdf-a", entity_id="9", kind="line", points=[(2, 0), (3, 0)], page_index=0)
    with pytest.raises(ValueError, match="duplicate imported entity"):
        ImportBatch(source, (first, second))
