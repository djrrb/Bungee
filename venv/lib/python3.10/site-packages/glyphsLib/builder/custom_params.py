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


from collections import defaultdict
import re

from glyphsLib.util import bin_to_int_list, int_list_to_bin
from .filters import parse_glyphs_filter
from .common import to_ufo_color
from .constants import (
    GLYPHS_PREFIX,
    UFO2FT_COLOR_PALETTES_KEY,
    UFO2FT_FILTERS_KEY,
    UFO2FT_USE_PROD_NAMES_KEY,
    CODEPAGE_RANGES,
    REVERSE_CODEPAGE_RANGES,
    PUBLIC_PREFIX,
    UFO_FILENAME_CUSTOM_PARAM,
)
from .features import replace_feature, replace_prefixes

"""Set Glyphs custom parameters in UFO info or lib, where appropriate.

Custom parameter data will be extracted from a Glyphs object such as GSFont,
GSFontMaster or GSInstance by wrapping it in the GlyphsObjectProxy.
This proxy normalizes and speeds up the API used to access custom parameters,
and also keeps track of which customParameters have been read from the object.

Note:
    In the special case of GSInstance -> UFO, the source object is not
    actually the GSInstance but a designspace InstanceDescriptor wrapped in
    InstanceDescriptorAsGSInstance. This is because the generation of
    instance UFOs from a Glyphs font happens in two steps:

        1. the GSFont is turned into a designspace + master UFOS
        2. the designspace + master UFOs are interpolated into instance UFOs

    We want step 2. to rely only on information from the designspace, that's why
    we use the InstanceDescriptor as a source of customParameters to put into
    the instance UFO.

In the other direction, put information from UFO info or lib into a GSFont or a
GSFontMaster. The UFO source is wrapped in a UFOProxy that records which
attributes are read/written.

In order to go in both directions, each known parameter is managed by a
ParamHandler object that can implement special rules to translate the value
between Glyphs and UFO formats. This files aims at providing at least one
handler per defined UFO info attribute, plus a bunch of handlers for known
Custom Paramerters or known UFO lib elements.

To go for example from UFO to Glyphs, each registered ParamHandler is called,
and each tries to find its parameter in the UFO's info or lib data. Accesses to
the UFO lib are recorded by the UFO proxy. After all registered ParamHandlers
have worked, we know which UFO lib fields have been "consumed" in a smart way,
and we can stupidly copy the other ones over to the Glyphs side. Same when
going from Glyphs to UFOs.
"""

CUSTOM_PARAM_PREFIX = GLYPHS_PREFIX + "customParameter."


def identity(value):
    return value


class GlyphsObjectProxy:
    """Accelerate and record access to the glyphs object's custom parameters"""

    def __init__(self, glyphs_object, glyphs_module):
        self._owner = glyphs_object
        # This is a key part to be used in UFO lib keys to be able to choose
        # between master and font attributes during roundtrip
        self.sub_key = glyphs_object.__class__.__name__ + "."
        self._glyphs_module = glyphs_module
        self._lookup = defaultdict(list)
        for param in glyphs_object.customParameters:
            self._lookup[param.name].append(param.value)
        self._handled = set()

    def get_attribute_value(self, key):
        if not hasattr(self._owner, key):
            return None
        return getattr(self._owner, key)

    def set_attribute_value(self, key, value):
        if not hasattr(self._owner, key):
            return
        setattr(self._owner, key, value)

    def get_custom_value(self, key):
        """Return the first and only custom parameter matching the given name."""
        self._handled.add(key)
        values = self._lookup[key]
        if len(values) > 1:
            raise RuntimeError(f"More than one value for this customParameter: {key}")
        if values:
            return values[0]
        return None

    def get_custom_values(self, key):
        """Return a set of values for the given customParameter name."""
        self._handled.add(key)
        return self._lookup[key]

    def set_custom_value(self, key, value):
        """Set one custom parameter with the given value.
        We assume that the list of custom parameters does not already contain
        the given parameter so we only append.
        """
        self._owner.customParameters.append(
            self._glyphs_module.GSCustomParameter(name=key, value=value)
        )

    def set_custom_values(self, key, values):
        """Set several values for the customParameter with the given key.
        We append one GSCustomParameter per value.
        """
        for value in values:
            self.set_custom_value(key, value)

    def unhandled_custom_parameters(self):
        for param in self._owner.customParameters:
            if param.name not in self._handled:
                yield param

    def mark_handled(self, key):
        """Mark a key as handled so it is ignored by `unhandled_custom_parameters`.

        Use e.g. when you handle a custom parameter outside this module.
        """
        self._handled.add(key)

    def is_font(self):
        """Returns whether we are looking at a top-level GSFont object as
        opposed to a master or instance."""
        return hasattr(self._owner, "glyphs")

    def has_properties(self):
        if self.is_font():
            return self._owner.format_version > 2
        else:
            return hasattr(self._owner, "properties")

    def get_property(self, key):
        for prop in self._owner.properties:
            if key == prop.key:
                return prop.defaultValue
        return None


