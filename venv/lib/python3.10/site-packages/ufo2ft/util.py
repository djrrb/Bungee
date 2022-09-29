import importlib
import logging
import re
from copy import deepcopy
from inspect import currentframe, getfullargspec
from typing import Set

from fontTools import subset, ttLib, unicodedata
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.misc.fixedTools import otRound
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen

logger = logging.getLogger(__name__)


def makeOfficialGlyphOrder(font, glyphOrder=None):
    """Make the final glyph order for 'font'.

    If glyphOrder is None, try getting the font.glyphOrder list.
    If not explicit glyphOrder is defined, sort glyphs alphabetically.

    If ".notdef" glyph is present in the font, force this to always be
    the first glyph (at index 0).
    """
    if glyphOrder is None:
        glyphOrder = getattr(font, "glyphOrder", ())
    names = set(font.keys())
    order = []
    if ".notdef" in names:
        names.remove(".notdef")
        order.append(".notdef")
    for name in glyphOrder:
        if name not in names:
            continue
        names.remove(name)
        order.append(name)
    order.extend(sorted(names))
    return order


class _GlyphSet(dict):
    @classmethod
    def from_layer(cls, font, layerName=None, copy=False, skipExportGlyphs=None):
        """Return a mapping of glyph names to glyph objects from `font`."""
        if layerName is not None:
            layer = font.layers[layerName]
        else:
            layer = font.layers.defaultLayer

        if copy:
            self = _copyLayer(layer, obj_type=cls)
            self.lib = deepcopy(layer.lib)
        else:
            self = cls((g.name, g) for g in layer)
            self.lib = layer.lib

        # If any glyphs in the skipExportGlyphs list are used as components, decompose
        # them in the containing glyphs...
        if skipExportGlyphs:
            for glyph in self.values():
                if any(c.baseGlyph in skipExportGlyphs for c in glyph.components):
                    deepCopyContours(self, glyph, glyph, Transform(), skipExportGlyphs)
                    if hasattr(glyph, "removeComponent"):  # defcon
                        for c in [
                            component
                            for component in glyph.components
                            if component.baseGlyph in skipExportGlyphs
                        ]:
                            glyph.removeComponent(c)
                    else:  # ufoLib2
                        glyph.components[:] = [
                            c
                            for c in glyph.components
                            if c.baseGlyph not in skipExportGlyphs
                        ]
            # ... and then remove them from the glyph set, if even present.
            for glyph_name in skipExportGlyphs:
                if glyph_name in self:
                    del self[glyph_name]

        self.name = layer.name if layerName is not None else None
        return self


def _copyLayer(layer, obj_type=dict):
    try:
        g = next(iter(layer))
    except StopIteration:  # layer is empty
        return obj_type()

    newGlyph = _getNewGlyphFactory(g)
    glyphSet = obj_type()
    for glyph in layer:
        glyphSet[glyph.name] = _copyGlyph(glyph, glyphFactory=newGlyph)
    return glyphSet


def _getNewGlyphFactory(glyph):
    # defcon.Glyph doesn't take a name argument, ufoLib2 requires one...
    cls = glyph.__class__
    if "name" in getfullargspec(cls.__init__).args:

        def newGlyph(name):
            return cls(name=name)

    else:

        def newGlyph(name):
            # use instantiateGlyphObject() to keep any custom sub-element classes
            # https://github.com/googlefonts/ufo2ft/issues/363
            g2 = glyph.layer.instantiateGlyphObject()
            g2.name = name
            return g2

    return newGlyph


