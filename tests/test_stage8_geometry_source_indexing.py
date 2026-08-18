from __future__ import annotations

from forest_manager.forest_control.stage8_asset_resolution import Stage8T2AssetResolver


class FakeService:
    def __init__(self):
        self.calls = []
        self.values = {
            0: "Lavandula angustifolia 'Hidcote' (Lavender)",
            1: "Rosa canina (Dog rose)",
            2: "Carex nigra (Sedge)",
        }

    def get_array_element(self, forest_name, property_name, index, *, preflight=True):
        self.calls.append((forest_name, property_name, index, preflight))
        if index not in self.values:
            raise RuntimeError("end")
        return {"value": self.values[index]}


def test_geometry_source_listing_starts_at_zero_and_keeps_first_source():
    service = FakeService()
    resolver = Stage8T2AssetResolver(catalog=object(), control_service=service)

    names = resolver.list_geometry_source_names("FM_Forest_001", preflight=True)

    assert names == (
        "Lavandula angustifolia 'Hidcote' (Lavender)",
        "Rosa canina (Dog rose)",
        "Carex nigra (Sedge)",
    )
    assert service.calls[0] == ("FM_Forest_001", "namelist", 0, True)
    assert service.calls[1][2:] == (1, False)


def test_existing_first_geometry_source_is_visible_to_reuse_checks():
    resolver = Stage8T2AssetResolver(catalog=object(), control_service=FakeService())
    names = resolver.list_geometry_source_names("FM_Forest_001", preflight=False)
    assert "Lavandula angustifolia 'Hidcote' (Lavender)" in names
