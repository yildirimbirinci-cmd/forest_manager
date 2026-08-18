from forest_manager.forest_control.wall_edge_annotations import (
    normalize_wall_edge_annotation,
    read_wall_edge_annotation,
    remove_wall_edge_annotation,
    upsert_wall_edge_annotation,
)


def test_wall_segments_define_all_remaining_segments_as_walkway_open():
    annotation = normalize_wall_edge_annotation({
        "node_name": "Line001", "spline_index": 1, "segment_count": 8, "selected_segments": [2, 3, 7]
    })
    assert annotation.wall_segments == (2, 3, 7)
    assert annotation.walkway_open_segments == (1, 4, 5, 6, 8)


def test_wall_edge_annotation_persists_as_structured_scene_manifest_data():
    manifest = {"groups": []}
    annotation = normalize_wall_edge_annotation({
        "node_name": "Line001", "spline_index": 1, "segment_count": 6, "selected_segments": [5, 6]
    })
    upsert_wall_edge_annotation(manifest, annotation)
    assert read_wall_edge_annotation(manifest, "Line001") == annotation
    payload = manifest["site_annotations"]["wall_edges"]["Line001"]
    assert payload["default_unmarked_role"] == "walkway_open_edge"
    assert payload["wall_edge_source"] == "artist_3ds_max_segment_selection"


def test_wall_edge_clear_is_selective():
    manifest = {"groups": []}
    a = normalize_wall_edge_annotation({"node_name":"Line001","spline_index":1,"segment_count":4,"selected_segments":[1]})
    b = normalize_wall_edge_annotation({"node_name":"Line002","spline_index":1,"segment_count":4,"selected_segments":[2]})
    upsert_wall_edge_annotation(manifest,a); upsert_wall_edge_annotation(manifest,b)
    assert remove_wall_edge_annotation(manifest,"Line001") is True
    assert read_wall_edge_annotation(manifest,"Line001") is None
    assert read_wall_edge_annotation(manifest,"Line002") == b