class UFOProxy:
    """Record access to the UFO's lib custom parameters"""

    def __init__(self, ufo):
        self._owner = ufo
        self._handled = set()

    def has_info_attr(self, name):
        return hasattr(self._owner.info, name)

    def get_info_value(self, name):
        return getattr(self._owner.info, name)

    def set_info_value(self, name, value):
        setattr(self._owner.info, name, value)

    def has_lib_key(self, name):
        return name in self._owner.lib

    def get_lib_value(self, name):
        if name not in self._owner.lib:
            return None
        self._handled.add(name)
        return self._owner.lib[name]

    def set_lib_value(self, name, value):
        self._owner.lib[name] = value

    def unhandled_lib_items(self):
        for key, value in self._owner.lib.items():
            if key.startswith(CUSTOM_PARAM_PREFIX) and key not in self._handled:
                yield (key, value)


class AbstractParamHandler:
    # @abstractmethod
    def to_glyphs(self):
        pass

    # @abstractmethod
    def to_ufo(self):
        pass


class ParamHandler(AbstractParamHandler):
    def __init__(
        self,
        glyphs_name,
        ufo_name=None,
        glyphs_long_name=None,
        glyphs_multivalued=False,
        glyphs3_property=None,
        ufo_prefix=CUSTOM_PARAM_PREFIX,
        ufo_info=True,
        ufo_default=None,
        value_to_ufo=identity,
        value_to_glyphs=identity,
    ):
        self.glyphs_name = glyphs_name
        self.glyphs_long_name = glyphs_long_name
        self.glyphs_multivalued = glyphs_multivalued
        self.glyphs3_property = glyphs3_property
        # By default, they have the same name in both
        self.ufo_name = ufo_name or glyphs_name
        self.ufo_prefix = ufo_prefix
        self.ufo_info = ufo_info
        self.ufo_default = ufo_default
        # Value transformation functions
        self.value_to_ufo = value_to_ufo
        self.value_to_glyphs = value_to_glyphs

    # By default, the parameter is read from/written to:
    #  - the Glyphs object's customParameters
    #  - the UFO's info object if it has a matching attribute, else the lib
    def to_glyphs(self, glyphs, ufo):
        ufo_value = self._read_from_ufo(glyphs, ufo)
        if ufo_value is None:
            return
        glyphs_value = self.value_to_glyphs(ufo_value)
        self._write_to_glyphs(glyphs, glyphs_value)

    def to_ufo(self, builder, glyphs, ufo):
        glyphs_value = self._read_from_glyphs(glyphs)
        if glyphs_value is None:
            return
        ufo_value = self.value_to_ufo(glyphs_value)
        self._write_to_ufo(glyphs, ufo, ufo_value)

    def _read_from_glyphs(self, glyphs):
        # Is it now a property?
        if self.glyphs3_property and glyphs.has_properties():
            return glyphs.get_property(self.glyphs3_property)
        # Try both the prefixed (long) name and the short name
        if self.glyphs_multivalued:
            getter = glyphs.get_custom_values
        else:
            getter = glyphs.get_custom_value
        # The value registered using the small name has precedence
        small_name_value = getter(self.glyphs_name)
        if small_name_value is not None:
            return small_name_value
        if self.glyphs_long_name is not None:
            return getter(self.glyphs_long_name)
        return None

    def _write_to_glyphs(self, glyphs, value):
        # We currently convert UFO to Glyphs2 files.
        # If we ever export Glyphs3 by default, we need a similar test
        # here to the one in _read_from_glyphs to determine whether a
        # value should be placed in the new properties top-level key.

        # Never write the prefixed (long) name?
        # FIXME: (jany) maybe should rather preserve the naming choice of user
        if self.glyphs_multivalued:
            glyphs.set_custom_values(self.glyphs_name, value)
        else:
            glyphs.set_custom_value(self.glyphs_name, value)

    def _read_from_ufo(self, glyphs, ufo):
        if self.ufo_info and ufo.has_info_attr(self.ufo_name):
            return ufo.get_info_value(self.ufo_name)
        else:
            ufo_prefix = self.ufo_prefix
            if ufo_prefix == CUSTOM_PARAM_PREFIX:
                ufo_prefix += glyphs.sub_key
            return ufo.get_lib_value(ufo_prefix + self.ufo_name)

    def _write_to_ufo(self, glyphs, ufo, value):
        if self.ufo_default is not None and value == self.ufo_default:
            return
        if self.ufo_info and ufo.has_info_attr(self.ufo_name):
            # most OpenType table entries go in the info object
            ufo.set_info_value(self.ufo_name, value)
        else:
            # everything else gets dumped in the lib
            ufo_prefix = self.ufo_prefix
            if ufo_prefix == CUSTOM_PARAM_PREFIX:
                ufo_prefix += glyphs.sub_key
            ufo.set_lib_value(ufo_prefix + self.ufo_name, value)


