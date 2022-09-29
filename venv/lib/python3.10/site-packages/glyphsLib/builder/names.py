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


from collections import deque

from .constants import GLYPHS_PREFIX


def to_ufo_names(self, ufo, master, family_name):
    width = master.width
    weight = master.weight
    custom = master.customName

    if weight:
        ufo.lib[GLYPHS_PREFIX + "weight"] = weight
    if width:
        ufo.lib[GLYPHS_PREFIX + "width"] = width
    if custom:
        ufo.lib[GLYPHS_PREFIX + "customName"] = master.customName

    is_italic = bool(master.italicAngle)

    styleName = master.name
    ufo.info.familyName = family_name
    ufo.info.styleName = styleName

    # FIXME: (jany) should be the responsibility of ufo2ft?
    # Anyway, only generate the styleMap names if we're not round-tripping
    # (i.e. generating UFOs for fontmake, the traditional use-case of
    # glyphsLib.)
    if not self.minimize_glyphs_diffs:
        styleMapFamilyName, styleMapStyleName = build_stylemap_names(
            family_name=family_name,
            style_name=styleName,
            is_bold=(styleName == "Bold"),
            is_italic=is_italic,
        )
        ufo.info.styleMapFamilyName = styleMapFamilyName
        ufo.info.styleMapStyleName = styleMapStyleName


def build_stylemap_names(
    family_name, style_name, is_bold=False, is_italic=False, linked_style=None
):
    """Build UFO `styleMapFamilyName` and `styleMapStyleName` based on the
    family and style names, and the entries in the "Style Linking" section
    of the "Instances" tab in the "Font Info".

    The value of `styleMapStyleName` can be either "regular", "bold", "italic"
    or "bold italic", depending on the values of `is_bold` and `is_italic`.

    The `styleMapFamilyName` is a combination of the `family_name` and the
    `linked_style`.

    If `linked_style` is unset or set to 'Regular', the linked style is equal
    to the style_name with the last occurrences of the strings 'Regular',
    'Bold' and 'Italic' stripped from it.
    """

    styleMapStyleName = (
        " ".join(
            s for s in ("bold" if is_bold else "", "italic" if is_italic else "") if s
        )
        or "regular"
    )
    if not linked_style or linked_style == "Regular":
        linked_style = _get_linked_style(style_name, is_bold, is_italic)
    if linked_style:
        styleMapFamilyName = (family_name or "") + " " + linked_style
    else:
        styleMapFamilyName = family_name
    return styleMapFamilyName, styleMapStyleName


def _get_linked_style(style_name, is_bold, is_italic):
    # strip last occurrence of 'Regular', 'Bold', 'Italic' from style_name
    # depending on the values of is_bold and is_italic
    linked_style = deque()
    is_regular = not (is_bold or is_italic)
    for part in reversed(style_name.split()):
        if part == "Regular" and is_regular:
            is_regular = False
        elif part == "Bold" and is_bold:
            is_bold = False
        elif part == "Italic" and is_italic:
            is_italic = False
        else:
            linked_style.appendleft(part)
    return " ".join(linked_style)


def to_glyphs_family_names(self, ufo, merge=False):
    if not merge:
        # First UFO
        self.font.familyName = ufo.info.familyName
    else:
        # Subsequent UFOs
        if self.font.familyName != ufo.info.familyName:
            raise RuntimeError("All UFOs should have the same family name.")


def to_glyphs_master_names(self, ufo, master):
    name = ufo.info.styleName
    weight = ufo.lib.get(GLYPHS_PREFIX + "weight")
    width = ufo.lib.get(GLYPHS_PREFIX + "width")
    custom = ufo.lib.get(GLYPHS_PREFIX + "customName")

    master.set_all_name_components(name, weight, width, custom)