def _copyGlyph(glyph, glyphFactory=None, reverseContour=False):
    # copy everything except unused attributes: 'guidelines', 'note', 'image'
    if glyphFactory is None:
        glyphFactory = _getNewGlyphFactory(glyph)

    copy = glyphFactory(glyph.name)
    copy.width = glyph.width
    copy.height = glyph.height
    copy.unicodes = list(glyph.unicodes)
    copy.anchors = [dict(a) for a in glyph.anchors]
    copy.lib = deepcopy(glyph.lib)

    pointPen = copy.getPointPen()
    if reverseContour:
        from fontTools.pens.pointPen import ReverseContourPointPen

        pointPen = ReverseContourPointPen(pointPen)

    glyph.drawPoints(pointPen)

    return copy


def deepCopyContours(
    glyphSet, parent, composite, transformation, specificComponents=None
):
    """Copy contours from component to parent, including nested components.

    specificComponent: an optional list of glyph name strings. If not passed or
    None, decompose all components of a glyph unconditionally and completely. If
    passed, only completely decompose components whose baseGlyph is in the list.
    """

    for nestedComponent in composite.components:
        # Because this function works recursively, test at each turn if we are going to
        # recurse into a specificComponent. If so, set the specificComponents argument
        # to None so we unconditionally decompose the possibly nested component
        # completely.
        specificComponentsEffective = specificComponents
        if specificComponentsEffective:
            if nestedComponent.baseGlyph not in specificComponentsEffective:
                continue
            else:
                specificComponentsEffective = None

        try:
            nestedBaseGlyph = glyphSet[nestedComponent.baseGlyph]
        except KeyError:
            logger.warning(
                "dropping non-existent component '%s' in glyph '%s'",
                nestedComponent.baseGlyph,
                parent.name,
            )
        else:
            deepCopyContours(
                glyphSet,
                parent,
                nestedBaseGlyph,
                transformation.transform(nestedComponent.transformation),
                specificComponents=specificComponentsEffective,
            )

    # Check if there are any contours to copy before instantiating pens.
    if composite != parent and len(composite):
        if transformation == Identity:
            pen = parent.getPen()
        else:
            pen = TransformPen(parent.getPen(), transformation)
            # if the transformation has a negative determinant, it will
            # reverse the contour direction of the component
            xx, xy, yx, yy = transformation[:4]
            if xx * yy - xy * yx < 0:
                pen = ReverseContourPen(pen)

        for contour in composite:
            contour.draw(pen)


def makeUnicodeToGlyphNameMapping(font, glyphOrder=None):
    """Make a unicode: glyph name mapping for this glyph set (dict or Font).

    Raises InvalidFontData exception if multiple glyphs are mapped to the
    same unicode codepoint.
    """
    if glyphOrder is None:
        glyphOrder = makeOfficialGlyphOrder(font)
    mapping = {}
    for glyphName in glyphOrder:
        glyph = font[glyphName]
        unicodes = glyph.unicodes
        for uni in unicodes:
            if uni not in mapping:
                mapping[uni] = glyphName
            else:
                from ufo2ft.errors import InvalidFontData

                InvalidFontData(
                    "cannot map '%s' to U+%04X; already mapped to '%s'"
                    % (glyphName, uni, mapping[uni])
                )
    return mapping


def compileGSUB(featureFile, glyphOrder):
    """Compile and return a GSUB table from `featureFile` (feaLib
    FeatureFile), using the given `glyphOrder` (list of glyph names).
    """
    font = ttLib.TTFont()
    font.setGlyphOrder(glyphOrder)
    addOpenTypeFeatures(font, featureFile, tables={"GSUB"})
    return font.get("GSUB")


def compileGDEF(featureFile, glyphOrder):
    """Compile and return a GDEF table from `featureFile` (feaLib FeatureFile),
    using the given `glyphOrder` (list of glyph names).
    """
    from fontTools.feaLib.ast import TableBlock

    font = ttLib.TTFont()
    font.setGlyphOrder(glyphOrder)
    gdefDefined = False
    for statement in featureFile.statements:
        if isinstance(statement, TableBlock) and statement.name == "GDEF":
            gdefDefined = True

    if not gdefDefined:
        addOpenTypeFeatures(font, featureFile, tables={"GDEF", "GPOS", "GSUB"})
    else:
        addOpenTypeFeatures(font, featureFile, tables={"GDEF"})
    return font.get("GDEF")