KNOWN_PARAM_HANDLERS = []


def register(handler):
    KNOWN_PARAM_HANDLERS.append(handler)


GLYPHS_UFO_CUSTOM_PARAMS = (
    ("hheaAscender", "openTypeHheaAscender"),
    ("hheaDescender", "openTypeHheaDescender"),
    ("hheaLineGap", "openTypeHheaLineGap"),
    ("compatibleFullName", "openTypeNameCompatibleFullName"),
    ("preferredFamilyName", "openTypeNamePreferredFamilyName"),
    ("preferredSubfamilyName", "openTypeNamePreferredSubfamilyName"),
    ("WWSSubfamilyName", "openTypeNameWWSSubfamilyName"),
    # OS/2 parameters
    ("panose", "openTypeOS2Panose"),
    ("fsType", "openTypeOS2Type"),
    ("typoAscender", "openTypeOS2TypoAscender"),
    ("typoDescender", "openTypeOS2TypoDescender"),
    ("typoLineGap", "openTypeOS2TypoLineGap"),
    ("unicodeRanges", "openTypeOS2UnicodeRanges"),
    ("strikeoutSize", "openTypeOS2StrikeoutSize"),
    ("strikeoutPosition", "openTypeOS2StrikeoutPosition"),
    # OS/2 Subscript parameters
    ("subscriptXSize", "openTypeOS2SubscriptXSize"),
    ("subscriptYSize", "openTypeOS2SubscriptYSize"),
    ("subscriptXOffset", "openTypeOS2SubscriptXOffset"),
    ("subscriptYOffset", "openTypeOS2SubscriptYOffset"),
    # OS/2 Superscript parameters
    ("superscriptXSize", "openTypeOS2SuperscriptXSize"),
    ("superscriptYSize", "openTypeOS2SuperscriptYSize"),
    ("superscriptXOffset", "openTypeOS2SuperscriptXOffset"),
    ("superscriptYOffset", "openTypeOS2SuperscriptYOffset"),
    # ('weightClass', 'openTypeOS2WeightClass'),
    # ('widthClass', 'openTypeOS2WidthClass'),
    # ('winAscent', 'openTypeOS2WinAscent'),
    # ('winDescent', 'openTypeOS2WinDescent'),
    ("vheaVertAscender", "openTypeVheaVertTypoAscender"),
    ("vheaVertDescender", "openTypeVheaVertTypoDescender"),
    ("vheaVertLineGap", "openTypeVheaVertTypoLineGap"),
    ("vheaVertTypoAscender", "openTypeVheaVertTypoAscender"),
    ("vheaVertTypoDescender", "openTypeVheaVertTypoDescender"),
    ("vheaVertTypoLineGap", "openTypeVheaVertTypoLineGap"),
    # Postscript parameters
    ("blueScale", "postscriptBlueScale"),
    ("blueShift", "postscriptBlueShift"),
    ("isFixedPitch", "postscriptIsFixedPitch"),
    ("underlinePosition", "postscriptUnderlinePosition"),
    ("underlineThickness", "postscriptUnderlineThickness"),
)
for glyphs_name, ufo_name in GLYPHS_UFO_CUSTOM_PARAMS:
    register(ParamHandler(glyphs_name, ufo_name, glyphs_long_name=ufo_name))

