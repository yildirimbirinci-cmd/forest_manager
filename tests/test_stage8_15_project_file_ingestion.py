from __future__ import annotations

import pytest

from forest_manager.site_model import ProjectFileIngestionService, SiteModelService


def test_real_dxf_file_can_flow_into_site_model(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "site.dxf"
    document = ezdxf.new("R2010")
    document.modelspace().add_line((1, 2, 0), (3, 4, 0), dxfattribs={"layer": "EDGE"})
    document.saveas(path)

    service = SiteModelService()
    result = ProjectFileIngestionService().import_file(service, path, source_id="site-plan")

    assert len(result.ingestion.geometry_ids) == 1
    geometry = service.geometry(result.ingestion.geometry_ids[0])
    assert geometry.metadata["project_source_id"] == "site-plan"
    assert geometry.metadata["source_layer"] == "EDGE"
    assert geometry.metadata["cad_entity_type"] == "LINE"
