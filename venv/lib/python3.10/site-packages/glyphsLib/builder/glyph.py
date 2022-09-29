# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import itertools
import logging

import glyphsLib.glyphdata

from .. import GSLayer
from .builders import BRACKET_GLYPH_RE, BRACKET_GLYPH_SUFFIX_RE
from .common import from_loose_ufo_time, to_ufo_time
from .constants import (
    GLYPHLIB_PREFIX,
    GLYPHS_COLORS,
    PUBLIC_PREFIX,
    UFO2FT_COLOR_LAYER_MAPPING_KEY,
)

logger = logging.getLogger(__name__)

SCRIPT_LIB_KEY = GLYPHLIB_PREFIX + "script"
ORIGINAL_WIDTH_KEY = GLYPHLIB_PREFIX + "originalWidth"
BACKGROUND_WIDTH_KEY = GLYPHLIB_PREFIX + "backgroundWidth"


def _clone_layer(layer, paths=None, components=None):
    paths = paths if paths is not None else []
    components = components if components is not None else []
    if len(paths) == len(layer.paths) and len(components) == len(layer.components):
        return layer
    new_layer = GSLayer()
    new_layer.associatedMasterId = layer.associatedMasterId
    new_layer.parent = layer.parent
    new_layer.paths = paths
    new_layer.components = components
    new_layer.attributes = layer.attributes
    return new_layer


