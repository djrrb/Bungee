import logging
import math
from collections import Counter, namedtuple
from io import BytesIO
from types import SimpleNamespace

from fontTools.cffLib import (
    CharStrings,
    GlobalSubrsIndex,
    IndexedStrings,
    PrivateDict,
    SubrsIndex,
    TopDict,
    TopDictIndex,
)
from fontTools.misc.arrayTools import unionRect
from fontTools.misc.fixedTools import otRound
from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.pens.pointPen import SegmentToPointPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPointPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import USE_MY_METRICS, Glyph
from fontTools.ttLib.tables._h_e_a_d import mac_epoch_diff
from fontTools.ttLib.tables.O_S_2f_2 import Panose

from ufo2ft.constants import (
    COLOR_LAYERS_KEY,
    COLOR_PALETTES_KEY,
    COLR_CLIP_BOXES_KEY,
    OPENTYPE_META_KEY,
    UNICODE_VARIATION_SEQUENCES_KEY,
)
from ufo2ft.errors import InvalidFontData
from ufo2ft.fontInfoData import (
    dateStringForNow,
    dateStringToTimeValue,
    getAttrWithFallback,
    intListToNum,
    normalizeStringForPostscript,
)
from ufo2ft.util import (
    _copyGlyph,
    calcCodePageRanges,
    makeOfficialGlyphOrder,
    makeUnicodeToGlyphNameMapping,
)

logger = logging.getLogger(__name__)


BoundingBox = namedtuple("BoundingBox", ["xMin", "yMin", "xMax", "yMax"])
EMPTY_BOUNDING_BOX = BoundingBox(0, 0, 0, 0)


def _isNonBMP(s):
    for c in s:
        if ord(c) > 65535:
            return True
    return False


def _getVerticalOrigin(font, glyph):
    if hasattr(glyph, "verticalOrigin") and glyph.verticalOrigin is not None:
        verticalOrigin = glyph.verticalOrigin
    else:
        os2 = font.get("OS/2")
        typo_ascender = os2.sTypoAscender if os2 is not None else 0
        verticalOrigin = typo_ascender
    return otRound(verticalOrigin)


