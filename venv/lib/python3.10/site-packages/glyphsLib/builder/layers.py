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

from .constants import GLYPHS_PREFIX, UFO2FT_COLOR_LAYER_MAPPING_KEY

LAYER_ID_KEY = GLYPHS_PREFIX + "layerId"
LAYER_ORDER_PREFIX = GLYPHS_PREFIX + "layerOrderInGlyph."
LAYER_ORDER_TEMP_USER_DATA_KEY = "__layerOrder"


def to_ufo_color_layer_names(self, master, ufo):
    for glyph in ufo.layers.defaultLayer:
        if UFO2FT_COLOR_LAYER_MAPPING_KEY in glyph.lib:
            glyph.lib[UFO2FT_COLOR_LAYER_MAPPING_KEY] = [
                (self._layer_map[v[0]], v[1])
                for v in glyph.lib[UFO2FT_COLOR_LAYER_MAPPING_KEY]
            ]


def to_ufo_layer(self, glyph, layer):
    ufo_font = self._sources[layer.associatedMasterId or layer.layerId].font

    layer_name = layer.name
    # Give color layers better names
    if layer._is_color_palette_layer():
        layer_name = f"color.{layer._color_palette_index()}"

    if layer.associatedMasterId == layer.layerId:
        ufo_layer = ufo_font.layers.defaultLayer
    elif layer_name not in ufo_font.layers:
        ufo_layer = ufo_font.newLayer(layer_name)
    elif layer_name in ufo_font.layers and glyph.name in ufo_font.layers[layer_name]:
        self.logger.warning(
            "%s %s: Glyph %s, layer %s: Duplicate glyph layer name",
            ufo_font.info.familyName,
            ufo_font.info.styleName,
            glyph.name,
            layer_name,
        )
        n = 1
        new_layer_name = layer_name
        while new_layer_name in ufo_font.layers:
            new_layer_name = layer_name + " #" + repr(n)
            n += 1
        ufo_layer = ufo_font.newLayer(new_layer_name)
    else:
        ufo_layer = ufo_font.layers[layer_name]
    if self.minimize_glyphs_diffs:
        ufo_layer.lib[LAYER_ID_KEY] = layer.layerId
        ufo_layer.lib[LAYER_ORDER_PREFIX + glyph.name] = _layer_order_in_glyph(
            self, layer
        )
    self._layer_map[layer.layerId] = ufo_layer.name
    return ufo_layer


def to_ufo_background_layer(self, layer):
    ufo_font = self._sources[layer.associatedMasterId or layer.layerId].font
    if layer.associatedMasterId == layer.layerId:
        layer_name = "public.background"
    else:
        layer_name = layer.name + ".background"
    if layer_name not in ufo_font.layers:
        background_layer = ufo_font.newLayer(layer_name)
    else:
        background_layer = ufo_font.layers[layer_name]
    return background_layer


def _layer_order_in_glyph(self, layer):
    # TODO: optimize?
    for order, glyph_layer in enumerate(layer.parent.layers.values()):
        if glyph_layer is layer:
            return order
    return None


def to_glyphs_layer(self, ufo_layer, glyph, master):
    if ufo_layer is self._sources[master.id].font.layers.defaultLayer:
        layer = _get_or_make_foreground(self, glyph, master)
    elif ufo_layer.name == "public.background":
        master_layer = _get_or_make_foreground(self, glyph, master)
        layer = master_layer.background
    elif ufo_layer.name.endswith(".background"):
        # Find or create the foreground layer
        # TODO: (jany) add lib attribute to find foreground by layer id
        foreground_name = ufo_layer.name[: -len(".background")]
        foreground = next(
            (
                l
                for l in glyph.layers
                if l.name == foreground_name and l.associatedMasterId == master.id
            ),
            None,
        )
        if foreground is None:
            foreground = self.glyphs_module.GSLayer()
            foreground.name = foreground_name
            foreground.associatedMasterId = master.id
        layer = foreground.background
        # Background layers don't have an associated master id nor a name nor an id
    else:
        layer = next(
            (
                l
                for l in glyph.layers
                if l.name == ufo_layer.name and l.associatedMasterId == master.id
            ),
            None,
        )
        if layer is None:
            layer = self.glyphs_module.GSLayer()
        layer.associatedMasterId = master.id
        if LAYER_ID_KEY in ufo_layer.lib:
            layer.layerId = ufo_layer.lib[LAYER_ID_KEY]
        layer.name = ufo_layer.name
        glyph.layers.append(layer)
    order_key = LAYER_ORDER_PREFIX + glyph.name
    if order_key in ufo_layer.lib:
        order = ufo_layer.lib[order_key]
        layer.userData[LAYER_ORDER_TEMP_USER_DATA_KEY] = order
    return layer


def _get_or_make_foreground(self, glyph, master):
    layer = glyph.layers[master.id]
    if layer is None:
        layer = glyph.layers[master.id] = self.glyphs_module.GSLayer()
    layer.layerId = master.id
    layer.name = master.name
    return layer


def to_glyphs_layer_order(self, glyph):
    # TODO: (jany) ask for the rules of layer ordering inside a glyph
    # For now, order according to key in lib
    glyph.layers = sorted(glyph.layers, key=_layer_order)
    for layer in glyph.layers:
        if LAYER_ORDER_TEMP_USER_DATA_KEY in layer.userData:
            del layer.userData[LAYER_ORDER_TEMP_USER_DATA_KEY]


def _layer_order(layer):
    if LAYER_ORDER_TEMP_USER_DATA_KEY in layer.userData:
        return layer.userData[LAYER_ORDER_TEMP_USER_DATA_KEY]
    return float("inf")