def to_ufo_glyph(self, ufo_glyph, layer, glyph, do_color_layers=True):  # noqa: C901
    """Add .glyphs metadata, paths, components, and anchors to a glyph."""
    ufo_font = self._sources[layer.associatedMasterId or layer.layerId].font

    if layer.layerId == layer.associatedMasterId and do_color_layers:
        # Here we handle color layers. If this is a master layer and the glyph
        # has color layers, add ufo2ft lib key with the layer mapping.

        # There are two kinds of color layers: first, color palette layers that
        # are handled below, which are used to build COLRv0 table. For color
        # palette layers, the layer mapping is a tuple of (layer name, palette
        # index), but we don’t know the final UFO layer names yet, so we use
        # Glyphs layer IDs and change them to layer names in
        # to_ufo_color_layer_names().
        # When building minimal UFOs, we instead collect color layers and later
        # add them as separate glyphs to the UFO font.

        if any(
            l._is_color_palette_layer()
            and l.associatedMasterId == layer.associatedMasterId
            for l in glyph.layers
        ):
            layerMapping = [
                (l.layerId, l._color_palette_index())
                for l in glyph.layers
                if l._is_color_palette_layer()
                and l.associatedMasterId == layer.associatedMasterId
            ]

            if not self.minimal:
                ufo_glyph.lib[UFO2FT_COLOR_LAYER_MAPPING_KEY] = layerMapping
            elif glyph.export:
                layers = []
                for layerId, colorId in layerMapping:
                    layers.append((glyph.layers[layerId], colorId))
                self._color_palette_layers.append(((glyph, layer), layers))

        if self.minimal:
            # The other kind of color layers supports solid colors and
            # gradients among other things, and we use it to build COLRv1
            # table.
            # For each color layer, we collect paths that has the same
            # attributes, then we make a clone of the layer for each group with
            # only the paths in this group. We do this splitting because a
            # COLRv1 layer can’t have multiple gradients or colors.
            color_layers = [
                l
                for l in glyph.layers
                if l.attributes.get("color")
                and l.associatedMasterId == layer.associatedMasterId
            ]
            if color_layers:
                layers = []
                for color_layer in color_layers:
                    # Group consecutive paths with same attributes together.
                    groups = [
                        list(g)
                        for k, g in itertools.groupby(
                            color_layer.paths, key=lambda p: p.attributes
                        )
                    ]
                    for paths in groups:
                        layers.append(_clone_layer(color_layer, paths=paths))

                    # Group components based on whether component glyph has
                    # color layers or not.
                    groups = [
                        (k, list(g))
                        for k, g in itertools.groupby(
                            color_layer.components,
                            key=lambda c: any(
                                l.attributes.get("color")
                                for l in c.component.layers
                                if l.associatedMasterId == layer.associatedMasterId
                            ),
                        )
                    ]
                    for has_color, components in groups:
                        if not has_color:
                            new_layer = _clone_layer(color_layer, components=components)
                            new_layer.attributes = {}
                            layers.append(new_layer)
                        else:
                            for c in components:
                                layers.append(_clone_layer(color_layer, components=[c]))

                self._color_layers.append(((glyph, layer), layers))

    ufo_glyph.unicodes = [int(uval, 16) for uval in glyph.unicodes]

    note = glyph.note
    if note is not None:
        ufo_glyph.note = note

    # Optimization: profiling glyphs2ufo of NotoSans-MM.glyphs (6000 glyphs) on a Mac
    # mini late 2014, Python 3.6.8, revealed that a whopping 17% of the time was spent
    # converting lastChange to UFO timestamps. I could not reproduce this on a Windows
    # 10/Python 3.7 setup, so this might be a platform thing. If-guarding anyway
    # because these timestamps are useless in a UFO scenario if you use Git.
    if (
        self.minimize_glyphs_diffs
        and self.font.customParameters["Disable Last Change"] is not True
        and glyph.lastChange is not None
    ):
        ufo_glyph.lib[GLYPHLIB_PREFIX + "lastChange"] = to_ufo_time(glyph.lastChange)

    color_index = glyph.color
    if color_index is not None:
        # .3f is enough precision to round-trip uint8 to float losslessly.
        # https://github.com/unified-font-object/ufo-spec/issues/61
        # #issuecomment-389759127
        if (
            isinstance(color_index, list)
            and len(color_index) == 4
            and all(0 <= v < 256 for v in color_index)
        ):
            ufo_glyph.markColor = ",".join(
                "0" if v == 0 else "1" if v == 255 else "{:.3f}".format(v / 255)
                for v in color_index
            )
        elif isinstance(color_index, int) and color_index in range(len(GLYPHS_COLORS)):
            ufo_glyph.markColor = GLYPHS_COLORS[color_index]
        else:
            logger.warning(
                "Glyph {}, layer {}: Invalid color index/tuple {}".format(
                    glyph.name, layer.name, color_index
                )
            )

    export = glyph.export
    if not export:
        if self.write_skipexportglyphs:
            if "public.skipExportGlyphs" not in self._designspace.lib:
                self._designspace.lib["public.skipExportGlyphs"] = []
            self._designspace.lib["public.skipExportGlyphs"].append(glyph.name)
        else:
            ufo_glyph.lib[GLYPHLIB_PREFIX + "Export"] = export

    # FIXME: (jany) next line should be an API of GSGlyph?
    glyphinfo = glyphsLib.glyphdata.get_glyph(ufo_glyph.name)
    if self.glyphdata is not None:
        custom = glyphsLib.glyphdata.get_glyph(ufo_glyph.name, self.glyphdata)
        production_name = glyph.production or (
            custom.production_name
            if custom.production_name != glyphinfo.production_name
            else None
        )
        category = glyph.category or (
            custom.category if custom.category != glyphinfo.category else None
        )
        subCategory = glyph.subCategory or (
            custom.subCategory if custom.subCategory != glyphinfo.subCategory else None
        )
        script = glyph.script or (
            custom.script if custom.script != glyphinfo.script else None
        )
    else:
        production_name, category, subCategory, script = (
            glyph.production,
            glyph.category,
            glyph.subCategory,
            glyph.script,
        )

    if production_name:
        # Make sure production names of bracket glyphs also get a BRACKET suffix.
        bracket_glyph_name = BRACKET_GLYPH_RE.match(ufo_glyph.name)
        prod_bracket_glyph_name = BRACKET_GLYPH_RE.match(production_name)
        if bracket_glyph_name and not prod_bracket_glyph_name:
            production_name += BRACKET_GLYPH_SUFFIX_RE.match(ufo_glyph.name).group(1)
    else:
        production_name = glyphinfo.production_name
    if production_name != ufo_glyph.name:
        postscriptNamesKey = PUBLIC_PREFIX + "postscriptNames"
        if postscriptNamesKey not in ufo_font.lib:
            ufo_font.lib[postscriptNamesKey] = dict()
        ufo_font.lib[postscriptNamesKey][ufo_glyph.name] = production_name

    for key in ["leftMetricsKey", "rightMetricsKey", "widthMetricsKey"]:
        value = getattr(layer, key, None)
        if value:
            ufo_glyph.lib[GLYPHLIB_PREFIX + "layer." + key] = value
        value = getattr(glyph, key, None)
        if value:
            ufo_glyph.lib[GLYPHLIB_PREFIX + "glyph." + key] = value

    if script:
        ufo_glyph.lib[SCRIPT_LIB_KEY] = script

    # if glyph contains custom 'category' and 'subCategory' overrides, store
    # them in the UFO glyph's lib
    if category:
        ufo_glyph.lib[GLYPHLIB_PREFIX + "category"] = category
    else:
        category = glyphinfo.category
    if subCategory:
        ufo_glyph.lib[GLYPHLIB_PREFIX + "subCategory"] = subCategory
    else:
        subCategory = glyphinfo.subCategory

    # load width before background, which is loaded with lib data

    # The width may be taken from another master via the customParameters
    # 'Link Metrics With Master' or 'Link Metrics With First Master'.
    master = self.font.masters[layer.associatedMasterId or layer.layerId]
    metrics_source = master.metricsSource
    if metrics_source is None:
        width = layer.width
    else:
        metric_layer = self.font.glyphs[glyph.name].layers[metrics_source.id]
        if metric_layer:
            width = metric_layer.width
            if layer.width != width:
                logger.debug(
                    f"{layer.parent.name}: Applying width from master "
                    f"'{metrics_source.id}': {layer.width} -> {width}"
                )
        else:
            width = None

    if width is None:
        pass
    elif category == "Mark" and subCategory == "Nonspacing" and width > 0:
        # zero the width of Nonspacing Marks like Glyphs.app does on export
        # TODO: (jany) check for customParameter DisableAllAutomaticBehaviour
        # FIXME: (jany) also don't do that when rt UFO -> glyphs -> UFO
        ufo_glyph.lib[ORIGINAL_WIDTH_KEY] = width
        ufo_glyph.width = 0
    else:
        ufo_glyph.width = width

    if not self.minimal:
        self.to_ufo_background_image(ufo_glyph, layer)
        self.to_ufo_guidelines(ufo_glyph, layer)
        self.to_ufo_glyph_background(ufo_glyph, layer)
        self.to_ufo_annotations(ufo_glyph, layer)
    self.to_ufo_hints(ufo_glyph, layer)
    self.to_ufo_glyph_user_data(ufo_font, glyph)
    self.to_ufo_layer_user_data(ufo_glyph, layer)
    self.to_ufo_smart_component_axes(ufo_glyph, glyph)

    self.to_ufo_paths(ufo_glyph, layer)
    self.to_ufo_components(ufo_glyph, layer)
    self.to_ufo_glyph_anchors(ufo_glyph, layer.anchors)
    if self.is_vertical:
        self.to_ufo_glyph_height_and_vertical_origin(ufo_glyph, layer)