class BaseOutlineCompiler:
    """Create a feature-less outline binary."""

    sfntVersion = None
    tables = frozenset(
        [
            "head",
            "hmtx",
            "hhea",
            "name",
            "maxp",
            "cmap",
            "OS/2",
            "post",
            "vmtx",
            "vhea",
            "COLR",
            "CPAL",
            "meta",
        ]
    )

    def __init__(
        self,
        font,
        glyphSet=None,
        glyphOrder=None,
        tables=None,
        notdefGlyph=None,
        colrLayerReuse=True,
    ):
        self.ufo = font
        # use the previously filtered glyphSet, if any
        if glyphSet is None:
            glyphSet = {g.name: g for g in font}
        self.makeMissingRequiredGlyphs(font, glyphSet, self.sfntVersion, notdefGlyph)
        self.allGlyphs = glyphSet
        # store the glyph order
        if glyphOrder is None:
            glyphOrder = font.glyphOrder
        self.glyphOrder = self.makeOfficialGlyphOrder(glyphOrder)
        # make a reusable character mapping
        self.unicodeToGlyphNameMapping = self.makeUnicodeToGlyphNameMapping()
        if tables is not None:
            self.tables = tables
        self.colrLayerReuse = colrLayerReuse
        # cached values defined later on
        self._glyphBoundingBoxes = None
        self._fontBoundingBox = None
        self._compiledGlyphs = None

    def compile(self):
        """
        Compile the OpenType binary.
        """
        self.otf = TTFont(sfntVersion=self.sfntVersion)

        # only compile vertical metrics tables if vhea metrics are defined
        vertical_metrics = [
            "openTypeVheaVertTypoAscender",
            "openTypeVheaVertTypoDescender",
            "openTypeVheaVertTypoLineGap",
        ]
        self.vertical = all(
            getAttrWithFallback(self.ufo.info, metric) is not None
            for metric in vertical_metrics
        )
        self.colorLayers = (
            COLOR_LAYERS_KEY in self.ufo.lib and COLOR_PALETTES_KEY in self.ufo.lib
        )
        self.meta = OPENTYPE_META_KEY in self.ufo.lib

        # write the glyph order
        self.otf.setGlyphOrder(self.glyphOrder)

        # populate basic tables
        self.setupTable_head()
        self.setupTable_hmtx()
        self.setupTable_hhea()
        self.setupTable_name()
        self.setupTable_maxp()
        self.setupTable_cmap()
        self.setupTable_OS2()
        self.setupTable_post()
        if self.vertical:
            self.setupTable_vmtx()
            self.setupTable_vhea()
        if self.colorLayers:
            self.setupTable_COLR()
            self.setupTable_CPAL()
        if self.meta:
            self.setupTable_meta()
        self.setupOtherTables()
        self.importTTX()

        return self.otf

    def compileGlyphs(self):
        """Compile glyphs and return dict keyed by glyph name.

        **This should not be called externally.**
        Subclasses must override this method to handle compilation of glyphs.
        """
        raise NotImplementedError

    def getCompiledGlyphs(self):
        if self._compiledGlyphs is None:
            self._compiledGlyphs = self.compileGlyphs()
        return self._compiledGlyphs

    def makeGlyphsBoundingBoxes(self):
        """
        Make bounding boxes for all the glyphs, and return a dictionary of
        BoundingBox(xMin, xMax, yMin, yMax) namedtuples keyed by glyph names.
        The bounding box of empty glyphs (without contours or components) is
        set to None.
        The bbox values are integers.

        **This should not be called externally.**
        Subclasses must override this method to handle the bounds creation for
        their specific glyph type.
        """
        raise NotImplementedError

    @property
    def glyphBoundingBoxes(self):
        if self._glyphBoundingBoxes is None:
            self._glyphBoundingBoxes = self.makeGlyphsBoundingBoxes()
        return self._glyphBoundingBoxes

    def makeFontBoundingBox(self):
        """
        Make a bounding box for the font.

        **This should not be called externally.** Subclasses
        may override this method to handle the bounds creation
        in a different way if desired.
        """
        fontBox = None
        for glyphBox in self.glyphBoundingBoxes.values():
            if glyphBox is None:
                continue
            if fontBox is None:
                fontBox = glyphBox
            else:
                fontBox = unionRect(fontBox, glyphBox)
        if fontBox is None:  # unlikely
            fontBox = EMPTY_BOUNDING_BOX
        return fontBox

    @property
    def fontBoundingBox(self):
        if self._fontBoundingBox is None:
            self._fontBoundingBox = self.makeFontBoundingBox()
        return self._fontBoundingBox

    def makeUnicodeToGlyphNameMapping(self):
        """
        Make a ``unicode : glyph name`` mapping for the font.

        **This should not be called externally.** Subclasses
        may override this method to handle the mapping creation
        in a different way if desired.
        """
        return makeUnicodeToGlyphNameMapping(self.allGlyphs, self.glyphOrder)

    @staticmethod
    def makeMissingRequiredGlyphs(font, glyphSet, sfntVersion, notdefGlyph=None):
        """
        Add .notdef to the glyph set if it is not present.

        **This should not be called externally.** Subclasses
        may override this method to handle the glyph creation
        in a different way if desired.
        """
        if ".notdef" in glyphSet:
            return

        reverseContour = sfntVersion == "\000\001\000\000"
        if notdefGlyph:
            notdefGlyph = _copyGlyph(notdefGlyph, reverseContour=reverseContour)
        else:
            unitsPerEm = otRound(getAttrWithFallback(font.info, "unitsPerEm"))
            ascender = otRound(getAttrWithFallback(font.info, "ascender"))
            descender = otRound(getAttrWithFallback(font.info, "descender"))
            defaultWidth = otRound(unitsPerEm * 0.5)
            notdefGlyph = StubGlyph(
                name=".notdef",
                width=defaultWidth,
                unitsPerEm=unitsPerEm,
                ascender=ascender,
                descender=descender,
                reverseContour=reverseContour,
            )

        glyphSet[".notdef"] = notdefGlyph

    def makeOfficialGlyphOrder(self, glyphOrder):
        """
        Make the final glyph order.

        **This should not be called externally.** Subclasses
        may override this method to handle the order creation
        in a different way if desired.
        """
        return makeOfficialGlyphOrder(self.allGlyphs, glyphOrder)

    # --------------
    # Table Builders
    # --------------

    def setupTable_gasp(self):
        if "gasp" not in self.tables:
            return

        self.otf["gasp"] = gasp = newTable("gasp")
        gasp_ranges = dict()
        for record in self.ufo.info.openTypeGaspRangeRecords:
            rangeMaxPPEM = record["rangeMaxPPEM"]
            behavior_bits = record["rangeGaspBehavior"]
            rangeGaspBehavior = intListToNum(behavior_bits, 0, 4)
            gasp_ranges[rangeMaxPPEM] = rangeGaspBehavior
        gasp.gaspRange = gasp_ranges

    def setupTable_head(self):
        """
        Make the head table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "head" not in self.tables:
            return

        self.otf["head"] = head = newTable("head")
        font = self.ufo
        head.checkSumAdjustment = 0
        head.tableVersion = 1.0
        head.magicNumber = 0x5F0F3CF5

        # version numbers
        # limit minor version to 3 digits as recommended in OpenType spec:
        # https://www.microsoft.com/typography/otspec/recom.htm
        versionMajor = getAttrWithFallback(font.info, "versionMajor")
        versionMinor = getAttrWithFallback(font.info, "versionMinor")
        fullFontRevision = float("%d.%03d" % (versionMajor, versionMinor))
        head.fontRevision = round(fullFontRevision, 3)
        if head.fontRevision != fullFontRevision:
            logger.warning(
                "Minor version in %s has too many digits and won't fit into "
                "the head table's fontRevision field; rounded to %s.",
                fullFontRevision,
                head.fontRevision,
            )

        # upm
        head.unitsPerEm = otRound(getAttrWithFallback(font.info, "unitsPerEm"))

        # times
        head.created = (
            dateStringToTimeValue(getAttrWithFallback(font.info, "openTypeHeadCreated"))
            - mac_epoch_diff
        )
        head.modified = dateStringToTimeValue(dateStringForNow()) - mac_epoch_diff

        # bounding box
        xMin, yMin, xMax, yMax = self.fontBoundingBox
        head.xMin = otRound(xMin)
        head.yMin = otRound(yMin)
        head.xMax = otRound(xMax)
        head.yMax = otRound(yMax)

        # style mapping
        styleMapStyleName = getAttrWithFallback(font.info, "styleMapStyleName")
        macStyle = []
        if styleMapStyleName == "bold":
            macStyle = [0]
        elif styleMapStyleName == "bold italic":
            macStyle = [0, 1]
        elif styleMapStyleName == "italic":
            macStyle = [1]
        head.macStyle = intListToNum(macStyle, 0, 16)

        # misc
        head.flags = intListToNum(
            getAttrWithFallback(font.info, "openTypeHeadFlags"), 0, 16
        )
        head.lowestRecPPEM = otRound(
            getAttrWithFallback(font.info, "openTypeHeadLowestRecPPEM")
        )
        head.fontDirectionHint = 2
        head.indexToLocFormat = 0
        head.glyphDataFormat = 0

    def setupTable_name(self):
        """
        Make the name table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "name" not in self.tables:
            return

        font = self.ufo
        self.otf["name"] = name = newTable("name")
        name.names = []

        # Set name records from font.info.openTypeNameRecords
        for nameRecord in getAttrWithFallback(font.info, "openTypeNameRecords"):
            nameId = nameRecord["nameID"]
            platformId = nameRecord["platformID"]
            platEncId = nameRecord["encodingID"]
            langId = nameRecord["languageID"]
            # on Python 2, plistLib (used by ufoLib) returns unicode strings
            # only when plist data contain non-ascii characters, and returns
            # ascii-encoded bytes when it can. On the other hand, fontTools's
            # name table `setName` method wants unicode strings, so we must
            # decode them first
            nameVal = nameRecord["string"]
            name.setName(nameVal, nameId, platformId, platEncId, langId)

        # Build name records
        familyName = getAttrWithFallback(font.info, "styleMapFamilyName")
        styleName = getAttrWithFallback(font.info, "styleMapStyleName").title()
        preferredFamilyName = getAttrWithFallback(
            font.info, "openTypeNamePreferredFamilyName"
        )
        preferredSubfamilyName = getAttrWithFallback(
            font.info, "openTypeNamePreferredSubfamilyName"
        )
        fullName = f"{preferredFamilyName} {preferredSubfamilyName}"

        nameVals = {
            0: getAttrWithFallback(font.info, "copyright"),
            1: familyName,
            2: styleName,
            3: getAttrWithFallback(font.info, "openTypeNameUniqueID"),
            4: fullName,
            5: getAttrWithFallback(font.info, "openTypeNameVersion"),
            6: getAttrWithFallback(font.info, "postscriptFontName"),
            7: getAttrWithFallback(font.info, "trademark"),
            8: getAttrWithFallback(font.info, "openTypeNameManufacturer"),
            9: getAttrWithFallback(font.info, "openTypeNameDesigner"),
            10: getAttrWithFallback(font.info, "openTypeNameDescription"),
            11: getAttrWithFallback(font.info, "openTypeNameManufacturerURL"),
            12: getAttrWithFallback(font.info, "openTypeNameDesignerURL"),
            13: getAttrWithFallback(font.info, "openTypeNameLicense"),
            14: getAttrWithFallback(font.info, "openTypeNameLicenseURL"),
            16: preferredFamilyName,
            17: preferredSubfamilyName,
            18: getAttrWithFallback(font.info, "openTypeNameCompatibleFullName"),
            19: getAttrWithFallback(font.info, "openTypeNameSampleText"),
            21: getAttrWithFallback(font.info, "openTypeNameWWSFamilyName"),
            22: getAttrWithFallback(font.info, "openTypeNameWWSSubfamilyName"),
        }

        # don't add typographic names if they are the same as the legacy ones
        if nameVals[1] == nameVals[16]:
            del nameVals[16]
        if nameVals[2] == nameVals[17]:
            del nameVals[17]
        # postscript font name
        if nameVals[6]:
            nameVals[6] = normalizeStringForPostscript(nameVals[6])

        for nameId in sorted(nameVals.keys()):
            nameVal = nameVals[nameId]
            if not nameVal:
                continue
            platformId = 3
            platEncId = 10 if _isNonBMP(nameVal) else 1
            langId = 0x409
            # Set built name record if not set yet
            if name.getName(nameId, platformId, platEncId, langId):
                continue
            name.setName(nameVal, nameId, platformId, platEncId, langId)

    def setupTable_maxp(self):
        """
        Make the maxp table.

        **This should not be called externally.** Subclasses
        must override or supplement this method to handle the
        table creation for either CFF or TT data.
        """
        raise NotImplementedError

    def setupTable_cmap(self):
        """
        Make the cmap table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "cmap" not in self.tables:
            return

        from fontTools.ttLib.tables._c_m_a_p import cmap_format_4

        nonBMP = {k: v for k, v in self.unicodeToGlyphNameMapping.items() if k > 65535}
        if nonBMP:
            mapping = {
                k: v for k, v in self.unicodeToGlyphNameMapping.items() if k <= 65535
            }
        else:
            mapping = dict(self.unicodeToGlyphNameMapping)
        # mac
        cmap4_0_3 = cmap_format_4(4)
        cmap4_0_3.platformID = 0
        cmap4_0_3.platEncID = 3
        cmap4_0_3.language = 0
        cmap4_0_3.cmap = mapping
        # windows
        cmap4_3_1 = cmap_format_4(4)
        cmap4_3_1.platformID = 3
        cmap4_3_1.platEncID = 1
        cmap4_3_1.language = 0
        cmap4_3_1.cmap = mapping
        # store
        self.otf["cmap"] = cmap = newTable("cmap")
        cmap.tableVersion = 0
        cmap.tables = [cmap4_0_3, cmap4_3_1]
        # If we have glyphs outside Unicode BMP, we must set another
        # subtable that can hold longer codepoints for them.
        if nonBMP:
            from fontTools.ttLib.tables._c_m_a_p import cmap_format_12

            nonBMP.update(mapping)
            # mac
            cmap12_0_4 = cmap_format_12(12)
            cmap12_0_4.platformID = 0
            cmap12_0_4.platEncID = 4
            cmap12_0_4.language = 0
            cmap12_0_4.cmap = nonBMP
            # windows
            cmap12_3_10 = cmap_format_12(12)
            cmap12_3_10.platformID = 3
            cmap12_3_10.platEncID = 10
            cmap12_3_10.language = 0
            cmap12_3_10.cmap = nonBMP
            # update tables registry
            cmap.tables = [cmap4_0_3, cmap4_3_1, cmap12_0_4, cmap12_3_10]
        # unicode variation sequences
        uvsMapping = self.ufo.lib.get(UNICODE_VARIATION_SEQUENCES_KEY)
        if uvsMapping:
            from fontTools.ttLib.tables._c_m_a_p import cmap_format_14

            cmap14_0_5 = cmap_format_14(14)
            cmap14_0_5.platformID = 0
            cmap14_0_5.platEncID = 5
            cmap14_0_5.language = 0
            cmap14_0_5.cmap = {}
            if nonBMP:
                mapping = nonBMP
            uvsDict = dict()
            # public.unicodeVariationSequences uses hex strings as keys and
            # a dict of dicts, while cmap uses ints and a dict of tuples.
            for hexvs, glyphMapping in uvsMapping.items():
                uvsList = []
                for hexvalue, glyphName in glyphMapping.items():
                    value = int(hexvalue, 16)
                    if glyphName == mapping[value]:
                        uvsList.append((value, None))
                    else:
                        uvsList.append((value, glyphName))
                uvsDict[int(hexvs, 16)] = uvsList
            cmap14_0_5.uvsDict = uvsDict
            # update tables registry
            cmap.tables.append(cmap14_0_5)

    def setupTable_OS2(self):
        """
        Make the OS/2 table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "OS/2" not in self.tables:
            return

        self.otf["OS/2"] = os2 = newTable("OS/2")
        font = self.ufo
        os2.version = 0x0004
        # average glyph width
        os2.xAvgCharWidth = 0
        hmtx = self.otf.get("hmtx")
        if hmtx is not None:
            widths = [width for width, _ in hmtx.metrics.values() if width > 0]
            if widths:
                os2.xAvgCharWidth = otRound(sum(widths) / len(widths))
        # weight and width classes
        os2.usWeightClass = getAttrWithFallback(font.info, "openTypeOS2WeightClass")
        os2.usWidthClass = getAttrWithFallback(font.info, "openTypeOS2WidthClass")
        # embedding
        os2.fsType = intListToNum(
            getAttrWithFallback(font.info, "openTypeOS2Type"), 0, 16
        )

        # subscript, superscript, strikeout values, taken from AFDKO:
        # FDK/Tools/Programs/makeotf/makeotf_lib/source/hotconv/hot.c
        unitsPerEm = getAttrWithFallback(font.info, "unitsPerEm")
        italicAngle = float(getAttrWithFallback(font.info, "italicAngle"))
        xHeight = getAttrWithFallback(font.info, "xHeight")

        def adjustOffset(offset, angle):
            """Adjust Y offset based on italic angle, to get X offset."""
            return offset * math.tan(math.radians(-angle)) if angle else 0

        v = getAttrWithFallback(font.info, "openTypeOS2SubscriptXSize")
        if v is None:
            v = unitsPerEm * 0.65
        os2.ySubscriptXSize = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2SubscriptYSize")
        if v is None:
            v = unitsPerEm * 0.6
        os2.ySubscriptYSize = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2SubscriptYOffset")
        if v is None:
            v = unitsPerEm * 0.075
        os2.ySubscriptYOffset = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2SubscriptXOffset")
        if v is None:
            v = adjustOffset(-os2.ySubscriptYOffset, italicAngle)
        os2.ySubscriptXOffset = otRound(v)

        v = getAttrWithFallback(font.info, "openTypeOS2SuperscriptXSize")
        if v is None:
            v = os2.ySubscriptXSize
        os2.ySuperscriptXSize = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2SuperscriptYSize")
        if v is None:
            v = os2.ySubscriptYSize
        os2.ySuperscriptYSize = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2SuperscriptYOffset")
        if v is None:
            v = unitsPerEm * 0.35
        os2.ySuperscriptYOffset = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2SuperscriptXOffset")
        if v is None:
            v = adjustOffset(os2.ySuperscriptYOffset, italicAngle)
        os2.ySuperscriptXOffset = otRound(v)

        v = getAttrWithFallback(font.info, "openTypeOS2StrikeoutSize")
        if v is None:
            v = getAttrWithFallback(font.info, "postscriptUnderlineThickness")
        os2.yStrikeoutSize = otRound(v)
        v = getAttrWithFallback(font.info, "openTypeOS2StrikeoutPosition")
        if v is None:
            v = xHeight * 0.6 if xHeight else unitsPerEm * 0.22
        os2.yStrikeoutPosition = otRound(v)

        # family class
        ibmFontClass, ibmFontSubclass = getAttrWithFallback(
            font.info, "openTypeOS2FamilyClass"
        )
        os2.sFamilyClass = (ibmFontClass << 8) + ibmFontSubclass
        # panose
        data = getAttrWithFallback(font.info, "openTypeOS2Panose")
        panose = Panose()
        panose.bFamilyType = data[0]
        panose.bSerifStyle = data[1]
        panose.bWeight = data[2]
        panose.bProportion = data[3]
        panose.bContrast = data[4]
        panose.bStrokeVariation = data[5]
        panose.bArmStyle = data[6]
        panose.bLetterForm = data[7]
        panose.bMidline = data[8]
        panose.bXHeight = data[9]
        os2.panose = panose
        # Unicode ranges
        uniRanges = getAttrWithFallback(font.info, "openTypeOS2UnicodeRanges")
        if uniRanges is not None:
            os2.ulUnicodeRange1 = intListToNum(uniRanges, 0, 32)
            os2.ulUnicodeRange2 = intListToNum(uniRanges, 32, 32)
            os2.ulUnicodeRange3 = intListToNum(uniRanges, 64, 32)
            os2.ulUnicodeRange4 = intListToNum(uniRanges, 96, 32)
        else:
            os2.recalcUnicodeRanges(self.otf)

        # codepage ranges
        codepageRanges = getAttrWithFallback(font.info, "openTypeOS2CodePageRanges")
        if codepageRanges is None:
            unicodes = self.unicodeToGlyphNameMapping.keys()
            codepageRanges = calcCodePageRanges(unicodes)
        os2.ulCodePageRange1 = intListToNum(codepageRanges, 0, 32)
        os2.ulCodePageRange2 = intListToNum(codepageRanges, 32, 32)

        # vendor id
        os2.achVendID = getAttrWithFallback(font.info, "openTypeOS2VendorID")

        # vertical metrics
        os2.sxHeight = otRound(getAttrWithFallback(font.info, "xHeight"))
        os2.sCapHeight = otRound(getAttrWithFallback(font.info, "capHeight"))
        os2.sTypoAscender = otRound(
            getAttrWithFallback(font.info, "openTypeOS2TypoAscender")
        )
        os2.sTypoDescender = otRound(
            getAttrWithFallback(font.info, "openTypeOS2TypoDescender")
        )
        os2.sTypoLineGap = otRound(
            getAttrWithFallback(font.info, "openTypeOS2TypoLineGap")
        )
        os2.usWinAscent = otRound(
            getAttrWithFallback(font.info, "openTypeOS2WinAscent")
        )
        os2.usWinDescent = otRound(
            getAttrWithFallback(font.info, "openTypeOS2WinDescent")
        )
        # style mapping
        selection = list(getAttrWithFallback(font.info, "openTypeOS2Selection"))
        styleMapStyleName = getAttrWithFallback(font.info, "styleMapStyleName")
        if styleMapStyleName == "regular":
            selection.append(6)
        elif styleMapStyleName == "bold":
            selection.append(5)
        elif styleMapStyleName == "italic":
            selection.append(0)
        elif styleMapStyleName == "bold italic":
            selection += [0, 5]
        os2.fsSelection = intListToNum(selection, 0, 16)
        # characetr indexes
        unicodes = [i for i in self.unicodeToGlyphNameMapping.keys() if i is not None]
        if unicodes:
            minIndex = min(unicodes)
            maxIndex = max(unicodes)
        else:
            # the font may have *no* unicode values (it really happens!) so
            # there needs to be a fallback. use 0xFFFF, as AFDKO does:
            # FDK/Tools/Programs/makeotf/makeotf_lib/source/hotconv/map.c
            minIndex = 0xFFFF
            maxIndex = 0xFFFF
        if maxIndex > 0xFFFF:
            # the spec says that 0xFFFF should be used
            # as the max if the max exceeds 0xFFFF
            maxIndex = 0xFFFF
        os2.fsFirstCharIndex = minIndex
        os2.fsLastCharIndex = maxIndex
        os2.usBreakChar = 32
        os2.usDefaultChar = 0
        # maximum contextual lookup length
        os2.usMaxContex = 0

    def setupTable_hmtx(self):
        """
        Make the hmtx table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "hmtx" not in self.tables:
            return

        self.otf["hmtx"] = hmtx = newTable("hmtx")
        hmtx.metrics = {}
        for glyphName, glyph in self.allGlyphs.items():
            width = otRound(glyph.width)
            if width < 0:
                raise ValueError("The width should not be negative: '%s'" % (glyphName))
            bounds = self.glyphBoundingBoxes[glyphName]
            left = bounds.xMin if bounds else 0
            hmtx[glyphName] = (width, left)

    def _setupTable_hhea_or_vhea(self, tag):
        """
        Make the hhea table or the vhea table. This assume the hmtx or
        the vmtx were respectively made first.
        """
        if tag not in self.tables:
            return

        if tag == "hhea":
            isHhea = True
        else:
            isHhea = False
        self.otf[tag] = table = newTable(tag)
        mtxTable = self.otf.get(tag[0] + "mtx")
        font = self.ufo
        if isHhea:
            table.tableVersion = 0x00010000
        else:
            table.tableVersion = 0x00011000
        # Vertical metrics in hhea, horizontal metrics in vhea
        # and caret info.
        # The hhea metrics names are formed as:
        #   "openType" + tag.title() + "Ascender", etc.
        # While vhea metrics names are formed as:
        #   "openType" + tag.title() + "VertTypo" + "Ascender", etc.
        # Caret info names only differ by tag.title().
        commonPrefix = "openType%s" % tag.title()
        if isHhea:
            metricsPrefix = commonPrefix
        else:
            metricsPrefix = "openType%sVertTypo" % tag.title()
        metricsDict = {
            "ascent": "%sAscender" % metricsPrefix,
            "descent": "%sDescender" % metricsPrefix,
            "lineGap": "%sLineGap" % metricsPrefix,
            "caretSlopeRise": "%sCaretSlopeRise" % commonPrefix,
            "caretSlopeRun": "%sCaretSlopeRun" % commonPrefix,
            "caretOffset": "%sCaretOffset" % commonPrefix,
        }
        for otfName, ufoName in metricsDict.items():
            setattr(table, otfName, otRound(getAttrWithFallback(font.info, ufoName)))
        # Horizontal metrics in hhea, vertical metrics in vhea
        advances = []  # width in hhea, height in vhea
        firstSideBearings = []  # left in hhea, top in vhea
        secondSideBearings = []  # right in hhea, bottom in vhea
        extents = []
        if mtxTable is not None:
            for glyphName in self.allGlyphs:
                advance, firstSideBearing = mtxTable[glyphName]
                advances.append(advance)
                bounds = self.glyphBoundingBoxes[glyphName]
                if bounds is None:
                    continue
                if isHhea:
                    boundsAdvance = bounds.xMax - bounds.xMin
                    # equation from the hhea spec for calculating xMaxExtent:
                    #   Max(lsb + (xMax - xMin))
                    extent = firstSideBearing + boundsAdvance
                else:
                    boundsAdvance = bounds.yMax - bounds.yMin
                    # equation from the vhea spec for calculating yMaxExtent:
                    #   Max(tsb + (yMax - yMin)).
                    extent = firstSideBearing + boundsAdvance
                secondSideBearing = advance - firstSideBearing - boundsAdvance

                firstSideBearings.append(firstSideBearing)
                secondSideBearings.append(secondSideBearing)
                extents.append(extent)
        setattr(
            table,
            "advance%sMax" % ("Width" if isHhea else "Height"),
            max(advances) if advances else 0,
        )
        setattr(
            table,
            "min%sSideBearing" % ("Left" if isHhea else "Top"),
            min(firstSideBearings) if firstSideBearings else 0,
        )
        setattr(
            table,
            "min%sSideBearing" % ("Right" if isHhea else "Bottom"),
            min(secondSideBearings) if secondSideBearings else 0,
        )
        setattr(
            table,
            "%sMaxExtent" % ("x" if isHhea else "y"),
            max(extents) if extents else 0,
        )
        if isHhea:
            reserved = range(4)
        else:
            # vhea.reserved0 is caretOffset for legacy reasons
            reserved = range(1, 5)
        for i in reserved:
            setattr(table, "reserved%i" % i, 0)
        table.metricDataFormat = 0
        # glyph count
        setattr(
            table, "numberOf%sMetrics" % ("H" if isHhea else "V"), len(self.allGlyphs)
        )

    def setupTable_hhea(self):
        """
        Make the hhea table. This assumes that the hmtx table was made first.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        self._setupTable_hhea_or_vhea("hhea")

    def setupTable_vmtx(self):
        """
        Make the vmtx table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "vmtx" not in self.tables:
            return

        self.otf["vmtx"] = vmtx = newTable("vmtx")
        vmtx.metrics = {}
        for glyphName, glyph in self.allGlyphs.items():
            height = otRound(glyph.height)
            if height < 0:
                raise ValueError(
                    "The height should not be negative: '%s'" % (glyphName)
                )
            verticalOrigin = _getVerticalOrigin(self.otf, glyph)
            bounds = self.glyphBoundingBoxes[glyphName]
            top = bounds.yMax if bounds else 0
            vmtx[glyphName] = (height, verticalOrigin - top)

    def setupTable_VORG(self):
        """
        Make the VORG table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "VORG" not in self.tables:
            return

        self.otf["VORG"] = vorg = newTable("VORG")
        vorg.majorVersion = 1
        vorg.minorVersion = 0
        vorg.VOriginRecords = {}
        # Find the most frequent verticalOrigin
        vorg_count = Counter(
            _getVerticalOrigin(self.otf, glyph) for glyph in self.allGlyphs.values()
        )
        vorg.defaultVertOriginY = vorg_count.most_common(1)[0][0]
        if len(vorg_count) > 1:
            for glyphName, glyph in self.allGlyphs.items():
                vertOriginY = _getVerticalOrigin(self.otf, glyph)
                if vertOriginY == vorg.defaultVertOriginY:
                    continue
                vorg.VOriginRecords[glyphName] = vertOriginY
        vorg.numVertOriginYMetrics = len(vorg.VOriginRecords)

    def setupTable_vhea(self):
        """
        Make the vhea table. This assumes that the head and vmtx tables were
        made first.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        self._setupTable_hhea_or_vhea("vhea")

    def setupTable_post(self):
        """
        Make the post table.

        **This should not be called externally.** Subclasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "post" not in self.tables:
            return

        self.otf["post"] = post = newTable("post")
        font = self.ufo
        post.formatType = 3.0
        # italic angle
        italicAngle = float(getAttrWithFallback(font.info, "italicAngle"))
        post.italicAngle = italicAngle
        # underline
        underlinePosition = getAttrWithFallback(
            font.info, "postscriptUnderlinePosition"
        )
        post.underlinePosition = otRound(underlinePosition)
        underlineThickness = getAttrWithFallback(
            font.info, "postscriptUnderlineThickness"
        )
        post.underlineThickness = otRound(underlineThickness)
        post.isFixedPitch = int(
            getAttrWithFallback(font.info, "postscriptIsFixedPitch")
        )
        # misc
        post.minMemType42 = 0
        post.maxMemType42 = 0
        post.minMemType1 = 0
        post.maxMemType1 = 0

    def setupTable_COLR(self):
        """
        Compile the COLR table.

        **This should not be called externally.**
        """
        if "COLR" not in self.tables:
            return

        from fontTools.colorLib.builder import buildCOLR

        layerInfo = self.ufo.lib[COLOR_LAYERS_KEY]
        glyphMap = self.otf.getReverseGlyphMap()
        if layerInfo:
            # unpack (glyphs, clipBox) tuples to a flat dict keyed by glyph name,
            # as colorLib buildCOLR expects
            clipBoxes = {
                glyphName: tuple(box)
                for glyphs, box in self.ufo.lib.get(COLR_CLIP_BOXES_KEY, ())
                for glyphName in glyphs
            }
            self.otf["COLR"] = buildCOLR(
                layerInfo,
                glyphMap=glyphMap,
                clipBoxes=clipBoxes,
                allowLayerReuse=self.colrLayerReuse,
            )

    def setupTable_CPAL(self):
        """
        Compile the CPAL table.

        **This should not be called externally.**
        """
        if "CPAL" not in self.tables:
            return

        from fontTools.colorLib.builder import buildCPAL
        from fontTools.colorLib.errors import ColorLibError

        # colorLib wants colors as tuples, plistlib gives us lists
        palettes = [
            [tuple(color) for color in palette]
            for palette in self.ufo.lib[COLOR_PALETTES_KEY]
        ]
        try:
            self.otf["CPAL"] = buildCPAL(palettes)
        except ColorLibError as e:
            raise InvalidFontData("Failed to build CPAL table") from e

    def setupTable_meta(self):
        """
        Make the meta table.

        ***This should not be called externally.** Sublcasses
        may override or supplement this method to handle the
        table creation in a different way if desired.
        """
        if "meta" not in self.tables:
            return

        font = self.ufo
        self.otf["meta"] = meta = newTable("meta")
        ufo_meta = font.lib.get(OPENTYPE_META_KEY)
        for key, value in ufo_meta.items():
            if key in ["dlng", "slng"]:
                if not isinstance(value, list) or not all(
                    isinstance(string, str) for string in value
                ):
                    raise TypeError(
                        f"public.openTypeMeta '{key}' value should "
                        "be a list of strings"
                    )
                meta.data[key] = ",".join(value)
            elif key in ["appl", "bild"]:
                if not isinstance(value, bytes):
                    raise TypeError(
                        f"public.openTypeMeta '{key}' value should be bytes."
                    )
                meta.data[key] = value
            elif isinstance(value, bytes):
                meta.data[key] = value
            elif isinstance(value, str):
                meta.data[key] = value.encode("utf-8")
            else:
                raise TypeError(
                    f"public.openTypeMeta '{key}' value should be bytes or a string."
                )

    def setupOtherTables(self):
        """
        Make the other tables. The default implementation does nothing.

        **This should not be called externally.** Subclasses
        may override this method to add other tables to the
        font if desired.
        """
        pass

    def importTTX(self):
        """
        Merge TTX files from data directory "com.github.fonttools.ttx"

        **This should not be called externally.** Subclasses
        may override this method to handle the bounds creation
        in a different way if desired.
        """
        import os

        prefix = "com.github.fonttools.ttx"
        if not hasattr(self.ufo, "data"):
            return
        if not self.ufo.data.fileNames:
            return
        for path in self.ufo.data.fileNames:
            foldername, filename = os.path.split(path)
            if foldername == prefix and filename.endswith(".ttx"):
                ttx = self.ufo.data[path].decode("utf-8")
                fp = BytesIO(ttx.encode("utf-8"))
                # Preserve the original SFNT version when loading a TTX dump.
                sfntVersion = self.otf.sfntVersion
                try:
                    self.otf.importXML(fp)
                finally:
                    self.otf.sfntVersion = sfntVersion


