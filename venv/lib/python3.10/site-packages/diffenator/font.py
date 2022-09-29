"""Module for DFont"""
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.varLib.mutator import instantiateVariableFont
from diffenator.hbinput import HbInputGenerator
from diffenator.dump import (
        DumpAnchors,
        dump_kerning,
        dump_glyphs,
        dump_glyph_metrics,
        dump_attribs,
        dump_nametable,
        dump_gdef
)
from diffenator.constants import FTHintMode
from copy import copy
import uharfbuzz as hb
import freetype
from freetype.raw import *
from freetype import (
        FT_PIXEL_MODE_MONO,
        FT_PIXEL_MODE_GRAY,
        FT_Pointer,
        FT_Bitmap,
        FT_Fixed,
        FT_Set_Var_Design_Coordinates
)
import sys
import logging
try:
    # try and import unicodedata2 backport for py2.7.
    import unicodedata2 as uni
except ImportError:
    # on py2.7, this module only goes up to unicode 5.2.0 so it won't support
    # recently added glyphs.
    import unicodedata as uni
if sys.version_info.major == 3:
    unicode = str


logger = logging.getLogger('fontdiffenator')


WEIGHT_NAME_TO_FVAR = {
    "Thin": 100,
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
    "Black": 900
}

WIDTH_CLASS_TO_FVAR = {
    1: 50, # UltraCondensed
    2: 62.5, # ExtraCondensed
    3: 75, # Condensed
    4: 87.5, # SemiCondensed
    5: 100, # Normal
    6: 112.5, # SemiExpanded
    7: 125, # Expanded
    8: 150, # ExtraExpanded
    9: 200, # UltraExpanded
}

WIDTH_NAME_TO_FVAR = {
    "UltraCondensed": 50,
    "ExtraCondensed": 62.5,
    "Condensed": 75,
    "SemiCondensed": 87.5,
    "Normal": 100,
    "SemiExpanded": 112.5,
    "Expanded": 125,
    "ExtraExpanded": 150,
    "UltraExpanded": 200
}