def to_glyphs_glyph(self, ufo_glyph, ufo_layer, master):  # noqa: C901
    """Add UFO glif metadata, paths, components, and anchors to a GSGlyph.
    If the matching GSGlyph does not exist, then it is created,
    else it is updated with the new data.
    In all cases, a matching GSLayer is created in the GSGlyph to hold paths.
    """

    # FIXME: (jany) split between glyph and layer attributes
    #        have a write the first time, compare the next times for glyph
    #        always write for the layer

    # NOTE: This optimizes around the performance drain that is glyph name lookup
    #       without replacing the actual data structure. Ideally, FontGlyphsProxy
    #       provides O(1) lookup for all the ways you can use strings to look up
    #       glyphs.
    ufo_glyph_name = ufo_glyph.name  # Avoid method lookup in hot loop.
    glyph = None
    for glyph_object in self.font._glyphs:  # HOT LOOP. Avoid FontGlyphsProxy for speed!
        if glyph_object.name == ufo_glyph_name:  # HOT HOT HOT
            glyph = glyph_object
            break
    if glyph is None:
        glyph = self.glyphs_module.GSGlyph(name=ufo_glyph_name)
        # FIXME: (jany) ordering?
        self.font.glyphs.append(glyph)

    if ufo_glyph.unicodes:
        glyph.unicodes = [f"{c:04X}" for c in ufo_glyph.unicodes]
    glyph.note = ufo_glyph.note or ""
    if GLYPHLIB_PREFIX + "lastChange" in ufo_glyph.lib:
        last_change = ufo_glyph.lib[GLYPHLIB_PREFIX + "lastChange"]
        # We cannot be strict about the dateformat because it's not an official
        # UFO field mentioned in the spec so it could happen to have a timezone
        glyph.lastChange = from_loose_ufo_time(last_change)
    if ufo_glyph.markColor:
        glyph.color = _to_glyphs_color(ufo_glyph.markColor)

    # The export flag can be stored in the glyph's lib key (for upgrading legacy
    # sources) or the Designspace-level public.skipExportGlyphs lib key (canonical
    # place to store the information). The UFO level lib key is ignored.
    if GLYPHLIB_PREFIX + "Export" in ufo_glyph.lib:
        glyph.export = ufo_glyph.lib[GLYPHLIB_PREFIX + "Export"]
    if ufo_glyph.name in self.skip_export_glyphs:
        glyph.export = False

    ufo_font = self._sources[master.id].font
    ps_names_key = PUBLIC_PREFIX + "postscriptNames"
    if ps_names_key in ufo_font.lib and ufo_glyph.name in ufo_font.lib[ps_names_key]:
        glyph.production = ufo_font.lib[ps_names_key][ufo_glyph.name]
        # FIXME: (jany) maybe put something in glyphinfo? No, it's readonly
        #        maybe don't write in glyph.production if glyphinfo already
        #        has something
        # glyphinfo = glyphsLib.glyphdata.get_glyph(ufo_glyph.name)
        # production_name = glyph.production or glyphinfo.production_name

    glyphinfo = glyphsLib.glyphdata.get_glyph(ufo_glyph.name)

    layer = self.to_glyphs_layer(ufo_layer, glyph, master)

    for key in ["leftMetricsKey", "rightMetricsKey", "widthMetricsKey"]:
        # Also read the old version of the key that didn't have a prefix and
        # store it on the layer (because without the "glyph"/"layer" prefix we
        # didn't know whether it originally came from the layer of the glyph,
        # so it's easier to put it back on the most specific level, i.e. the
        # layer)
        for prefix, glyphs_object in (
            ("glyph.", glyph),
            ("", layer),
            ("layer.", layer),
        ):
            full_key = GLYPHLIB_PREFIX + prefix + key
            if full_key in ufo_glyph.lib:
                value = ufo_glyph.lib[full_key]
                setattr(glyphs_object, key, value)

    if SCRIPT_LIB_KEY in ufo_glyph.lib:
        glyph.script = ufo_glyph.lib[SCRIPT_LIB_KEY]

    if GLYPHLIB_PREFIX + "category" in ufo_glyph.lib:
        # TODO: (jany) store category only if different from glyphinfo?
        category = ufo_glyph.lib[GLYPHLIB_PREFIX + "category"]
        glyph.category = category
    else:
        category = glyphinfo.category
    if GLYPHLIB_PREFIX + "subCategory" in ufo_glyph.lib:
        sub_category = ufo_glyph.lib[GLYPHLIB_PREFIX + "subCategory"]
        glyph.subCategory = sub_category
    else:
        sub_category = glyphinfo.subCategory

    # load width before background, which is loaded with lib data
    if hasattr(layer, "foreground"):
        if ufo_glyph.width:
            # Don't store "0", it's the default in UFO.
            # Store in userData because the background's width is not relevant
            # in Glyphs.
            layer.userData[BACKGROUND_WIDTH_KEY] = ufo_glyph.width
    else:
        layer.width = ufo_glyph.width
    if category == "Mark" and sub_category == "Nonspacing" and layer.width == 0:
        # Restore originalWidth
        if ORIGINAL_WIDTH_KEY in ufo_glyph.lib:
            layer.width = ufo_glyph.lib[ORIGINAL_WIDTH_KEY]
            # TODO: (jany) check for customParam DisableAllAutomaticBehaviour?

    self.to_glyphs_background_image(ufo_glyph, layer)
    self.to_glyphs_guidelines(ufo_glyph, layer)
    self.to_glyphs_annotations(ufo_glyph, layer)
    self.to_glyphs_hints(ufo_glyph, layer)
    self.to_glyphs_glyph_user_data(ufo_font, glyph)
    self.to_glyphs_layer_user_data(ufo_glyph, layer)
    self.to_glyphs_smart_component_axes(ufo_glyph, glyph)

    self.to_glyphs_paths(ufo_glyph, layer)
    self.to_glyphs_components(ufo_glyph, layer)
    self.to_glyphs_glyph_anchors(ufo_glyph, layer)
    self.to_glyphs_glyph_height_and_vertical_origin(ufo_glyph, master, layer)