GLYPHS_UFO_CUSTOM_PARAMS_GLYPHS3_PROPERTIES = (
    ("license", "openTypeNameLicense", "licenses"),
    ("licenseURL", "openTypeNameLicenseURL", "licenseURL"),
    ("trademark", "trademark", "trademarks"),
    ("description", "openTypeNameDescription", "descriptions"),
    ("sampleText", "openTypeNameSampleText", "sampleTexts"),
    ("postscriptFontName", "postscriptFontName", "postscriptFontName"),
    ("postscriptFullName", "postscriptFullName", "postscriptFullName"),
    ("WWSFamilyName", "openTypeNameWWSFamilyName", "WWSFamilyName"),
    ("vendorID", "openTypeOS2VendorID", "vendorID"),
    ("versionString", "openTypeNameVersion", "versionString"),
)

for glyphs_name, ufo_name, property_name in GLYPHS_UFO_CUSTOM_PARAMS_GLYPHS3_PROPERTIES:
    register(
        ParamHandler(
            glyphs_name,
            ufo_name,
            glyphs_long_name=ufo_name,
            glyphs3_property=property_name,
        )
    )

# TODO: (jany) for all the following fields, check that they are stored in a
# meaningful Glyphs customParameter. Maybe they have short names?
GLYPHS_UFO_CUSTOM_PARAMS_NO_SHORT_NAME = (
    "openTypeHheaCaretSlopeRun",
    "openTypeVheaCaretSlopeRun",
    "openTypeHheaCaretSlopeRise",
    "openTypeVheaCaretSlopeRise",
    "openTypeHheaCaretOffset",
    "openTypeVheaCaretOffset",
    "openTypeHeadLowestRecPPEM",
    "openTypeHeadFlags",
    "openTypeNameVersion",
    "openTypeNameUniqueID",
    "openTypeOS2FamilyClass",
    "postscriptSlantAngle",
    "postscriptUniqueID",
    # Should this be handled in `blue_values.py`?
    # 'postscriptFamilyBlues',
    # 'postscriptFamilyOtherBlues',
    "postscriptBlueFuzz",
    "postscriptForceBold",
    "postscriptDefaultWidthX",
    "postscriptNominalWidthX",
    "postscriptWeightName",
    "postscriptDefaultCharacter",
    "postscriptWindowsCharacterSet",
    "macintoshFONDFamilyID",
    "macintoshFONDName",
    "styleMapFamilyName",
    "styleMapStyleName",
)
for name in GLYPHS_UFO_CUSTOM_PARAMS_NO_SHORT_NAME:
    register(ParamHandler(name))


class EmptyListDefaultParamHandler(ParamHandler):
    def to_glyphs(self, glyphs, ufo):
        ufo_value = self._read_from_ufo(glyphs, ufo)
        # Ingore default value == empty list
        if ufo_value is None or ufo_value == []:
            return
        glyphs_value = self.value_to_glyphs(ufo_value)
        self._write_to_glyphs(glyphs, glyphs_value)


register(EmptyListDefaultParamHandler("postscriptFamilyBlues"))
register(EmptyListDefaultParamHandler("postscriptFamilyOtherBlues"))


# Convert code page numbers to OS/2 ulCodePageRange bits. Empty lists stay empty lists.
class OS2CodePageRangesParamHandler(AbstractParamHandler):
    def to_glyphs(self, glyphs, ufo):
        ufo_codepage_bits = ufo.get_info_value("openTypeOS2CodePageRanges")
        if ufo_codepage_bits is None:
            return

        codepages = []
        unsupported_codepage_bits = []
        for codepage in ufo_codepage_bits:
            if codepage in REVERSE_CODEPAGE_RANGES:
                codepages.append(REVERSE_CODEPAGE_RANGES[codepage])
            else:
                unsupported_codepage_bits.append(codepage)

        glyphs.set_custom_value("codePageRanges", codepages)
        if unsupported_codepage_bits:
            glyphs.set_custom_value(
                "codePageRangesUnsupportedBits", unsupported_codepage_bits
            )

    def to_ufo(self, builder, glyphs, ufo):
        codepages = glyphs.get_custom_value("codePageRanges")
        if codepages is None:
            codepages = glyphs.get_custom_value("openTypeOS2CodePageRanges")
            if codepages is None:
                return

        ufo_codepage_bits = [CODEPAGE_RANGES[v] for v in codepages]
        unsupported_codepage_bits = glyphs.get_custom_value(
            "codePageRangesUnsupportedBits"
        )
        if unsupported_codepage_bits:
            ufo_codepage_bits.extend(unsupported_codepage_bits)

        ufo.set_info_value("openTypeOS2CodePageRanges", sorted(ufo_codepage_bits))


register(OS2CodePageRangesParamHandler())