class OutlineOTFCompiler(BaseOutlineCompiler):
    """Compile a .otf font with CFF outlines."""

    sfntVersion = "OTTO"
    tables = BaseOutlineCompiler.tables | {"CFF", "VORG"}

    def __init__(
        self,
        font,
        glyphSet=None,
        glyphOrder=None,
        tables=None,
        notdefGlyph=None,
        roundTolerance=None,
        optimizeCFF=True,
    ):
        if roundTolerance is not None:
            self.roundTolerance = float(roundTolerance)
        else:
            # round all coordinates to integers by default
            self.roundTolerance = 0.5
        super().__init__(
            font,
            glyphSet=glyphSet,
            glyphOrder=glyphOrder,
            tables=tables,
            notdefGlyph=notdefGlyph,
        )
        self.optimizeCFF = optimizeCFF
        self._defaultAndNominalWidths = None

    def getDefaultAndNominalWidths(self):
        """Return (defaultWidthX, nominalWidthX).

        If fontinfo.plist doesn't define these explicitly, compute optimal values
        from the glyphs' advance widths.
        """
        if self._defaultAndNominalWidths is None:
            info = self.ufo.info
            # populate the width values
            if all(
                getattr(info, attr, None) is None
                for attr in ("postscriptDefaultWidthX", "postscriptNominalWidthX")
            ):
                # no custom values set in fontinfo.plist; compute optimal ones
                from fontTools.cffLib.width import optimizeWidths

                widths = [otRound(glyph.width) for glyph in self.allGlyphs.values()]
                defaultWidthX, nominalWidthX = optimizeWidths(widths)
            else:
                defaultWidthX = otRound(
                    getAttrWithFallback(info, "postscriptDefaultWidthX")
                )
                nominalWidthX = otRound(
                    getAttrWithFallback(info, "postscriptNominalWidthX")
                )
            self._defaultAndNominalWidths = (defaultWidthX, nominalWidthX)
        return self._defaultAndNominalWidths

    def compileGlyphs(self):
        """Compile and return the CFF T2CharStrings for this font."""
        defaultWidth, nominalWidth = self.getDefaultAndNominalWidths()
        # The real PrivateDict will be created later on in setupTable_CFF.
        # For convenience here we use a namespace object to pass the default/nominal
        # widths that we need to draw the charstrings when computing their bounds.
        private = SimpleNamespace(
            defaultWidthX=defaultWidth, nominalWidthX=nominalWidth
        )
        compiledGlyphs = {}
        for glyphName in self.glyphOrder:
            glyph = self.allGlyphs[glyphName]
            cs = self.getCharStringForGlyph(glyph, private)
            compiledGlyphs[glyphName] = cs
        return compiledGlyphs

    def makeGlyphsBoundingBoxes(self):
        """
        Make bounding boxes for all the glyphs, and return a dictionary of
        BoundingBox(xMin, xMax, yMin, yMax) namedtuples keyed by glyph names.
        The bounding box of empty glyphs (without contours or components) is
        set to None.

        Check that the float values are within the range of the specified
        self.roundTolerance, and if so use the rounded value; else take the
        floor or ceiling to ensure that the bounding box encloses the original
        values.
        """

        def toInt(value, else_callback):
            rounded = otRound(value)
            if tolerance >= 0.5 or abs(rounded - value) <= tolerance:
                return rounded
            else:
                return int(else_callback(value))

        tolerance = self.roundTolerance
        glyphBoxes = {}
        charStrings = self.getCompiledGlyphs()
        for name, cs in charStrings.items():
            bounds = cs.calcBounds(charStrings)
            if bounds is not None:
                rounded = []
                for value in bounds[:2]:
                    rounded.append(toInt(value, math.floor))
                for value in bounds[2:]:
                    rounded.append(toInt(value, math.ceil))
                bounds = BoundingBox(*rounded)
            if bounds == EMPTY_BOUNDING_BOX:
                bounds = None
            glyphBoxes[name] = bounds
        return glyphBoxes

    def getCharStringForGlyph(self, glyph, private, globalSubrs=None):
        """
        Get a Type2CharString for the *glyph*

        **This should not be called externally.** Subclasses
        may override this method to handle the charstring creation
        in a different way if desired.
        """
        width = glyph.width
        defaultWidth = private.defaultWidthX
        nominalWidth = private.nominalWidthX
        if width == defaultWidth:
            # if width equals the default it can be omitted from charstring
            width = None
        else:
            # subtract the nominal width
            width -= nominalWidth
        if width is not None:
            width = otRound(width)
        pen = T2CharStringPen(width, self.allGlyphs, roundTolerance=self.roundTolerance)
        glyph.draw(pen)
        charString = pen.getCharString(private, globalSubrs, optimize=self.optimizeCFF)
        return charString

    def setupTable_maxp(self):
        """Make the maxp table."""
        if "maxp" not in self.tables:
            return

        self.otf["maxp"] = maxp = newTable("maxp")
        maxp.tableVersion = 0x00005000
        maxp.numGlyphs = len(self.glyphOrder)

    def setupOtherTables(self):
        self.setupTable_CFF()
        if self.vertical:
            self.setupTable_VORG()

    def setupTable_CFF(self):
        """Make the CFF table."""
        if not {"CFF", "CFF "}.intersection(self.tables):
            return

        self.otf["CFF "] = cff = newTable("CFF ")
        cff = cff.cff
        # NOTE: Set up a back-reference to be used by some CFFFontSet methods
        # down the line (as of fontTools 4.21.1).
        cff.otFont = self.otf
        # set up the basics
        cff.major = 1
        cff.minor = 0
        cff.hdrSize = 4
        cff.offSize = 4
        cff.fontNames = []
        strings = IndexedStrings()
        cff.strings = strings
        private = PrivateDict(strings=strings)
        private.rawDict.update(private.defaults)
        globalSubrs = GlobalSubrsIndex(private=private)
        topDict = TopDict(GlobalSubrs=globalSubrs, strings=strings)
        topDict.Private = private
        charStrings = topDict.CharStrings = CharStrings(
            file=None,
            charset=None,
            globalSubrs=globalSubrs,
            private=private,
            fdSelect=None,
            fdArray=None,
        )
        charStrings.charStringsAreIndexed = True
        topDict.charset = []
        charStringsIndex = charStrings.charStringsIndex = SubrsIndex(
            private=private, globalSubrs=globalSubrs
        )
        cff.topDictIndex = topDictIndex = TopDictIndex()
        topDictIndex.append(topDict)
        topDictIndex.strings = strings
        cff.GlobalSubrs = globalSubrs
        # populate naming data
        info = self.ufo.info
        psName = getAttrWithFallback(info, "postscriptFontName")
        cff.fontNames.append(psName)
        topDict = cff.topDictIndex[0]
        topDict.version = "%d.%d" % (
            getAttrWithFallback(info, "versionMajor"),
            getAttrWithFallback(info, "versionMinor"),
        )
        trademark = getAttrWithFallback(info, "trademark")
        if trademark:
            trademark = normalizeStringForPostscript(
                trademark.replace("\u00A9", "Copyright")
            )
        if trademark != self.ufo.info.trademark:
            logger.info(
                "The trademark was normalized for storage in the "
                "CFF table and consequently some characters were "
                "dropped: '%s'",
                trademark,
            )
        if trademark is None:
            trademark = ""
        topDict.Notice = trademark
        copyright = getAttrWithFallback(info, "copyright")
        if copyright:
            copyright = normalizeStringForPostscript(
                copyright.replace("\u00A9", "Copyright")
            )
        if copyright != self.ufo.info.copyright:
            logger.info(
                "The copyright was normalized for storage in the "
                "CFF table and consequently some characters were "
                "dropped: '%s'",
                copyright,
            )
        if copyright is None:
            copyright = ""
        topDict.Copyright = copyright
        topDict.FullName = getAttrWithFallback(info, "postscriptFullName")
        topDict.FamilyName = getAttrWithFallback(
            info, "openTypeNamePreferredFamilyName"
        )
        topDict.Weight = getAttrWithFallback(info, "postscriptWeightName")
        # populate various numbers
        topDict.isFixedPitch = int(getAttrWithFallback(info, "postscriptIsFixedPitch"))
        topDict.ItalicAngle = float(getAttrWithFallback(info, "italicAngle"))
        underlinePosition = getAttrWithFallback(info, "postscriptUnderlinePosition")
        topDict.UnderlinePosition = otRound(underlinePosition)
        underlineThickness = getAttrWithFallback(info, "postscriptUnderlineThickness")
        topDict.UnderlineThickness = otRound(underlineThickness)
        # populate font matrix
        unitsPerEm = otRound(getAttrWithFallback(info, "unitsPerEm"))
        topDict.FontMatrix = [1.0 / unitsPerEm, 0, 0, 1.0 / unitsPerEm, 0, 0]
        # populate the width values
        defaultWidthX, nominalWidthX = self.getDefaultAndNominalWidths()
        if defaultWidthX:
            private.rawDict["defaultWidthX"] = defaultWidthX
        if nominalWidthX:
            private.rawDict["nominalWidthX"] = nominalWidthX
        # populate hint data
        blueFuzz = otRound(getAttrWithFallback(info, "postscriptBlueFuzz"))
        blueShift = otRound(getAttrWithFallback(info, "postscriptBlueShift"))
        blueScale = getAttrWithFallback(info, "postscriptBlueScale")
        forceBold = getAttrWithFallback(info, "postscriptForceBold")
        blueValues = getAttrWithFallback(info, "postscriptBlueValues")
        if isinstance(blueValues, list):
            blueValues = [otRound(i) for i in blueValues]
        otherBlues = getAttrWithFallback(info, "postscriptOtherBlues")
        if isinstance(otherBlues, list):
            otherBlues = [otRound(i) for i in otherBlues]
        familyBlues = getAttrWithFallback(info, "postscriptFamilyBlues")
        if isinstance(familyBlues, list):
            familyBlues = [otRound(i) for i in familyBlues]
        familyOtherBlues = getAttrWithFallback(info, "postscriptFamilyOtherBlues")
        if isinstance(familyOtherBlues, list):
            familyOtherBlues = [otRound(i) for i in familyOtherBlues]
        stemSnapH = getAttrWithFallback(info, "postscriptStemSnapH")
        if isinstance(stemSnapH, list):
            stemSnapH = [otRound(i) for i in stemSnapH]
        stemSnapV = getAttrWithFallback(info, "postscriptStemSnapV")
        if isinstance(stemSnapV, list):
            stemSnapV = [otRound(i) for i in stemSnapV]
        # only write the blues data if some blues are defined.
        if any((blueValues, otherBlues, familyBlues, familyOtherBlues)):
            private.rawDict["BlueFuzz"] = blueFuzz
            private.rawDict["BlueShift"] = blueShift
            private.rawDict["BlueScale"] = blueScale
            private.rawDict["ForceBold"] = forceBold
            if blueValues:
                private.rawDict["BlueValues"] = blueValues
            if otherBlues:
                private.rawDict["OtherBlues"] = otherBlues
            if familyBlues:
                private.rawDict["FamilyBlues"] = familyBlues
            if familyOtherBlues:
                private.rawDict["FamilyOtherBlues"] = familyOtherBlues
        # only write the stems if both are defined.
        if stemSnapH and stemSnapV:
            private.rawDict["StemSnapH"] = stemSnapH
            private.rawDict["StdHW"] = stemSnapH[0]
            private.rawDict["StemSnapV"] = stemSnapV
            private.rawDict["StdVW"] = stemSnapV[0]
        # populate glyphs
        cffGlyphs = self.getCompiledGlyphs()
        for glyphName in self.glyphOrder:
            charString = cffGlyphs[glyphName]
            charString.private = private
            charString.globalSubrs = globalSubrs
            # add to the font
            if glyphName in charStrings:
                # XXX a glyph already has this name. should we choke?
                glyphID = charStrings.charStrings[glyphName]
                charStringsIndex.items[glyphID] = charString
            else:
                charStringsIndex.append(charString)
                glyphID = len(topDict.charset)
                charStrings.charStrings[glyphName] = glyphID
                topDict.charset.append(glyphName)
        topDict.FontBBox = self.fontBoundingBox