def to_ufo_glyph_height_and_vertical_origin(self, ufo_glyph, layer):
    # implentation based on:
    # https://github.com/googlefonts/glyphsLib/issues/557#issuecomment-667074856
    assert self.is_vertical

    ascender, descender = _get_typo_ascender_descender(layer.master)

    if layer.vertWidth is not None:
        ufo_glyph.height = layer.vertWidth
    else:
        ufo_glyph.height = ascender - descender

    if layer.vertOrigin is not None:
        ufo_glyph.verticalOrigin = ascender - layer.vertOrigin
    else:
        ufo_glyph.verticalOrigin = ascender


def _get_typo_ascender_descender(master):
    # Glyphsapp will use the typo metrics to set the verOrigin and
    # vertWidth. If typo metrics are not present, the master
    # ascender and descender are used instead.
    if "typoAscender" in master.customParameters:
        ascender = master.customParameters["typoAscender"]
    else:
        ascender = master.ascender
    if "typoDescender" in master.customParameters:
        descender = master.customParameters["typoDescender"]
    else:
        descender = master.descender
    return ascender, descender


def to_ufo_glyph_background(self, glyph, layer):
    """Set glyph background."""

    if not layer.hasBackground:
        return

    background = layer.background
    ufo_layer = self.to_ufo_background_layer(layer)
    new_glyph = ufo_layer.newGlyph(glyph.name)

    width = background.userData[BACKGROUND_WIDTH_KEY]
    if width is not None:
        new_glyph.width = width

    self.to_ufo_background_image(new_glyph, background)
    self.to_ufo_paths(new_glyph, background)
    self.to_ufo_components(new_glyph, background)
    self.to_ufo_glyph_anchors(new_glyph, background.anchors)
    self.to_ufo_guidelines(new_glyph, background)


def _to_glyphs_color(color):
    # If the color matches one of Glyphs's predefined colors, return that
    # index.
    for index, glyphs_color in enumerate(GLYPHS_COLORS):
        if str(color) == glyphs_color:
            return index

    # Otherwise, make a Glyphs-formatted RGBA color list: [u8, u8, u8, u8].
    # Glyphs up to version 2.5.1 always set the alpha channel to 1. It should
    # round-trip the actual value in later versions.
    # https://github.com/googlefonts/glyphsLib/pull/363#issuecomment-390418497
    return [round(float(component) * 255) for component in color.split(",")]


def to_glyphs_glyph_height_and_vertical_origin(self, ufo_glyph, master, layer):
    ascender, descender = _get_typo_ascender_descender(master)
    if ufo_glyph.height != (ascender - descender):
        layer.vertWidth = ufo_glyph.height

    if ufo_glyph.verticalOrigin is not None and ufo_glyph.verticalOrigin != ascender:
        layer.vertOrigin = ascender - ufo_glyph.verticalOrigin