def closeGlyphsOverGSUB(gsub, glyphs):
    """Use the FontTools subsetter to perform a closure over the GSUB table
    given the initial `glyphs` (set of glyph names, str). Update the set
    in-place adding all the glyph names that can be reached via GSUB
    substitutions from this initial set.
    """
    subsetter = subset.Subsetter()
    subsetter.glyphs = glyphs
    gsub.closure_glyphs(subsetter)


def classifyGlyphs(unicodeFunc, cmap, gsub=None):
    """'unicodeFunc' is a callable that takes a Unicode codepoint and
    returns a string denoting some Unicode property associated with the
    given character (or None if a character is considered 'neutral').
    'cmap' is a dictionary mapping Unicode codepoints to glyph names.
    'gsub' is an (optional) fonttools GSUB table object, used to find all
    the glyphs that are "reachable" via substitutions from the initial
    sets of glyphs defined in the cmap.

    Returns a dictionary of glyph sets associated with the given Unicode
    properties.
    """
    glyphSets = {}
    neutralGlyphs = set()
    for uv, glyphName in cmap.items():
        key = unicodeFunc(uv)
        if key is None:
            neutralGlyphs.add(glyphName)
        else:
            glyphSets.setdefault(key, set()).add(glyphName)

    if gsub is not None:
        if neutralGlyphs:
            closeGlyphsOverGSUB(gsub, neutralGlyphs)

        for glyphs in glyphSets.values():
            s = glyphs | neutralGlyphs
            closeGlyphsOverGSUB(gsub, s)
            glyphs.update(s - neutralGlyphs)

    return glyphSets


def unicodeInScripts(uv, scripts):
    """Check UnicodeData's ScriptExtension property for unicode codepoint
    'uv' and return True if it intersects with the set of 'scripts' provided,
    False if it does not intersect.
    Return None for 'Common' script ('Zyyy').
    """
    sx = unicodedata.script_extension(chr(uv))
    if "Zyyy" in sx:
        return None
    return not sx.isdisjoint(scripts)


# we consider the 'Common' and 'Inherited' scripts as neutral for
# determining a script horizontal direction
DFLT_SCRIPTS = {"Zyyy", "Zinh"}


def unicodeScriptDirection(uv):
    sc = unicodedata.script(chr(uv))
    if sc in DFLT_SCRIPTS:
        return None
    return unicodedata.script_horizontal_direction(sc)


