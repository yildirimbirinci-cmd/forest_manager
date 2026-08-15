from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class LayerRule:
    role: str
    layer_order: int
    description: str
    target_behavior: str


_RULES: tuple[tuple[tuple[str, ...], LayerRule], ...] = (
    (
        ("lavandula", "lavender"),
        LayerRule(
            role="foreground_mass",
            layer_order=10,
            description="Low repeated planting mass / foreground carpet role.",
            target_behavior="preserve current probability; dense visual mass; native scale variation only",
        ),
    ),
    (
        ("butomus", "flowering", "flower"),
        LayerRule(
            role="mid_accent",
            layer_order=20,
            description="Flowering middle layer used as visible accent among the mass planting.",
            target_behavior="preserve current probability; accent distribution; native scale variation only",
        ),
    ),
    (
        ("bush", "berberis", "shrub"),
        LayerRule(
            role="structural_shrub",
            layer_order=30,
            description="Structural shrub layer that provides larger repeating planting masses.",
            target_behavior="preserve current probability; structural grouping; native scale variation only",
        ),
    ),
)


def _classify_geometry(name: str) -> LayerRule:
    lowered = name.casefold()
    for tokens, rule in _RULES:
        if any(token in lowered for token in tokens):
            return rule
    return LayerRule(
        role="unclassified",
        layer_order=90,
        description="No deterministic vegetation layer rule matched this geometry.",
        target_behavior="preserve current Forest behavior until explicitly classified",
    )


def build_layered_composition_plan(context: dict, transform_state: dict | None = None) -> dict:
    geometry = context.get("geometry") or {}
    density = context.get("density") or {}
    area = context.get("selection_area") or {}

    names = list(geometry.get("geometry_names") or [])
    probabilities = list(geometry.get("probabilities") or [])
    if not names:
        raise RuntimeError("Composition context contains no Forest geometry.")
    if len(names) != len(probabilities):
        raise RuntimeError("Geometry/probability count mismatch.")

    items = []
    for index, (name, probability) in enumerate(zip(names, probabilities), start=1):
        rule = _classify_geometry(str(name))
        item = {
            "geometry_index": index,
            "geometry_name": str(name),
            "current_probability": float(probability),
            **asdict(rule),
        }
        items.append(item)

    items.sort(key=lambda item: (item["layer_order"], item["geometry_index"]))

    transform_state = transform_state or {}
    return {
        "policy": "semantic_layer_roles_v1",
        "read_only": True,
        "forest_name": context.get("forest_name"),
        "area_square_meters": area.get("area_square_meters"),
        "density_meters_x": density.get("meters_x"),
        "density_meters_y": density.get("meters_y"),
        "probability_total": round(sum(float(v) for v in probabilities), 4),
        "preserve_density": True,
        "preserve_probabilities": True,
        "preserve_native_scale_variation": True,
        "transform_state": {
            "applyscale": transform_state.get("applyscale"),
            "applyrotation": transform_state.get("applyrotation"),
            "applytranslation": transform_state.get("applytranslation"),
            "scalexmin": transform_state.get("scalexmin"),
            "scalexmax": transform_state.get("scalexmax"),
            "scaleymin": transform_state.get("scaleymin"),
            "scaleymax": transform_state.get("scaleymax"),
            "scalezmin": transform_state.get("scalezmin"),
            "scalezmax": transform_state.get("scalezmax"),
            "scalelock": transform_state.get("scalelock"),
        },
        "layers": items,
        "next_apply_scope": {
            "allowed": [
                "assign deterministic semantic layer roles",
                "introduce grouping/distribution rules only after explicit preview approval",
            ],
            "protected": [
                "75.0 m density",
                "current geometry probabilities",
                "native scale limits",
                "rotation disabled",
                "translation disabled",
                "user spline and unrelated scene objects",
            ],
        },
        "verified": True,
    }