class DFont(TTFont):
    """Container font for ttfont, freetype and hb fonts"""
    def __init__(self, path=None, lazy=False, size=1500,
                 ft_load_glyph_flags=FTHintMode.UNHINTED):
        self.path = path
        self.ttfont = TTFont(self.path)

        has_outlines = self.ttfont.has_key("glyf") or self.ttfont.has_key("CFF ")
        if not has_outlines:
            # Create faux empty glyf table with empty glyphs to make
            # it a valid font, e.g. for old-style CBDT/CBLC fonts
            logger.warning("No outlines present, treating {} as bitmap font".format(self.path))
            self.ttfont["glyf"] = newTable("glyf")
            self.ttfont["glyf"].glyphs = {}
            pen = TTGlyphPen({})
            for name in self.ttfont.getGlyphOrder():
                self.ttfont["glyf"].glyphs[name] = pen.glyph()

        self._src_ttfont = TTFont(self.path)
        self.glyphset = None
        self.recalc_glyphset()
        self.axis_order = None
        self.instance_coordinates = self._get_dflt_instance_coordinates()
        self.instances_coordinates = self._get_instances_coordinates()
        self.glyphs = self.marks = self.mkmks = self.kerns = \
            self.glyph_metrics = self.names = self.attribs = None

        self.ftfont = freetype.Face(self.path)
        self.ftslot = self.ftfont.glyph
        self.ft_load_glyph_flags=ft_load_glyph_flags

        self.size = size
        if self.ftfont.is_scalable:
            self.ftfont.set_char_size(self.size)

        with open(self.path, 'rb') as fontfile:
            self._fontdata = fontfile.read()
        self.hbface = hb.Face.create(self._fontdata)
        self.hbfont = hb.Font.create(self.hbface)

        self.hbfont.scale = (self.size, self.size)

        if not lazy:
            self.recalc_tables()

    def _get_instances_coordinates(self):
        results = {}
        if self.is_variable:
            for inst in self._src_ttfont['fvar'].instances:
                inst_name = self._src_ttfont['name'].getName(inst.subfamilyNameID, 3, 1, 1033).toUnicode()
                results[inst_name] = inst.coordinates
        return results

    def _get_dflt_instance_coordinates(self):
        if self.is_variable:
            return {i.axisTag: i.defaultValue for i in self._src_ttfont['fvar'].axes}
        return None

    def glyph(self, name):
        return self.glyphset[name]

    def recalc_glyphset(self):
        if not 'cmap' in self.ttfont.keys():
            self.glyphset = []
        inputs = InputGenerator(self).all_inputs()
        self.glyphset = {g.name: g for g in inputs}

    @property
    def is_variable(self):
        if 'fvar' in self._src_ttfont:
            return True
        return False

    def set_variations(self, axes):
        """Instantiate a ttfont VF with axes vals"""
        logger.debug("Setting variations to {}".format(axes))
        if self.is_variable:
            font = instantiateVariableFont(self._src_ttfont, axes, inplace=False)
            self.ttfont = copy(font)
            self.axis_order = [a.axisTag for a in self._src_ttfont['fvar'].axes]
            self.instance_coordinates = {a.axisTag: a.defaultValue for a in
                                    self._src_ttfont['fvar'].axes}
            for axis in axes:
                if axis in self.instance_coordinates:
                    self.instance_coordinates[axis] = axes[axis]
                else:
                    logger.info("font has no axis called {}".format(axis))
            self.recalc_tables()

            coords = []
            for name in self.axis_order:
                coord = FT_Fixed(int(self.instance_coordinates[name]) << 16)
                coords.append(coord)
            ft_coords = (FT_Fixed * len(coords))(*coords)
            FT_Set_Var_Design_Coordinates(self.ftfont._FT_Face, len(ft_coords), ft_coords)
            self.hbface = hb.Face.create(self._fontdata)
            self.hbfont = hb.Font.create(self.hbface)
            self.hbfont.set_variations(self.instance_coordinates)
            self.hbfont.scale = (self.size, self.size)
        else:
            logger.info("Not vf")

    def set_variations_from_static(self, static_font):
        """Set VF font variations so they match a static font."""
        if not self.is_variable:
            raise Exception("Not a variable font")

        # Use an fvar instance if its name matches the static font's
        # typographic subfamily name or subfamily name
        subfamilyname = static_font.ttfont['name'].getName(2, 3, 1, 1033)
        typosubfamilyname = static_font.ttfont['name'].getName(17, 3, 1, 1033)

        anysubfamilyname = typosubfamilyname or subfamilyname
        subfamilyname = anysubfamilyname.toUnicode() if anysubfamilyname else ""

        # The Google Fonts v1 api can only handle the wght axis. For families
        # which have widths, we have to release them as a seperate family,
        # https://fonts.google.com/?query=condensed
        # To distinguish the width family from the normal family, we append
        # the width to the family name e.g Roboto Condensed
        filename = os.path.basename(static_font.path)
        family_name = filename.split("-")[0]
        family_name_width = find_token(family_name, list(WIDTH_NAME_TO_FVAR.keys()))
        if family_name_width:
            subfamilyname = f"{family_name_width} {subfamilyname}"

        if subfamilyname in self.instances_coordinates:
            logger.debug(f"Instance name '{subfamilyname}' matches static font "
                "subfamily names. Setting variations using this instance.")
            variations = self.instances_coordinates[subfamilyname]
            self.set_variations(variations)
            return

        # if the font doesn't contain an instance name which matches the
        # static font, infer the correct values
        logger.debug(f"Font does not contain an instance name which matches "
            f"static font subfamily names '{subfamilyname}'. Inferring "
            "values instead.")
        variations = {}
        # wght
        parsed_weight = find_token(
            os.path.basename(static_font.path),
            list(WEIGHT_NAME_TO_FVAR.keys())
        )
        if parsed_weight:
            variations["wght"] = WEIGHT_NAME_TO_FVAR[parsed_weight]
        else:
            logger.debug(f"Couldn't parse weight value from {static_font.path}")
            weight_class = static_font.ttfont["OS/2"].usWeightClass
            # Google Fonts used to set the usWeightClass of Thin static
            # fonts to 250 and the ExtraLight to 275. Override these
            # values with 100 and 200.
            if weight_class == 250:
                weight_class = 100
            if weight_class == 275:
                weight_class = 200
            variations["wght"] = weight_class

        # wdth
        # We cannot simply use OS/2.usWidthClass since Google Fonts
        # releases Condensed styles as new families. These new families
        # have a usWidthClass of 5 (Normal).
        parsed_width = find_token(
            os.path.basename(static_font.path),
            list(WIDTH_NAME_TO_FVAR.keys())
        )
        if parsed_width:
            variations["wdth"] = WIDTH_NAME_TO_FVAR[parsed_width]
        else:
            logger.debug(f"Couldn't parse weight value from {static_font.path}")
            width_class = static_font.ttfont["OS/2"].usWidthClass
            variations["wdth"] = WIDTH_CLASS_TO_FVAR[width_class]
        # TODO (M Foley) add slnt axes
        self.set_variations(variations)

    def recalc_tables(self):
        """Recalculate DFont tables"""
        self.recalc_glyphset()
        anchors = DumpAnchors(self)
        self.glyphs = dump_glyphs(self)
        self.marks = anchors.marks_table
        self.mkmks = anchors.mkmks_table
        self.attribs = dump_attribs(self)
        self.names = dump_nametable(self)
        self.kerns = dump_kerning(self)
        self.metrics = dump_glyph_metrics(self)
        self.gdef_base, self.gdef_mark = dump_gdef(self)