# enforce that winAscent/Descent are positive, according to UFO spec
for glyphs_name in ("winAscent", "winDescent"):
    ufo_name = "openTypeOS2W" + glyphs_name[1:]
    register(
        ParamHandler(
            glyphs_name,
            ufo_name,
            glyphs_long_name=ufo_name,
            value_to_ufo=abs,
            value_to_glyphs=abs,
        )
    )

# The value of these could be a float, and ufoLib/defcon expect an int.
for glyphs_name in ("weightClass", "widthClass"):
    ufo_name = "openTypeOS2W" + glyphs_name[1:]
    register(ParamHandler(glyphs_name, ufo_name, value_to_ufo=int))


# convert Glyphs' GASP Table to UFO openTypeGaspRangeRecords
def to_ufo_gasp_table(value):
    # XXX maybe the parser should cast the gasp values to int?
    value = {int(k): int(v) for k, v in value.items()}
    gasp_records = []
    # gasp range records must be sorted in ascending rangeMaxPPEM
    for max_ppem, gasp_behavior in sorted(value.items()):
        gasp_records.append(
            {
                "rangeMaxPPEM": max_ppem,
                "rangeGaspBehavior": bin_to_int_list(gasp_behavior),
            }
        )
    return gasp_records


def to_glyphs_gasp_table(value):
    return {
        str(record["rangeMaxPPEM"]): int_list_to_bin(record["rangeGaspBehavior"])
        for record in value
    }


register(
    ParamHandler(
        glyphs_name="GASP Table",
        ufo_name="openTypeGaspRangeRecords",
        value_to_ufo=to_ufo_gasp_table,
        value_to_glyphs=to_glyphs_gasp_table,
    )
)

register(
    ParamHandler(
        glyphs_name="gasp Table",
        ufo_name="openTypeGaspRangeRecords",
        value_to_ufo=to_ufo_gasp_table,
        value_to_glyphs=to_glyphs_gasp_table,
    )
)


def to_ufo_color_palettes(value):
    return [[to_ufo_color(color) for color in palette] for palette in value]


def _to_glyphs_color(color):
    if color[0] == color[1] == color[2]:
        color = [color[0], color[3]]
    return ",".join(str(round(v * 255)) for v in color)


def to_glyphs_color_palettes(value):
    return [[_to_glyphs_color(color) for color in palette] for palette in value]


register(
    ParamHandler(
        glyphs_name="Color Palettes",
        ufo_name=UFO2FT_COLOR_PALETTES_KEY,
        ufo_info=False,
        ufo_prefix="",
        value_to_ufo=to_ufo_color_palettes,
        value_to_glyphs=to_glyphs_color_palettes,
    )
)

# TODO: (jany) look at
# https://forum.glyphsapp.com/t/name-table-entry-win-id4/3811/10
# Use Name Table Entry for the next param


def to_glyphs_opentype_name_records(value):
    # In ufoLib2, font.info.openTypeNameRecords is a list of NameRecord objects,
    # while in defcon it is a list of dicts; reduce both to dicts.
    return [dict(r) for r in value]


register(
    ParamHandler(
        glyphs_name="openTypeNameRecords",
        value_to_glyphs=to_glyphs_opentype_name_records,
    )
)

register(ParamHandler(glyphs_name="Disable Last Change", ufo_name="disablesLastChange"))

register(
    ParamHandler(
        # convert between Glyphs.app's and ufo2ft's equivalent parameter
        glyphs_name="Don't use Production Names",
        ufo_name=UFO2FT_USE_PROD_NAMES_KEY,
        ufo_prefix="",
        value_to_ufo=lambda value: not value,
        value_to_glyphs=lambda value: not value,
    )
)


class MiscParamHandler(ParamHandler):
    """Copy GSFont attributes to ufo lib"""

    def _read_from_glyphs(self, glyphs):
        return glyphs.get_attribute_value(self.glyphs_name)

    def _write_to_glyphs(self, glyphs, value):
        glyphs.set_attribute_value(self.glyphs_name, value)


register(MiscParamHandler(glyphs_name="disablesAutomaticAlignment"))
register(MiscParamHandler(glyphs_name="iconName"))


class DisplayStringsParamHandler(MiscParamHandler):
    def __init__(self):
        super().__init__(glyphs_name="DisplayStrings")

    def to_ufo(self, builder, glyphs, ufo):
        # We test for builder here because apply_instance_data() passes None and
        # we don't want to copy-paste or subclass UFOBuilder.
        if (
            builder is not None
            and builder.store_editor_state
            and builder.font.DisplayStrings
        ):
            super().to_ufo(builder, glyphs, ufo)


