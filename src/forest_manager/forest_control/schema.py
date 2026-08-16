from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ForestSemanticField:
    domain: str
    name: str
    raw_properties: tuple[str, ...]
    access: str
    notes: str = ""


@dataclass(frozen=True)
class ForestSemanticDomain:
    name: str
    fields: tuple[ForestSemanticField, ...]


_DOMAINS: tuple[ForestSemanticDomain, ...] = (
    ForestSemanticDomain("geometry", (
        ForestSemanticField("geometry", "sources", ("cobjlist", "matlist", "namelist", "coloridlist", "geomlist", "tempidlist", "tempnamelist", "widthlist", "heightlist", "ScaleList", "zoffsetlist", "centerlist", "radiuslist", "specidlist", "usemeshdimlist", "conamelist", "includechildlist", "keepgrouplist", "nongeomlist", "old_problist", "problist"), "atomic_adapter_required", "Synchronized geometry arrays must never be mutated independently."),
        ForestSemanticField("geometry", "global_scale", ("globscale",), "scalar"),
        ForestSemanticField("geometry", "global_size", ("globsize", "width", "height"), "scalar_group"),
    )),
    ForestSemanticDomain("distribution", (
        ForestSemanticField("distribution", "density", ("units_x", "units_y", "pixels_x", "pixels_y", "lock_ratio"), "scalar_group"),
        ForestSemanticField("distribution", "distribution_map", ("distmap", "mapname", "distmapchan", "densityMap"), "bitmap_reference_group"),
        ForestSemanticField("distribution", "cluster", ("clusize", "clurough", "clunoise", "cluedge"), "scalar_group"),
        ForestSemanticField("distribution", "path_distribution", ("distpathnodes", "distpathmode", "distpathgeomid", "distpathspacing", "distpathoffset", "distpathrandpos", "distpathxfollow", "distpathzfollow"), "node_reference_group"),
        ForestSemanticField("distribution", "reference_distribution", ("distrefnodes", "distrefmode", "distrefgetrot", "distrefgetscale", "distrefnumitems", "distrefrandpos", "distrefmatid", "distrefmatchname", "distrefmatchregex"), "node_reference_group"),
        ForestSemanticField("distribution", "extended_distribution_controls", ("distmode", "divers", "divmapchan", "divmapnoise", "drotation", "maxdensity", "randstacked", "seed", "seedtype", "sepsubsplines", "threshold"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
        ForestSemanticField("distribution", "diversity_map_reference", ("divtmap",), "read_only", "Runtime inventory exposes UndefinedClass and no writable reference contract."),
    )),
    ForestSemanticDomain("areas", (
        ForestSemanticField("areas", "area_records", ("aridlist", "pf_aractivelist", "arnamelist", "arnodelist", "arnodenamelist", "artypelist", "arincexclist", "arresollist", "arslicelist", "arslicetoplist", "arwidthlist", "arforceopenlist", "armaplist", "arscalelist", "arthresholdlist", "arsurfidlist", "arflafdenslist", "arflafscalist", "arflinvlist", "arselspeclist", "arspeclist", "arpaintlist", "arboundchecklist", "arprojectlist", "arshapelist", "arobscalelist", "arlinkidlist", "arscalemin", "arscalemax", "arzoffset"), "area_record_adapter", "Synchronized Area arrays are exposed through the atomic AreaBoundaryRecordAdapter; direct raw-array editing remains hidden from the artist UI."),
    )),
    ForestSemanticDomain("transform", (
        ForestSemanticField("transform", "translation", ("applytranslation", "transxmin", "transymin", "transzmin", "transxmax", "transymax", "transzmax", "transmapx", "transmapy", "transmapz", "transmap", "transmapchan", "transcolormap", "transprobmap"), "scalar_group"),
        ForestSemanticField("transform", "rotation", ("applyrotation", "xrotmin", "xrotmax", "yrotmin", "yrotmax", "zrotmin", "zrotmax", "rotmapx", "rotmapy", "rotmapz", "userotprobcurve", "rotprobcurve", "rotmap", "rotmapchan", "rotcolormap", "rotprobmap"), "mixed_group", "rotprobcurve is opaque/read-only on this Forest Pack build."),
        ForestSemanticField("transform", "scale", ("applyscale", "scalexmax", "scalexmin", "scaleymax", "scaleymin", "scalezmax", "scalezmin", "scamapx", "scamapy", "scamapz", "usescaprobcurve", "scaprobcurve", "scamap", "scamapchan", "scacolormap", "scaprobmap", "scalelock"), "mixed_group", "scaprobcurve is opaque/read-only on this Forest Pack build."),
        ForestSemanticField("transform", "extended_transform_controls", ("mirror", "offset_X", "offset_Y", "sdgizmo"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
    )),
    ForestSemanticDomain("surface", (
        ForestSemanticField("surface", "surface_limits", ("surflist", "surflink", "altlimited", "altmax", "altmin", "surfaltdens", "surfaltscal", "slopelimited", "slopemax", "slopemin", "surfslodens", "surfsloscal", "surfanim", "linkeditsurf", "direction", "surfmode", "uvalign", "uvscalex", "uvscaley", "uvmultscalex", "uvmultscaley"), "mixed_group"),
        ForestSemanticField("surface", "surface_falloff_curves", ("spdenscurve", "spscalcurve", "Surface_Falloff_Curves"), "read_only_opaque", "Forest Pack exposes CurveClass/SubAnim shells without writable controllers."),
        ForestSemanticField("surface", "extended_surface_controls", ("scalelope", "spdensact", "spdensexc", "spdensinc", "spscalact", "spscalexc", "spscalinc", "spscalz"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
    )),
    ForestSemanticDomain("camera", (
        ForestSemanticField("camera", "camera_limits", ("camera", "lookattarget", "camlimit", "uselookat", "camlookat", "camlod", "camloddist", "camlodlookat", "camwidth", "camnear", "camfar", "cambho"), "mixed_group"),
        ForestSemanticField("camera", "camera_curves", ("camdenscurve", "camscacurve"), "read_only_opaque"),
        ForestSemanticField("camera", "extended_camera_controls", ("camdensact", "camdensear", "camdensfar", "camscaact"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
    )),
    ForestSemanticDomain("material", (
        ForestSemanticField("material", "tint", ("tintmixmode", "tintcolor1", "tintcolor2", "tintmin", "tintmax", "tintmode", "tintmap", "tintmapmode", "tintmapchan"), "mixed_group"),
        ForestSemanticField("material", "material_adjustment", ("mathue", "matsaturation", "matbrightness", "matapply", "matapplycolor", "matrangewidth"), "scalar_color_group"),
        ForestSemanticField("material", "geometry_texture_reference", ("geomtex",), "read_only", "UndefinedClass in current scene; no writable texture-reference contract."),
    )),
    ForestSemanticDomain("animation", (
        ForestSemanticField("animation", "animation_range", ("animation", "animsoffset", "animsamples", "animonlyrend", "animap", "animapchan", "animstart", "animend"), "mixed_group"),
    )),
    ForestSemanticDomain("display", (
        ForestSemanticField("display", "viewport", ("vmesh", "geomtexid", "vtype", "adaptfaces", "cloudcolorid", "cloudens", "vmaxitems"), "mixed_group", "geomtexid is runtime-verified read-only; the remaining viewport fields are writable."),
        ForestSemanticField("display", "render", ("rmesh", "rskip", "opacity", "wireFrame", "rtype", "renderMode", "rmaxitems", "maxfaces"), "scalar_group"),
        ForestSemanticField("display", "extended_viewport_controls", ("collpreview", "hidecustom", "iconSize", "radius"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
        ForestSemanticField("display", "fast_opacity", ("fastopac",), "read_only", "Runtime setter rejects writes on this Forest Pack build."),
        ForestSemanticField("display", "extended_render_controls", ("opaclevel", "pf_efonlyrender", "ssitself"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
        ForestSemanticField("display", "render_identifier", ("renderid",), "read_only", "Runtime setter rejects writes on this Forest Pack build."),
    )),
    ForestSemanticDomain("collision", (
        ForestSemanticField("collision", "collision_controls", ("collheight", "mode"), "scalar_group", "Runtime-verified writable in Stage 5D.51."),
    )),
    ForestSemanticDomain("effects", (
        ForestSemanticField("effects", "effect_records", ("efidlist", "efnamelist", "efxmllist", "efenablelist", "efselspeclist", "efspeclist", "efpaid", "efpaeffid", "efpatype", "efpaname", "efpalimit", "efpadesc", "efpanumtype", "efpaintval", "efpaintmin", "efpaintmax", "efpaintdef", "efpafloatval", "efpafloatmin", "efpafloatmax", "efpafloatdef", "efpaunitval", "efpaunitmin", "efpaunitmax", "efpaunitdef", "efpainode", "efpaspline", "efpacontref", "efpacontanim", "efpacontype", "efpatexmap", "efpacurve"), "read_only_until_record_adapter"),
        ForestSemanticField("effects", "effect_curves", ("Effect_Curves",), "read_only_opaque"),
    )),
)


def semantic_domains() -> tuple[ForestSemanticDomain, ...]:
    return _DOMAINS


def semantic_fields() -> tuple[ForestSemanticField, ...]:
    return tuple(field for domain in _DOMAINS for field in domain.fields)


def find_semantic_field(domain: str, name: str) -> ForestSemanticField:
    for field in semantic_fields():
        if field.domain == domain and field.name == name:
            return field
    raise KeyError(f"Unknown Forest semantic field: {domain}.{name}")


def raw_property_coverage(properties: Iterable[str]) -> dict[str, object]:
    available = set(properties)
    declared = {raw for field in semantic_fields() for raw in field.raw_properties}
    covered = sorted(available & declared)
    undeclared = sorted(available - declared)
    missing = sorted(declared - available)
    return {
        "available_count": len(available),
        "declared_count": len(declared),
        "covered_count": len(covered),
        "covered": covered,
        "undeclared": undeclared,
        "declared_but_missing": missing,
    }
