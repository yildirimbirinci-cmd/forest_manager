from __future__ import annotations

import pytest

from forest_manager.site_model import CadFileReader, GeometryKind, ProjectSourceKind


def test_real_dxf_reader_extracts_supported_entities(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "site.dxf"
    document = ezdxf.new("R2010")
    document.header["$INSUNITS"] = 6
    modelspace = document.modelspace()
    modelspace.add_line((0, 0, 0), (10, 0, 0), dxfattribs={"layer": "BOUNDARY"})
    modelspace.add_lwpolyline([(0, 0), (5, 0), (5, 5)], close=True, dxfattribs={"layer": "PLANTING"})
    document.saveas(path)

    batch = CadFileReader().read(path, source_id="cad-1")

    assert batch.source.kind is ProjectSourceKind.CAD
    assert batch.source.metadata["reader_backend"] == "ezdxf"
    assert batch.source.metadata["dxf_insunits"] == 6
    assert len(batch.entities) == 2
    assert {entity.kind for entity in batch.entities} == {GeometryKind.LINE, GeometryKind.POLYLINE}
    assert {entity.locator.layer for entity in batch.entities} == {"BOUNDARY", "PLANTING"}