register(DisplayStringsParamHandler())

# deal with any Glyphs naming quirks here
register(
    MiscParamHandler(
        glyphs_name="disablesNiceNames",
        ufo_name="useNiceNames",
        value_to_ufo=lambda value: int(not value),
        value_to_glyphs=lambda value: not bool(value),
    )
)

for number in ("", "1", "2", "3"):
    register(MiscParamHandler("customValue" + number, ufo_info=False))
register(MiscParamHandler("weightValue", ufo_info=False))
register(MiscParamHandler("widthValue", ufo_info=False))


def append_unique(array, value):
    if value not in array:
        array.append(value)


class OS2SelectionParamHandler(AbstractParamHandler):
    flags = {7: "Use Typo Metrics", 8: "Has WWS Names"}

    # Note that en empty openTypeOS2Selection list should stay an empty list, as
    # opposed to a non-existant list. In the latter case, we round-trip nothing, in the
    # former, we at least write an empty list to openTypeOS2SelectionUnsupportedBits
    # which we use to re-instate an empty list in the UFO on tripping back.
    def to_glyphs(self, glyphs, ufo):
        ufo_flags = ufo.get_info_value("openTypeOS2Selection")
        if ufo_flags is None:
            return

        unsupported_bits = []
        for flag in ufo_flags:
            if flag in self.flags:
                glyphs.set_custom_value(self.flags[flag], True)
            else:
                unsupported_bits.append(flag)
        glyphs.set_custom_value("openTypeOS2SelectionUnsupportedBits", unsupported_bits)

    def to_ufo(self, builder, glyphs, ufo):
        use_typo_metrics = glyphs.get_custom_value(self.flags[7])
        has_wws_name = glyphs.get_custom_value(self.flags[8])
        unsupported_bits = glyphs.get_custom_value(
            "openTypeOS2SelectionUnsupportedBits"
        )
        if not use_typo_metrics and not has_wws_name and unsupported_bits is None:
            return

        selection_bits = []
        if use_typo_metrics:
            selection_bits.append(7)
        if has_wws_name:
            selection_bits.append(8)
        if unsupported_bits:
            selection_bits.extend(unsupported_bits)
        ufo.set_info_value("openTypeOS2Selection", sorted(selection_bits))


register(OS2SelectionParamHandler())


class GlyphOrderParamHandler(AbstractParamHandler):
    """Translate between Glyphs.app's glyphOrder parameter and UFO's
    public.glyphOrder.

    See the GlyphOrderTest class for a thorough explanation.
    """

    def to_glyphs(self, glyphs, ufo):
        if glyphs.is_font():
            ufo_glyphOrder = ufo.get_lib_value(PUBLIC_PREFIX + "glyphOrder")
            if ufo_glyphOrder:
                glyphs.set_custom_value("glyphOrder", ufo_glyphOrder)

    def to_ufo(self, builder, glyphs, ufo):
        if glyphs.is_font():
            glyphs_glyphOrder = glyphs.get_custom_value("glyphOrder")
            if glyphs_glyphOrder:
                ufo.set_lib_value(PUBLIC_PREFIX + "glyphOrder", glyphs_glyphOrder)


register(GlyphOrderParamHandler())