class InputGenerator(HbInputGenerator):
    """Taken from Nototool's HbIntputGenerator"""

    def all_inputs(self, warn=False):
        """Generate harfbuzz inputs for all glyphs in a given font."""

        inputs = []
        glyph_set = self.font.ttfont.getGlyphSet()
        for name in self.font.ttfont.getGlyphOrder():
            is_zero_width = glyph_set[name].width == 0
            cur_input = self.input_from_name(name, pad=is_zero_width)
            if cur_input is not None:
                features, characters = cur_input
                characters = characters.replace(' ', '')
                inputs.append(
                    Glyph(name, features, unicode(characters), self.font)
                )
            else:
                features = ('',)
                inputs.append(Glyph(name, features, '', self.font))
        return inputs

    def input_from_name(self, name, seen=None, pad=False):
        """Given glyph name, return input to harbuzz to render this glyph.

        Returns input in the form of a (features, text) tuple, where `features`
        is a list of feature tags to activate and `text` is an input string.

        Argument `seen` is used by the method to avoid following cycles when
        recursively looking for possible input. `pad` can be used to add
        whitespace to text output, for non-spacing glyphs.

        Can return None in two situations: if no possible input is found (no
        simple unicode mapping or substitution rule exists to generate the
        glyph), or if the requested glyph already exists in `seen` (in which
        case this path of generating input should not be followed further).
        """

        if name in self.memo:
            return self.memo[name]

        inputs = []

        # avoid following cyclic paths through features
        if seen is None:
            seen = set()
        if name in seen:
            return None
        seen.add(name)

        # see if this glyph has a simple unicode mapping
        if name in self.reverse_cmap:
            text = chr(self.reverse_cmap[name])
            if text != chr(0):
                inputs.append(((), text))

        # check the substitution features
        inputs.extend(self._inputs_from_gsub(name, seen))
        # seen.remove(name)

        # since this method sometimes returns None to avoid cycles, the
        # recursive calls that it makes might have themselves returned None,
        # but we should avoid returning None here if there are other options
        inputs = [i for i in inputs if i is not None]
        if not inputs:
            return None

        features, text = min(inputs)
        # can't pad if we don't support space
        if pad and self.space_width > 0:
            width, space = self.widths[name], self.space_width
            padding = ' ' * (width // space + (1 if width % space else 0))
            text = padding + text
        self.memo[name] = features, text
        return self.memo[name]


class Glyph:
    def __init__(self, name, features, characters, font):
        self.name = name
        self.features = features
        self.characters = characters
        self.combining = True if characters and uni.combining(characters[0]) else False
        self.key = self.characters + ''.join(features)
        self.font = font
        self.index = self.font.ttfont.getGlyphID(name)
        self.width = self.font.ttfont['hmtx'].metrics[name][0]

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


def find_token(string, tokens):
    """Find the largest token within a string e.g

    > find_token("aab", ["a, "aa",..])
    'aa'"""
    tokens = sorted(tokens, key=lambda k: len(k), reverse=True)
    for token in tokens:
        if token in string:
            return token
    return None


def font_matcher(font_before, font_after, axes=None):
    """Instantiate a variable font so it matches a static font. If two
    variable fonts and an axes dict is provided, instantiate both
    variable fonts using the axes dict."""
    if font_before.is_variable and not font_after.is_variable:
        font_before.set_variations_from_static(font_after)

    elif not font_before.is_variable and font_after.is_variable:
        font_after.set_variations_from_static(font_before)

    elif font_before.is_variable and font_after.is_variable and axes:
        variations = {s.split('=')[0]: float(s.split('=')[1]) for s
                      in axes.split(", ")}
        font_before.set_variations(variations)
        font_after.set_variations(variations)

