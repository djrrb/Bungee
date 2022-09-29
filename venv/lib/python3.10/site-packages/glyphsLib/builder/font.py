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


import logging

from .common import to_ufo_time, from_ufo_time
from .constants import GLYPHS_PREFIX, UFO2FT_FILTERS_KEY

logger = logging.getLogger(__name__)

APP_VERSION_LIB_KEY = GLYPHS_PREFIX + "appVersion"
KEYBOARD_INCREMENT_KEY = GLYPHS_PREFIX + "keyboardIncrement"
MASTER_ORDER_LIB_KEY = GLYPHS_PREFIX + "fontMasterOrder"


def to_ufo_font_attributes(self, family_name):
    """Generate a list of UFOs with metadata loaded from .glyphs data.

    Modifies the list of UFOs in the UFOBuilder (self) in-place.
    """

    font = self.font

    # "date" can be missing; Glyphs.app removes it on saving if it's empty:
    # https://github.com/googlefonts/glyphsLib/issues/134
    date_created = getattr(font, "date", None)
    if date_created is not None:
        date_created = to_ufo_time(date_created)
    units_per_em = font.upm
    version_major = font.versionMajor
    version_minor = font.versionMinor
    copyright = font.copyright
    designer = font.designer
    designer_url = font.designerURL
    manufacturer = font.manufacturer
    manufacturer_url = font.manufacturerURL
    # XXX note is unused?
    # note = font.note
    glyph_order = list(glyph.name for glyph in font.glyphs)

    for index, master in enumerate(font.masters):
        source = self._designspace.newSourceDescriptor()
        ufo = self.ufo_module.Font()
        source.font = ufo

        ufo.lib[APP_VERSION_LIB_KEY] = font.appVersion
        ufo.lib[KEYBOARD_INCREMENT_KEY] = font.keyboardIncrement

        if date_created is not None:
            ufo.info.openTypeHeadCreated = date_created
        ufo.info.unitsPerEm = units_per_em
        ufo.info.versionMajor = version_major
        ufo.info.versionMinor = version_minor

        if copyright:
            ufo.info.copyright = copyright
        if designer:
            ufo.info.openTypeNameDesigner = designer
        if designer_url:
            ufo.info.openTypeNameDesignerURL = designer_url
        if manufacturer:
            ufo.info.openTypeNameManufacturer = manufacturer
        if manufacturer_url:
            ufo.info.openTypeNameManufacturerURL = manufacturer_url

        # NOTE: glyphs2ufo will *always* set a UFO public.glyphOrder equal to the
        # order of glyphs in the glyphs file, which can optionally be overwritten
        # by a glyphOrder custom parameter below in `to_ufo_custom_params`.
        ufo.glyphOrder = glyph_order

        self.to_ufo_names(ufo, master, family_name)
        self.to_ufo_family_user_data(ufo)

        ufo.lib.setdefault(UFO2FT_FILTERS_KEY, []).append(
            {"namespace": "glyphsLib.filters", "name": "eraseOpenCorners", "pre": True}
        )

        self.to_ufo_custom_params(ufo, font)

        self.to_ufo_master_attributes(source, master)

        ufo.lib[MASTER_ORDER_LIB_KEY] = index

        # FIXME: (jany) in the future, yield this UFO (for memory, lazy iter)
        self._designspace.addSource(source)
        self._sources[master.id] = source


def to_glyphs_font_attributes(self, source, master, is_initial):
    """
    Copy font attributes from `ufo` either to `self.font` or to `master`.

    Arguments:
    self -- The UFOBuilder
    ufo -- The current UFO being read
    master -- The current master being written
    is_initial -- True iff this the first UFO that we process
    """
    if is_initial:
        _set_glyphs_font_attributes(self, source)
    else:
        _compare_and_merge_glyphs_font_attributes(self, source)


def _set_glyphs_font_attributes(self, source):
    font = self.font
    ufo = source.font
    info = ufo.info

    if APP_VERSION_LIB_KEY in ufo.lib:
        font.appVersion = ufo.lib[APP_VERSION_LIB_KEY]
    if KEYBOARD_INCREMENT_KEY in ufo.lib:
        font.keyboardIncrement = ufo.lib[KEYBOARD_INCREMENT_KEY]

    if info.openTypeHeadCreated is not None:
        # FIXME: (jany) should wrap in glyphs_datetime? or maybe the GSFont
        #     should wrap in glyphs_datetime if needed?
        font.date = from_ufo_time(info.openTypeHeadCreated)
    if info.unitsPerEm is not None:
        font.upm = info.unitsPerEm
    if info.versionMajor is not None:
        font.versionMajor = info.versionMajor
    if info.versionMinor is not None:
        font.versionMinor = info.versionMinor

    if info.copyright is not None:
        font.copyright = info.copyright
    if info.openTypeNameDesigner is not None:
        font.designer = info.openTypeNameDesigner
    if info.openTypeNameDesignerURL is not None:
        font.designerURL = info.openTypeNameDesignerURL
    if info.openTypeNameManufacturer is not None:
        font.manufacturer = info.openTypeNameManufacturer
    if info.openTypeNameManufacturerURL is not None:
        font.manufacturerURL = info.openTypeNameManufacturerURL

    self.to_glyphs_family_names(ufo)
    self.to_glyphs_family_user_data_from_ufo(ufo)
    self.to_glyphs_custom_params(ufo, font)


def _compare_and_merge_glyphs_font_attributes(self, source):
    ufo = source.font
    self.to_glyphs_family_names(ufo, merge=True)


def to_glyphs_ordered_masters(self):
    """Modify in-place the list of UFOs to restore their original order in
    the Glyphs file (if any, otherwise does not change the order)."""
    return sorted(self.designspace.sources, key=_original_master_order)


def _original_master_order(source):
    try:
        return source.font.lib[MASTER_ORDER_LIB_KEY]
    # Key may not be found or source.font be None if it's a layer source.
    except (KeyError, AttributeError):
        return 1 << 31