class FilterParamHandler(AbstractParamHandler):
    """Handler for (Pre)Filter custom paramters.

    This is complicated. ufo2ft grew filter modules to mimic some of Glyph's
    automatic features, but due to the impendance mismatch between the flow of
    data in Glyphs and in UFOs plus Designspaces, they need to be handled in
    two ways: once for filters that should be applied to masters and once for
    filters on instances, which should be applied only to interpolated UFOs:

       +------+
       |GSFont+-------------------+
       +----+-+                   |
            |                     |
          +-+-----------+       +-+----------+
          |GSFontMaster |       |GSIntance   |
          +-------------+       +------------+
           userData                    customParameters
             com...ufo2ft.filters        Filter & PreFilter

                ^  |                      |  ^
     roundtrips |  |                      |  |
                |  v                      |  |
            lib                           |  | roundtrips
              com...ufo2ft.filters        |  |
          +-----------+                   v  |
          |Master UFO |          lib
          +---+-------+            com.schriftgestaltung.customParameter...
              |
          +---+-----+        +----------+                    +-----------------+
          | Source  |        | Instance |    ------------>   |Interpolated UFO |
          +---+-----+        +-----+----+                    +-----------------+
              |                    |          goes 1 way        lib
      +-------+-----+              |     apply_instance_data()    com...ufo2ft.filters
      | Designspace +--------------+
      +-------------+

    The ufo2ft filters should roundtrip as-is between UFO source masters and
    GSFontMaster, because that's how we use them in the UFO workflow with 1
    master UFO = 1 final font with filters applied.

    The Glyphs filters defined on GSInstance should keep doing what they were
    doing already:

    - first be copied as-is into the designspace instance's lib, which should
      roundtrip back to Glyphs
    - then be converted to ufo2ft equivalents and put in the final interpolated
      UFOs before they are compiled into final fonts. Those should not
      roundtrip because the interpolated UFO is discarded after compilation.

    The handler below only handles the latter, one-way case. Since ufo2ft
    filters are a UFO lib key, they are automatically stored in a master's
    userData by another code path.
    """

    def to_glyphs(self, glyphs, ufo):
        pass

    def to_ufo(self, builder, glyphs, ufo):
        if not glyphs.is_font():
            ufo_filters = []
            for pre_filter in glyphs.get_custom_values("PreFilter"):
                ufo_filters.append(parse_glyphs_filter(pre_filter, is_pre=True))
            for filter in glyphs.get_custom_values("Filter"):
                ufo_filters.append(parse_glyphs_filter(filter, is_pre=False))

            if not ufo_filters:
                return
            if not ufo.has_lib_key(UFO2FT_FILTERS_KEY):
                ufo.set_lib_value(UFO2FT_FILTERS_KEY, [])
            existing = ufo.get_lib_value(UFO2FT_FILTERS_KEY)
            existing.extend(ufo_filters)


register(FilterParamHandler())


class ReplacePrefixParamHandler(AbstractParamHandler):
    def to_ufo(self, builder, glyphs, ufo):
        repl_map = {}
        for value in glyphs.get_custom_values("Replace Prefix"):
            prefix_name, prefix_code = re.split(r"\s*;\s*", value, 1)
            # if multiple 'Replace Prefix' custom params replace the same
            # prefix, the last wins
            repl_map[prefix_name] = prefix_code

        features_text = ufo._owner.features.text

        if not (repl_map and features_text):
            return

        glyph_names = set(ufo._owner.keys())

        ufo._owner.features.text = replace_prefixes(
            repl_map, features_text, glyph_names=glyph_names
        )

    def to_glyphs(self, glyphs, ufo):
        # do the same as ReplaceFeatureParamHandler.to_glyphs
        pass


register(ReplacePrefixParamHandler())


class ReplaceFeatureParamHandler(AbstractParamHandler):
    def to_ufo(self, builder, glyphs, ufo):
        for value in glyphs.get_custom_values("Replace Feature"):
            tag, repl = re.split(r"\s*;\s*", value, 1)
            ufo._owner.features.text = replace_feature(
                tag, repl, ufo._owner.features.text or ""
            )

    def to_glyphs(self, glyphs, ufo):
        # TODO: (jany) The "Replace Feature" custom parameter can be used to
        # have one master/instance with different features than what is stored
        # in the GSFont. When going from several UFOs to one GSFont, we could
        # detect when UFOs have different features, put the common ones in
        # GSFont and replace the different ones with this custom parameter.
        # See the file `tests/builder/features_test.py`.
        pass


register(ReplaceFeatureParamHandler())


class ReencodeGlyphsParamHandler(AbstractParamHandler):
    """The "Reencode Glyphs" custom parameter contains a list of
    'glyphname=unicodevalue' strings: e.g., ["smiley=E100", "logo=E101"].
    It only applies to specific instance (not to master or globally) and is
    meant to assign Unicode values to glyphs with the specied name at export
    time.
    When the Unicode value in question is already assigned to another glyph,
    the latter's Unicode value is deleted.
    When the Unicode value is left out, e.g., "f_f_i=", "f_f_j=", this will
    strip "f_f_i" and "f_f_j" of their Unicode values.

    This parameter handler only handles going from Glyphs to (instance) UFOs,
    and not also in the opposite direction, as the parameter isn't stored in
    the UFO lib, but directly applied to the UFO unicode values.
    """

    def to_ufo(self, builder, glyphs, ufo):
        # TODO Check that the wrapped glyphs object is indeed an instance, and
        # not a GSFont or GSMaster (unlikely)
        reencode_list = glyphs.get_custom_value("Reencode Glyphs")
        if not reencode_list:
            return
        ufo = ufo._owner
        cmap = {glyph.unicode: glyph.name for glyph in ufo}
        for entry in reencode_list:
            name, hexcode = entry.split("=")
            if name not in ufo:
                continue
            if hexcode.strip() == "":
                ufo[name].unicode = None
            else:
                codepoint = int(hexcode, 16)
                if codepoint in cmap:
                    previous = cmap[codepoint]
                    ufo[previous].unicode = None
                ufo[name].unicode = codepoint

    def to_glyphs(self, glyphs, ufo):
        # The 'Reencode Glyphs' parameter only applies to instances, which
        # are not meant to be roundtripped. No need to handle it here.
        pass


