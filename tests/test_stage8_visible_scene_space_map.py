from __future__ import annotations

from PIL import Image

from forest_manager.forest_control.plant_group_execution import _scene_space_semantic_diversity_map, _species_color_palette


def _groups():
    return [
        {"group_id":"1","semantic_role":"flower_accent","coverage_weight":0.33},
        {"group_id":"2","semantic_role":"flower_accent","coverage_weight":0.33},
        {"group_id":"3","semantic_role":"groundcover","coverage_weight":0.24},
        {"group_id":"4","semantic_role":"structural_shrub","coverage_weight":0.05},
        {"group_id":"5","semantic_role":"tree_canopy","coverage_weight":0.05},
    ]


def test_scene_space_map_contains_all_five_group_color_ids_inside_polygon():
    image=_scene_space_semantic_diversity_map(_groups(),size=(160,80),site_polygon_normalized=[(0,0),(1,0),(1,1),(0,1)])
    try:
        colors=set(image.getdata())
        palette=set(_species_color_palette(5))
        assert palette.issubset(colors)
        assert (0,0,0) not in colors
    finally:
        image.close()


def test_scene_space_map_keeps_outside_polygon_black():
    image=_scene_space_semantic_diversity_map(_groups(),size=(100,100),site_polygon_normalized=[(0.2,0.2),(0.8,0.2),(0.8,0.8),(0.2,0.8)])
    try:
        assert image.getpixel((0,0)) == (0,0,0)
        assert image.getpixel((50,50)) != (0,0,0)
    finally:
        image.close()