class OutlineTTFCompiler(BaseOutlineCompiler):
    """Compile a .ttf font with TrueType outlines."""

    sfntVersion = "\000\001\000\000"
    tables = BaseOutlineCompiler.tables | {"loca", "gasp", "glyf"}

    def compileGlyphs(self):
        """Compile and return the TrueType glyphs for this font."""
        allGlyphs = self.allGlyphs
        ttGlyphs = {}
        for name in self.glyphOrder:
            glyph = allGlyphs[name]
            pen = TTGlyphPointPen(allGlyphs)
            try:
                glyph.drawPoints(pen)
            except NotImplementedError:
                logger.error("%r has invalid curve format; skipped", name)
                ttGlyph = Glyph()
            else:
                ttGlyph = pen.glyph()
            ttGlyphs[name] = ttGlyph
        return ttGlyphs

    def makeGlyphsBoundingBoxes(self):
        """Make bounding boxes for all the glyphs.

        Return a dictionary of BoundingBox(xMin, xMax, yMin, yMax) namedtuples
        keyed by glyph names.
        The bounding box of empty glyphs (without contours or components) is
        set to None.
        """
        glyphBoxes = {}
        ttGlyphs = self.getCompiledGlyphs()
        for glyphName, glyph in ttGlyphs.items():
            glyph.recalcBounds(ttGlyphs)
            bounds = BoundingBox(glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
            if bounds == EMPTY_BOUNDING_BOX:
                bounds = None
            glyphBoxes[glyphName] = bounds
        return glyphBoxes

    def setupTable_maxp(self):
        """Make the maxp table."""
        if "maxp" not in self.tables:
            return

        self.otf["maxp"] = maxp = newTable("maxp")
        maxp.tableVersion = 0x00010000
        maxp.numGlyphs = len(self.glyphOrder)
        maxp.maxZones = 1
        maxp.maxTwilightPoints = 0
        maxp.maxStorage = 0
        maxp.maxFunctionDefs = 0
        maxp.maxInstructionDefs = 0
        maxp.maxStackElements = 0
        maxp.maxSizeOfInstructions = 0
        maxp.maxComponentElements = max(
            len(g.components) for g in self.allGlyphs.values()
        )

    def setupTable_post(self):
        """Make a format 2 post table with the compiler's glyph order."""
        super().setupTable_post()
        if "post" not in self.otf:
            return

        post = self.otf["post"]
        post.formatType = 2.0
        post.extraNames = []
        post.mapping = {}
        post.glyphOrder = self.glyphOrder

    def setupOtherTables(self):
        self.setupTable_glyf()
        if self.ufo.info.openTypeGaspRangeRecords:
            self.setupTable_gasp()

    def setupTable_glyf(self):
        """Make the glyf table."""
        if not {"glyf", "loca"}.issubset(self.tables):
            return

        self.otf["loca"] = newTable("loca")
        self.otf["glyf"] = glyf = newTable("glyf")
        glyf.glyphs = {}
        glyf.glyphOrder = self.glyphOrder

        hmtx = self.otf.get("hmtx")
        ttGlyphs = self.getCompiledGlyphs()
        for name in self.glyphOrder:
            ttGlyph = ttGlyphs[name]
            if ttGlyph.isComposite() and hmtx is not None and self.autoUseMyMetrics:
                self.autoUseMyMetrics(ttGlyph, name, hmtx)
            glyf[name] = ttGlyph

    @staticmethod
    def autoUseMyMetrics(ttGlyph, glyphName, hmtx):
        """Set the "USE_MY_METRICS" flag on the first component having the
        same advance width as the composite glyph, no transform and no
        horizontal shift (but allow it to shift vertically).
        This forces the composite glyph to use the possibly hinted horizontal
        metrics of the sub-glyph, instead of those from the "hmtx" table.
        """
        width = hmtx[glyphName][0]
        for component in ttGlyph.components:
            try:
                baseName, transform = component.getComponentInfo()
            except AttributeError:
                # component uses '{first,second}Pt' instead of 'x' and 'y'
                continue
            try:
                baseMetrics = hmtx[baseName]
            except KeyError:
                continue  # ignore missing components
            else:
                if baseMetrics[0] == width and transform[:-1] == (1, 0, 0, 1, 0):
                    component.flags |= USE_MY_METRICS
                    break


class StubGlyph:

    """
    This object will be used to create missing glyphs
    (specifically .notdef) in the provided UFO.
    """

    def __init__(
        self,
        name,
        width,
        unitsPerEm,
        ascender,
        descender,
        unicodes=None,
        reverseContour=False,
    ):
        self.name = name
        self.width = width
        self.unitsPerEm = unitsPerEm
        self.ascender = ascender
        self.descender = descender
        self.unicodes = unicodes if unicodes is not None else []
        self.components = []
        self.anchors = []
        if self.unicodes:
            self.unicode = self.unicodes[0]
        else:
            self.unicode = None
        if name == ".notdef":
            self.draw = self._drawDefaultNotdef
            self.drawPoints = self._drawDefaultNotdefPoints
        self.reverseContour = reverseContour

    def __len__(self):
        if self.name == ".notdef":
            return 1
        return 0

    @property
    def height(self):
        return self.ascender - self.descender

    def draw(self, pen):
        pass

    def drawPoints(self, pen):
        pass

    def _drawDefaultNotdef(self, pen):
        # Draw contour in PostScript direction (counter-clockwise) by default. Reverse
        # for TrueType.
        if self.reverseContour:
            pen = ReverseContourPen(pen)
        width = otRound(self.unitsPerEm * 0.5)
        stroke = otRound(self.unitsPerEm * 0.05)
        ascender = self.ascender
        descender = self.descender
        xMin = stroke
        xMax = width - stroke
        yMax = ascender
        yMin = descender
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMax, yMin))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMin, yMax))
        pen.lineTo((xMin, yMin))
        pen.closePath()
        xMin += stroke
        xMax -= stroke
        yMax -= stroke
        yMin += stroke
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMin, yMax))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMax, yMin))
        pen.lineTo((xMin, yMin))
        pen.closePath()

    def _drawDefaultNotdefPoints(self, pen):
        adapterPen = SegmentToPointPen(pen, guessSmooth=False)
        self.draw(adapterPen)

    def _get_controlPointBounds(self):
        pen = ControlBoundsPen(None)
        self.draw(pen)
        return pen.bounds

    controlPointBounds = property(_get_controlPointBounds)