register(ReencodeGlyphsParamHandler())


def to_ufo_custom_params(self, ufo, glyphs_object):
    # glyphs_module=None because we shouldn't instanciate any Glyphs classes
    glyphs_proxy = GlyphsObjectProxy(glyphs_object, glyphs_module=None)
    ufo_proxy = UFOProxy(ufo)

    glyphs_proxy.mark_handled(UFO_FILENAME_CUSTOM_PARAM)

    for handler in KNOWN_PARAM_HANDLERS:
        handler.to_ufo(self, glyphs_proxy, ufo_proxy)

    for param in glyphs_proxy.unhandled_custom_parameters():
        name = _normalize_custom_param_name(param.name)
        ufo.lib[CUSTOM_PARAM_PREFIX + glyphs_proxy.sub_key + name] = param.value

    _set_default_params(ufo)


def to_glyphs_custom_params(self, ufo, glyphs_object):
    glyphs_proxy = GlyphsObjectProxy(glyphs_object, glyphs_module=self.glyphs_module)
    ufo_proxy = UFOProxy(ufo)

    # Handle known parameters
    for handler in KNOWN_PARAM_HANDLERS:
        handler.to_glyphs(glyphs_proxy, ufo_proxy)

    # Since all UFO `info` entries (from `fontinfo.plist`) have a registered
    # handler, the only place where we can find unexpected stuff is the `lib`.
    # See the file `tests/builder/fontinfo_test.py` for `fontinfo` coverage.
    prefix = CUSTOM_PARAM_PREFIX + glyphs_proxy.sub_key
    for name, value in ufo_proxy.unhandled_lib_items():
        name = _normalize_custom_param_name(name)
        if not name.startswith(prefix):
            continue
        name = name[len(prefix) :]
        glyphs_proxy.set_custom_value(name, value)

    _unset_default_params(glyphs_object)


def _normalize_custom_param_name(name):
    """Replace curved quotes with straight quotes in a custom parameter name.
    These should be the only keys with problematic (non-ascii) characters,
    since they can be user-generated.
    """

    replacements = (("\u2018", "'"), ("\u2019", "'"), ("\u201C", '"'), ("\u201D", '"'))
    for orig, replacement in replacements:
        name = name.replace(orig, replacement)
    return name


DEFAULT_PARAMETERS = (
    # ufo2ft defaults to fsType Bit 2 ("Preview & Print embedding"), while
    # Glyphs.app defaults to Bit 3 ("Editable embedding")
    ("fsType", "openTypeOS2Type", [3]),
    # Reference:
    # https://glyphsapp.com/content/1-get-started/2-manuals/
    # 1-handbook-glyphs-2-0/Glyphs-Handbook-2.3.pdf#page=200
    ("underlineThickness", "postscriptUnderlineThickness", 50),
    ("underlinePosition", "postscriptUnderlinePosition", -100),
)


def _set_default_params(ufo):
    """Set Glyphs.app's default parameters when different from ufo2ft ones."""
    for _, ufo_name, default_value in DEFAULT_PARAMETERS:
        if getattr(ufo.info, ufo_name) is None:
            if isinstance(default_value, list):
                # Prevent problem if the same default value list is put in
                # several unrelated objects.
                default_value = default_value[:]
            setattr(ufo.info, ufo_name, default_value)


def _unset_default_params(glyphs):
    """Unset Glyphs.app's parameters that have default values.
    FIXME: (jany) maybe this should be taken care of in the writer? and/or
        classes should have better default values?
    """
    for glyphs_name, _, default_value in DEFAULT_PARAMETERS:
        if (
            glyphs_name in glyphs.customParameters
            and glyphs.customParameters[glyphs_name] == default_value
        ):
            del glyphs.customParameters[glyphs_name]
        # These parameters can be referred to with the two names in Glyphs
        if (
            glyphs_name in glyphs.customParameters
            and glyphs.customParameters[glyphs_name] == default_value
        ):
            del glyphs.customParameters[glyphs_name]