def calcCodePageRanges(unicodes):
    """Given a set of Unicode codepoints (integers), calculate the
    corresponding OS/2 CodePage range bits.
    This is a direct translation of FontForge implementation:
    https://github.com/fontforge/fontforge/blob/7b2c074/fontforge/tottf.c#L3158
    """
    codepageRanges = set()

    chars = [chr(u) for u in unicodes]

    hasAscii = set(range(0x20, 0x7E)).issubset(unicodes)
    hasLineart = "┤" in chars

    for char in chars:
        if char == "Þ" and hasAscii:
            codepageRanges.add(0)  # Latin 1
        elif char == "Ľ" and hasAscii:
            codepageRanges.add(1)  # Latin 2: Eastern Europe
            if hasLineart:
                codepageRanges.add(58)  # Latin 2
        elif char == "Б":
            codepageRanges.add(2)  # Cyrillic
            if "Ѕ" in chars and hasLineart:
                codepageRanges.add(57)  # IBM Cyrillic
            if "╜" in chars and hasLineart:
                codepageRanges.add(49)  # MS-DOS Russian
        elif char == "Ά":
            codepageRanges.add(3)  # Greek
            if hasLineart and "½" in chars:
                codepageRanges.add(48)  # IBM Greek
            if hasLineart and "√" in chars:
                codepageRanges.add(60)  # Greek, former 437 G
        elif char == "İ" and hasAscii:
            codepageRanges.add(4)  # Turkish
            if hasLineart:
                codepageRanges.add(56)  # IBM turkish
        elif char == "א":
            codepageRanges.add(5)  # Hebrew
            if hasLineart and "√" in chars:
                codepageRanges.add(53)  # Hebrew
        elif char == "ر":
            codepageRanges.add(6)  # Arabic
            if "√" in chars:
                codepageRanges.add(51)  # Arabic
            if hasLineart:
                codepageRanges.add(61)  # Arabic; ASMO 708
        elif char == "ŗ" and hasAscii:
            codepageRanges.add(7)  # Windows Baltic
            if hasLineart:
                codepageRanges.add(59)  # MS-DOS Baltic
        elif char == "₫" and hasAscii:
            codepageRanges.add(8)  # Vietnamese
        elif char == "ๅ":
            codepageRanges.add(16)  # Thai
        elif char == "エ":
            codepageRanges.add(17)  # JIS/Japan
        elif char == "ㄅ":
            codepageRanges.add(18)  # Chinese: Simplified chars
        elif char == "ㄱ":
            codepageRanges.add(19)  # Korean wansung
        elif char == "央":
            codepageRanges.add(20)  # Chinese: Traditional chars
        elif char == "곴":
            codepageRanges.add(21)  # Korean Johab
        elif char == "♥" and hasAscii:
            codepageRanges.add(30)  # OEM Character Set
        # TODO: Symbol bit has a special meaning (check the spec), we need
        # to confirm if this is wanted by default.
        # elif chr(0xF000) <= char <= chr(0xF0FF):
        #    codepageRanges.add(31)          # Symbol Character Set
        elif char == "þ" and hasAscii and hasLineart:
            codepageRanges.add(54)  # MS-DOS Icelandic
        elif char == "╚" and hasAscii:
            codepageRanges.add(62)  # WE/Latin 1
            codepageRanges.add(63)  # US
        elif hasAscii and hasLineart and "√" in chars:
            if char == "Å":
                codepageRanges.add(50)  # MS-DOS Nordic
            elif char == "é":
                codepageRanges.add(52)  # MS-DOS Canadian French
            elif char == "õ":
                codepageRanges.add(55)  # MS-DOS Portuguese

    if hasAscii and "‰" in chars and "∑" in chars:
        codepageRanges.add(29)  # Macintosh Character Set (US Roman)

    # when no codepage ranges can be enabled, fall back to enabling bit 0
    # (Latin 1) so that the font works in MS Word:
    # https://github.com/googlei18n/fontmake/issues/468
    if not codepageRanges:
        codepageRanges.add(0)

    return codepageRanges


class _LazyFontName:
    def __init__(self, font):
        self.font = font

    def __str__(self):
        from ufo2ft.fontInfoData import getAttrWithFallback

        return getAttrWithFallback(self.font.info, "postscriptFontName")


def getDefaultMasterFont(designSpaceDoc):
    defaultSource = designSpaceDoc.findDefault()
    if not defaultSource:
        from ufo2ft.errors import InvalidDesignSpaceData

        raise InvalidDesignSpaceData(
            "Can't find base (neutral) master in DesignSpace document"
        )
    if not defaultSource.font:
        from ufo2ft.errors import InvalidDesignSpaceData

        raise InvalidDesignSpaceData(
            "DesignSpace source '%s' is missing required 'font' attribute"
            % getattr(defaultSource, "name", "<Unknown>")
        )
    return defaultSource.font


def _getDefaultNotdefGlyph(designSpaceDoc):
    from ufo2ft.errors import InvalidDesignSpaceData

    try:
        baseUfo = getDefaultMasterFont(designSpaceDoc)
    except InvalidDesignSpaceData:
        notdefGlyph = None
    else:
        # unlike ufoLib2, defcon has no Font.get() method
        try:
            notdefGlyph = baseUfo[".notdef"]
        except KeyError:
            notdefGlyph = None
    return notdefGlyph


