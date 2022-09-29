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


import os
import posixpath

from .constants import (
    GLYPHS_PREFIX,
    GLYPHLIB_PREFIX,
    PUBLIC_PREFIX,
    UFO2FT_FEATURE_WRITERS_KEY,
    DEFAULT_FEATURE_WRITERS,
    DEFAULT_LAYER_NAME,
)

UFO_DATA_KEY = GLYPHLIB_PREFIX + "ufoData"
FONT_USER_DATA_KEY = GLYPHLIB_PREFIX + "fontUserData"
LAYER_LIB_KEY = GLYPHLIB_PREFIX + "layerLib"
LAYER_NAME_KEY = GLYPHLIB_PREFIX + "layerName"
GLYPH_USER_DATA_KEY = GLYPHLIB_PREFIX + "glyphUserData"
NODE_USER_DATA_KEY = GLYPHLIB_PREFIX + "nodeUserData"


def _has_manual_kern_feature(font):
    """Return true if the GSFont contains a manually written 'kern' feature."""
    return any(f for f in font.features if f.name == "kern" and not f.automatic)


def to_designspace_family_user_data(self):
    if self.use_designspace:
        for key, value in dict(self.font.userData).items():
            if _user_data_has_no_special_meaning(key):
                self.designspace.lib[key] = value

        # only write our custom ufo2ft featureWriters settings if the font
        # does have a manually written 'kern' feature; and if the lib key wasn't
        # already set in font.userData (in which case we assume the user knows
        # what she's doing).
        if (
            _has_manual_kern_feature(self.font)
            and UFO2FT_FEATURE_WRITERS_KEY not in self.designspace.lib
        ):
            self.designspace.lib[UFO2FT_FEATURE_WRITERS_KEY] = DEFAULT_FEATURE_WRITERS


def to_ufo_family_user_data(self, ufo):
    """Set family-wide user data as Glyphs does."""
    if not self.use_designspace:
        ufo.lib[FONT_USER_DATA_KEY] = dict(self.font.userData)


def to_ufo_master_user_data(self, ufo, master):
    """Set master-specific user data as Glyphs does."""
    for key in master.userData.keys():
        if _user_data_has_no_special_meaning(key):
            ufo.lib[key] = master.userData[key]

    # Restore UFO data files. This code assumes that all paths are POSIX paths.
    if UFO_DATA_KEY in master.userData:
        for filename, data in master.userData[UFO_DATA_KEY].items():
            ufo.data[filename] = bytes(data)


def to_ufo_glyph_user_data(self, ufo, glyph):
    key = GLYPH_USER_DATA_KEY + "." + glyph.name
    if glyph.userData:
        ufo.lib[key] = dict(glyph.userData)


def to_ufo_layer_lib(self, master, ufo, ufo_layer):
    key = LAYER_LIB_KEY + "." + ufo_layer.name
    # glyphsLib v5.3.2 and previous versions stored the layer lib in
    # the GSFont useData under a key named after the layer.
    # When different original UFOs each had a layer with the same layer name,
    # only the layer lib of the last one was stored and was exported to UFOs
    if key in self.font.userData.keys():
        ufo_layer.lib.update(self.font.userData[key])
    if key in master.userData.keys():
        ufo_layer.lib.update(master.userData[key])
        if LAYER_NAME_KEY in ufo_layer.lib:
            layer_name = ufo_layer.lib.pop(LAYER_NAME_KEY)
            # ufoLib2
            if hasattr(ufo, "renameLayer") and callable(ufo.renameLayer):
                ufo.renameLayer(ufo_layer.name, layer_name)
            # defcon
            else:
                ufo_layer.name = layer_name


def to_ufo_layer_user_data(self, ufo_glyph, layer):
    user_data = layer.userData
    for key in user_data.keys():
        if _user_data_has_no_special_meaning(key):
            ufo_glyph.lib[key] = user_data[key]


def to_ufo_node_user_data(self, ufo_glyph, node, user_data: dict):
    if user_data:
        path_index, node_index = node._indices()
        key = f"{NODE_USER_DATA_KEY}.{path_index}.{node_index}"
        ufo_glyph.lib[key] = user_data


def to_glyphs_family_user_data_from_designspace(self):
    """Set the GSFont userData from the designspace family-wide lib data."""
    target_user_data = self.font.userData
    for key, value in self.designspace.lib.items():
        if key == UFO2FT_FEATURE_WRITERS_KEY and value == DEFAULT_FEATURE_WRITERS:
            # if the designspace contains featureWriters settings that are the
            # same as glyphsLib default settings, there's no need to store them
            continue
        if _user_data_has_no_special_meaning(key):
            target_user_data[key] = value


def to_glyphs_family_user_data_from_ufo(self, ufo):
    """Set the GSFont userData from the UFO family-wide lib data."""
    target_user_data = self.font.userData
    try:
        for key, value in ufo.lib[FONT_USER_DATA_KEY].items():
            # Existing values taken from the designspace lib take precedence
            if key not in target_user_data.keys():
                target_user_data[key] = value
    except KeyError:
        # No FONT_USER_DATA in ufo.lib
        pass


def to_glyphs_master_user_data(self, ufo, master):
    """Set the GSFontMaster userData from the UFO master-specific lib data."""
    target_user_data = master.userData
    for key, value in ufo.lib.items():
        if _user_data_has_no_special_meaning(key):
            target_user_data[key] = value

    # Save UFO data files
    if ufo.data.fileNames:
        from glyphsLib.types import BinaryData

        ufo_data = {}
        for os_filename in ufo.data.fileNames:
            filename = posixpath.join(*os_filename.split(os.path.sep))
            ufo_data[filename] = BinaryData(ufo.data[os_filename])
        master.userData[UFO_DATA_KEY] = ufo_data


def to_glyphs_glyph_user_data(self, ufo, glyph):
    key = GLYPH_USER_DATA_KEY + "." + glyph.name
    if key in ufo.lib:
        glyph.userData = ufo.lib[key]


def to_glyphs_layer_lib(self, ufo_layer, master):
    user_data = {}
    for key, value in ufo_layer.lib.items():
        if _user_data_has_no_special_meaning(key):
            user_data[key] = value

    # the default layer may have a custom name
    layer_name = ufo_layer.name
    if (
        ufo_layer is self._sources[master.id].font.layers.defaultLayer
        and layer_name != DEFAULT_LAYER_NAME
    ):
        user_data[LAYER_NAME_KEY] = ufo_layer.name
        layer_name = DEFAULT_LAYER_NAME

    if user_data:
        key = LAYER_LIB_KEY + "." + layer_name
        master.userData[key] = user_data


def to_glyphs_layer_user_data(self, ufo_glyph, layer):
    user_data = layer.userData
    for key, value in ufo_glyph.lib.items():
        if _user_data_has_no_special_meaning(key):
            user_data[key] = value


def to_glyphs_node_user_data(self, ufo_glyph, node, path_index, node_index):
    key = f"{NODE_USER_DATA_KEY}.{path_index}.{node_index}"
    if key in ufo_glyph.lib:
        for k, v in ufo_glyph.lib[key].items():
            if k == "name":
                continue  # We take the node name from a UFO point's name attribute.
            node.userData[k] = v


def _user_data_has_no_special_meaning(key):
    return not (key.startswith(GLYPHS_PREFIX) or key.startswith(PUBLIC_PREFIX))
