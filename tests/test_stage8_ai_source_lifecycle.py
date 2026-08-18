from pathlib import Path

from forest_manager.forest_control.official_planting_pipeline import (
    OfficialStage8PlantingPipeline,
    PreparedOfficialPlantingPlan,
)


class FakeResolver:
    def __init__(self, names):
        self.names = list(names)
        self.merges = []

    def list_geometry_source_names(self, forest_name, *, preflight=True, max_items=256):
        return tuple(self.names)

    def merge_resolved_asset(self, *, asset_path, requested_name, semantic_role, geometry_count):
        name = Path(asset_path).stem
        self.names.append(name)
        row = {
            "requested_name": requested_name,
            "semantic_role": semantic_role,
            "asset_path": str(asset_path),
            "source_name": name,
            "geometry_index": geometry_count + 1,
            "verified": True,
        }
        self.merges.append(row)
        return row


def _prepared(*rows):
    groups = [
        {
            "group_id": row[0],
            "semantic_role": row[1],
            "resolved_name": row[2],
            "requested_name": row[3],
            "asset_path": row[4],
        }
        for row in rows
    ]
    return PreparedOfficialPlantingPlan(
        resolved_plan=object(),
        manifest={"primary_forest": "FM_Forest_001", "groups": []},
        asset_resolution=tuple(groups),
    )


def test_inspection_reuses_existing_sources_without_merging():
    resolver = FakeResolver([
        "Rudbeckia 'Goldsturm' (Coneflower)",
        "Rosa canina (Dog rose)",
    ])
    pipeline = OfficialStage8PlantingPipeline(resolver=resolver)
    prepared = _prepared(
        ("g1", "flower_accent", "Rudbeckia 'Goldsturm' (Coneflower)", "purple coneflower", "C:/T2/Rudbeckia 'Goldsturm' (Coneflower).max"),
        ("g2", "flower_accent", "Rosa canina (Dog rose)", "roses", "C:/T2/Rosa canina (Dog rose).max"),
    )
    report = pipeline.inspect_scene_sources(prepared)
    assert report.ready is True
    assert report.reuse_sources == (
        "Rudbeckia 'Goldsturm' (Coneflower)",
        "Rosa canina (Dog rose)",
    )
    assert report.missing_sources == ()
    assert resolver.merges == []


def test_ensure_scene_sources_merges_only_missing_assets_once():
    resolver = FakeResolver(["Rudbeckia 'Goldsturm' (Coneflower)"])
    pipeline = OfficialStage8PlantingPipeline(resolver=resolver)
    prepared = _prepared(
        ("g1", "flower_accent", "Rudbeckia 'Goldsturm' (Coneflower)", "purple coneflower", "C:/T2/Rudbeckia 'Goldsturm' (Coneflower).max"),
        ("g2", "flower_accent", "Rosa canina (Dog rose)", "roses", "C:/T2/Rosa canina (Dog rose).max"),
    )
    first = pipeline.ensure_scene_sources(prepared)
    second = pipeline.ensure_scene_sources(prepared, preflight=False)
    assert first["reuse_sources"] == ["Rudbeckia 'Goldsturm' (Coneflower)"]
    assert first["merge_count"] == 1
    assert second["merge_count"] == 0
    assert len(resolver.merges) == 1