# NOTE about the security risk involved in using eval: the function below is
# meant to be used to parse string coming from the command-line, which is
# inherently "trusted"; if that weren't the case, a potential attacker
# could do worse things than segfaulting the Python interpreter...


def _kwargsEval(s):
    return eval(
        "dict(%s)" % s, {"__builtins__": {"True": True, "False": False, "dict": dict}}
    )


_pluginSpecRE = re.compile(
    r"(?:([\w\.]+)::)?"  # MODULE_NAME + '::'
    r"(\w+)"  # CLASS_NAME [required]
    r"(?:\((.*)\))?"  # (KWARGS)
)


def _loadPluginFromString(spec, moduleName, isValidFunc):
    spec = spec.strip()
    m = _pluginSpecRE.match(spec)
    if not m or (m.end() - m.start()) != len(spec):
        raise ValueError(spec)
    moduleName = m.group(1) or moduleName
    className = m.group(2)
    kwargs = m.group(3)

    module = importlib.import_module(moduleName)
    klass = getattr(module, className)
    if not isValidFunc(klass):
        raise TypeError(klass)
    try:
        options = _kwargsEval(kwargs) if kwargs else {}
    except SyntaxError as e:
        raise ValueError("options have incorrect format: %r" % kwargs) from e

    return klass(**options)


def quantize(number, factor):
    """Round to a multiple of the given parameter"""
    return factor * otRound(number / factor)


def init_kwargs(kwargs, defaults):
    """Initialise kwargs default values.

    To be used as the first function in top-level `ufo2ft.compile*` functions.

    Raise TypeError with unexpected keyword arguments (missing from 'defaults').
    """
    extra_kwargs = set(kwargs).difference(defaults)
    if extra_kwargs:
        # get the name of the function that called init_kwargs
        func_name = currentframe().f_back.f_code.co_name
        raise TypeError(
            f"{func_name}() got unexpected keyword arguments: "
            f"{', '.join(repr(k) for k in extra_kwargs)}"
        )
    return {k: (kwargs[k] if k in kwargs else v) for k, v in defaults.items()}


def prune_unknown_kwargs(kwargs, *callables):
    """Inspect callables and return a new dict skipping any unknown arguments.

    To be used after `init_kwargs` to narrow down arguments for underlying code.
    """
    known_args = set()
    for func in callables:
        known_args.update(getfullargspec(func).args)
    return {k: v for k, v in kwargs.items() if k in known_args}


def ensure_all_sources_have_names(doc: DesignSpaceDocument) -> None:
    """Change in-place the given document to make sure that all <source> elements
    have a unique name assigned.

    This may rename sources with a "temp_master.N" name, designspaceLib's default
    stand-in.
    """
    used_names: Set[str] = set()
    counter = 0
    for source in doc.sources:
        while source.name is None or source.name in used_names:
            source.name = f"temp_master.{counter}"
            counter += 1
        used_names.add(source.name)


def getMaxComponentDepth(glyph, glyphSet, maxComponentDepth=0):
    """Return the height of a composite glyph's tree of components.

    This is equal to the depth of its deepest node, where the depth
    means the number of edges (component references) from the node
    to the tree's root.

    For glyphs that contain no components, only contours, this is 0.
    Composite glyphs have max component depth of 1 or greater.
    """
    if not glyph.components:
        return maxComponentDepth

    maxComponentDepth += 1

    initialMaxComponentDepth = maxComponentDepth
    for component in glyph.components:
        try:
            baseGlyph = glyphSet[component.baseGlyph]
        except KeyError:
            continue
        componentDepth = getMaxComponentDepth(
            baseGlyph, glyphSet, initialMaxComponentDepth
        )
        maxComponentDepth = max(maxComponentDepth, componentDepth)

    return maxComponentDepth
