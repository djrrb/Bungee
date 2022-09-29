"""
This file provides fallback data for info attributes
that are required for building OTFs. There are two main
functions that are important:

* :func:`~getAttrWithFallback`
* :func:`~preflightInfo`

There are a set of other functions that are used internally
for synthesizing values for specific attributes. These can be
used externally as well.
"""


import calendar
import logging
import math
import os
import time
import unicodedata
from datetime import datetime

from fontTools import ufoLib
from fontTools.misc.fixedTools import otRound
from fontTools.misc.textTools import binary2num

logger = logging.getLogger(__name__)


# -----------------
# Special Fallbacks
# -----------------

# generic
_styleMapStyleNames = ["regular", "bold", "italic", "bold italic"]


def ascenderFallback(info):
    upm = getAttrWithFallback(info, "unitsPerEm")
    return otRound(upm * 0.8)


def descenderFallback(info):
    upm = getAttrWithFallback(info, "unitsPerEm")
    return -otRound(upm * 0.2)


def capHeightFallback(info):
    upm = getAttrWithFallback(info, "unitsPerEm")
    return otRound(upm * 0.7)


def xHeightFallback(info):
    upm = getAttrWithFallback(info, "unitsPerEm")
    return otRound(upm * 0.5)


def styleMapFamilyNameFallback(info):
    """
    Fallback to *openTypeNamePreferredFamilyName* if
    *styleMapStyleName* or, if *styleMapStyleName* isn't defined,
    *openTypeNamePreferredSubfamilyName* is
    *regular*, *bold*, *italic* or *bold italic*, otherwise
    fallback to *openTypeNamePreferredFamilyName openTypeNamePreferredFamilyName*.
    """
    familyName = getAttrWithFallback(info, "openTypeNamePreferredFamilyName")
    styleName = info.styleMapStyleName
    if not styleName:
        styleName = getAttrWithFallback(info, "openTypeNamePreferredSubfamilyName")
    if styleName is None:
        styleName = ""
    elif styleName.lower() in _styleMapStyleNames:
        styleName = ""
    return (familyName + " " + styleName).strip()


def styleMapStyleNameFallback(info):
    """
    Fallback to *openTypeNamePreferredSubfamilyName* if
    it is one of *regular*, *bold*, *italic*, *bold italic*, otherwise
    fallback to *regular*.
    """
    styleName = getAttrWithFallback(info, "openTypeNamePreferredSubfamilyName")
    if styleName is None:
        styleName = "regular"
    elif styleName.strip().lower() not in _styleMapStyleNames:
        styleName = "regular"
    else:
        styleName = styleName.strip().lower()
    return styleName


# head

_date_format = "%Y/%m/%d %H:%M:%S"


def dateStringForNow():
    return time.strftime(_date_format, time.gmtime())


def openTypeHeadCreatedFallback(info):
    """
    Fallback to the environment variable SOURCE_DATE_EPOCH if set, otherwise
    now.
    """
    if "SOURCE_DATE_EPOCH" in os.environ:
        t = datetime.utcfromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]))
        return t.strftime(_date_format)
    else:
        return dateStringForNow()


# hhea


def openTypeHheaAscenderFallback(info):
    """
    Fallback to *ascender + typoLineGap*.
    """
    return getAttrWithFallback(info, "ascender") + getAttrWithFallback(
        info, "openTypeOS2TypoLineGap"
    )


def openTypeHheaDescenderFallback(info):
    """
    Fallback to *descender*.
    """
    return getAttrWithFallback(info, "descender")


def openTypeHheaCaretSlopeRiseFallback(info):
    """
    Fallback to *openTypeHheaCaretSlopeRise*. If the italicAngle is zero,
    return 1. If italicAngle is non-zero, compute the slope rise from the
    complementary openTypeHheaCaretSlopeRun, if the latter is defined.
    Else, default to an arbitrary fixed reference point (1000).
    """
    italicAngle = getAttrWithFallback(info, "italicAngle")
    if italicAngle != 0:
        if (
            hasattr(info, "openTypeHheaCaretSlopeRun")
            and info.openTypeHheaCaretSlopeRun is not None
        ):
            slopeRun = info.openTypeHheaCaretSlopeRun
            return otRound(slopeRun / math.tan(math.radians(-italicAngle)))
        else:
            return 1000  # just an arbitrary non-zero reference point
    return 1


def openTypeHheaCaretSlopeRunFallback(info):
    """
    Fallback to *openTypeHheaCaretSlopeRun*. If the italicAngle is zero,
    return 0. If italicAngle is non-zero, compute the slope run from the
    complementary openTypeHheaCaretSlopeRise.
    """
    italicAngle = getAttrWithFallback(info, "italicAngle")
    if italicAngle != 0:
        slopeRise = getAttrWithFallback(info, "openTypeHheaCaretSlopeRise")
        return otRound(math.tan(math.radians(-italicAngle)) * slopeRise)
    return 0


# name


def openTypeNameVersionFallback(info):
    """
    Fallback to *versionMajor.versionMinor* in the form 0.000.
    """
    versionMajor = getAttrWithFallback(info, "versionMajor")
    versionMinor = getAttrWithFallback(info, "versionMinor")
    return "Version %d.%s" % (versionMajor, str(versionMinor).zfill(3))


def openTypeNameUniqueIDFallback(info):
    """
    Fallback to *openTypeNameVersion;openTypeOS2VendorID;postscriptFontName*.
    """
    version = getAttrWithFallback(info, "openTypeNameVersion").replace("Version ", "")
    vendor = getAttrWithFallback(info, "openTypeOS2VendorID")
    fontName = getAttrWithFallback(info, "postscriptFontName")
    return f"{version};{vendor};{fontName}"


def openTypeNamePreferredFamilyNameFallback(info):
    """
    Fallback to *familyName*.
    """
    return getAttrWithFallback(info, "familyName")


def openTypeNamePreferredSubfamilyNameFallback(info):
    """
    Fallback to *styleName*.
    """
    return getAttrWithFallback(info, "styleName")


def openTypeNameWWSFamilyNameFallback(info):
    # not yet supported
    return None


def openTypeNameWWSSubfamilyNameFallback(info):
    # not yet supported
    return None


# OS/2


def openTypeOS2TypoAscenderFallback(info):
    """
    Fallback to *ascender*.
    """
    return getAttrWithFallback(info, "ascender")


def openTypeOS2TypoDescenderFallback(info):
    """
    Fallback to *descender*.
    """
    return getAttrWithFallback(info, "descender")


def openTypeOS2TypoLineGapFallback(info):
    """
    Fallback to *UPM * 1.2 - ascender + descender*, or zero if that's negative.
    """
    return max(
        int(getAttrWithFallback(info, "unitsPerEm") * 1.2)
        - getAttrWithFallback(info, "ascender")
        + getAttrWithFallback(info, "descender"),
        0,
    )


def openTypeOS2WinAscentFallback(info):
    """
    Fallback to *ascender + typoLineGap*.
    """
    return getAttrWithFallback(info, "ascender") + getAttrWithFallback(
        info, "openTypeOS2TypoLineGap"
    )


def openTypeOS2WinDescentFallback(info):
    """
    Fallback to *descender*.
    """
    return abs(getAttrWithFallback(info, "descender"))


# postscript

_postscriptFontNameExceptions = set("[](){}<>/%")
_postscriptFontNameAllowed = {chr(i) for i in range(33, 127)}


def normalizeStringForPostscript(s, allowSpaces=True):
    normalized = []
    for c in s:
        if c == " " and not allowSpaces:
            continue
        if c in _postscriptFontNameExceptions:
            continue
        if c not in _postscriptFontNameAllowed:
            # Use compatibility decomposed form, to keep parts in ascii
            c = unicodedata.normalize("NFKD", c)
            if not set(c) < _postscriptFontNameAllowed:
                c = c.encode("ascii", errors="replace").decode()
        normalized.append(c)
    return "".join(normalized)


def normalizeNameForPostscript(name):
    return normalizeStringForPostscript(name, allowSpaces=False)


def postscriptFontNameFallback(info):
    """
    Fallback to a string containing only valid characters
    as defined in the specification. This will draw from
    *openTypeNamePreferredFamilyName* and *openTypeNamePreferredSubfamilyName*.
    """
    name = "{}-{}".format(
        getAttrWithFallback(info, "openTypeNamePreferredFamilyName"),
        getAttrWithFallback(info, "openTypeNamePreferredSubfamilyName"),
    )
    return normalizeNameForPostscript(name)


def postscriptFullNameFallback(info):
    """
    Fallback to *openTypeNamePreferredFamilyName openTypeNamePreferredSubfamilyName*.
    """
    return "{} {}".format(
        getAttrWithFallback(info, "openTypeNamePreferredFamilyName"),
        getAttrWithFallback(info, "openTypeNamePreferredSubfamilyName"),
    )


def postscriptSlantAngleFallback(info):
    """
    Fallback to *italicAngle*.
    """
    return getAttrWithFallback(info, "italicAngle")


def postscriptUnderlineThicknessFallback(info):
    """Return UPM * 0.05 (50 for 1000 UPM) and warn."""
    logger.debug("Underline thickness not set in UFO, defaulting to UPM * 0.05")
    return getAttrWithFallback(info, "unitsPerEm") * 0.05


def postscriptUnderlinePositionFallback(info):
    """Return UPM * -0.075 (-75 for 1000 UPM) and warn."""
    logger.debug("Underline position not set in UFO, defaulting to UPM * -0.075")
    return getAttrWithFallback(info, "unitsPerEm") * -0.075


def postscriptBlueScaleFallback(info):
    """
    Fallback to a calculated value: 3/(4 * *maxZoneHeight*)
    where *maxZoneHeight* is the tallest zone from *postscriptBlueValues*
    and *postscriptOtherBlues*. If zones are not set, return 0.039625.
    """
    blues = getAttrWithFallback(info, "postscriptBlueValues")
    otherBlues = getAttrWithFallback(info, "postscriptOtherBlues")
    maxZoneHeight = 0
    blueScale = 0.039625
    if blues:
        assert len(blues) % 2 == 0
        for x, y in zip(blues[:-1:2], blues[1::2]):
            maxZoneHeight = max(maxZoneHeight, abs(y - x))
    if otherBlues:
        assert len(otherBlues) % 2 == 0
        for x, y in zip(otherBlues[:-1:2], otherBlues[1::2]):
            maxZoneHeight = max(maxZoneHeight, abs(y - x))
    if maxZoneHeight != 0:
        blueScale = 3 / (4 * maxZoneHeight)
    return blueScale


# --------------
# Attribute Maps
# --------------

staticFallbackData = dict(
    versionMajor=0,
    versionMinor=0,
    copyright=None,
    trademark=None,
    familyName="New Font",
    styleName="Regular",
    unitsPerEm=1000,
    italicAngle=0,
    # not needed
    year=None,
    note=None,
    openTypeHeadLowestRecPPEM=6,
    openTypeHeadFlags=[0, 1],
    openTypeHheaLineGap=0,
    openTypeHheaCaretOffset=0,
    openTypeNameDesigner=None,
    openTypeNameDesignerURL=None,
    openTypeNameManufacturer=None,
    openTypeNameManufacturerURL=None,
    openTypeNameLicense=None,
    openTypeNameLicenseURL=None,
    openTypeNameDescription=None,
    openTypeNameCompatibleFullName=None,
    openTypeNameSampleText=None,
    openTypeNameRecords=[],
    openTypeOS2WidthClass=5,
    openTypeOS2WeightClass=400,
    openTypeOS2Selection=[],
    openTypeOS2VendorID="NONE",
    openTypeOS2Panose=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    openTypeOS2FamilyClass=[0, 0],
    openTypeOS2UnicodeRanges=None,
    openTypeOS2CodePageRanges=None,
    openTypeOS2Type=[2],
    openTypeOS2SubscriptXSize=None,
    openTypeOS2SubscriptYSize=None,
    openTypeOS2SubscriptXOffset=None,
    openTypeOS2SubscriptYOffset=None,
    openTypeOS2SuperscriptXSize=None,
    openTypeOS2SuperscriptYSize=None,
    openTypeOS2SuperscriptXOffset=None,
    openTypeOS2SuperscriptYOffset=None,
    openTypeOS2StrikeoutSize=None,
    openTypeOS2StrikeoutPosition=None,
    # fallback to None on these
    # as the user should be in
    # complete control
    openTypeVheaVertTypoAscender=None,
    openTypeVheaVertTypoDescender=None,
    openTypeVheaVertTypoLineGap=None,
    # fallback to horizontal caret:
    # a value of 0 for the rise
    # and a value of 1 for the run.
    openTypeVheaCaretSlopeRise=0,
    openTypeVheaCaretSlopeRun=1,
    openTypeVheaCaretOffset=0,
    postscriptUniqueID=None,
    postscriptWeightName=None,
    postscriptIsFixedPitch=False,
    postscriptBlueValues=[],
    postscriptOtherBlues=[],
    postscriptFamilyBlues=[],
    postscriptFamilyOtherBlues=[],
    postscriptStemSnapH=[],
    postscriptStemSnapV=[],
    postscriptBlueFuzz=0,
    postscriptBlueShift=7,
    postscriptForceBold=0,
    postscriptDefaultWidthX=200,
    postscriptNominalWidthX=0,
    # not used in OTF
    postscriptDefaultCharacter=None,
    postscriptWindowsCharacterSet=None,
    # not used in OTF
    macintoshFONDFamilyID=None,
    macintoshFONDName=None,
)

specialFallbacks = dict(
    ascender=ascenderFallback,
    descender=descenderFallback,
    capHeight=capHeightFallback,
    xHeight=xHeightFallback,
    styleMapFamilyName=styleMapFamilyNameFallback,
    styleMapStyleName=styleMapStyleNameFallback,
    openTypeHeadCreated=openTypeHeadCreatedFallback,
    openTypeHheaAscender=openTypeHheaAscenderFallback,
    openTypeHheaDescender=openTypeHheaDescenderFallback,
    openTypeHheaCaretSlopeRise=openTypeHheaCaretSlopeRiseFallback,
    openTypeHheaCaretSlopeRun=openTypeHheaCaretSlopeRunFallback,
    openTypeNameVersion=openTypeNameVersionFallback,
    openTypeNameUniqueID=openTypeNameUniqueIDFallback,
    openTypeNamePreferredFamilyName=openTypeNamePreferredFamilyNameFallback,
    openTypeNamePreferredSubfamilyName=openTypeNamePreferredSubfamilyNameFallback,
    openTypeNameWWSFamilyName=openTypeNameWWSFamilyNameFallback,
    openTypeNameWWSSubfamilyName=openTypeNameWWSSubfamilyNameFallback,
    openTypeOS2TypoAscender=openTypeOS2TypoAscenderFallback,
    openTypeOS2TypoDescender=openTypeOS2TypoDescenderFallback,
    openTypeOS2TypoLineGap=openTypeOS2TypoLineGapFallback,
    openTypeOS2WinAscent=openTypeOS2WinAscentFallback,
    openTypeOS2WinDescent=openTypeOS2WinDescentFallback,
    postscriptFontName=postscriptFontNameFallback,
    postscriptFullName=postscriptFullNameFallback,
    postscriptSlantAngle=postscriptSlantAngleFallback,
    postscriptUnderlineThickness=postscriptUnderlineThicknessFallback,
    postscriptUnderlinePosition=postscriptUnderlinePositionFallback,
    postscriptBlueScale=postscriptBlueScaleFallback,
)

requiredAttributes = set(ufoLib.fontInfoAttributesVersion2) - (
    set(staticFallbackData.keys()) | set(specialFallbacks.keys())
)

recommendedAttributes = {
    "styleMapFamilyName",
    "versionMajor",
    "versionMinor",
    "copyright",
    "trademark",
    "openTypeHeadCreated",
    "openTypeNameDesigner",
    "openTypeNameDesignerURL",
    "openTypeNameManufacturer",
    "openTypeNameManufacturerURL",
    "openTypeNameLicense",
    "openTypeNameLicenseURL",
    "openTypeNameDescription",
    "openTypeNameSampleText",
    "openTypeOS2WidthClass",
    "openTypeOS2WeightClass",
    "openTypeOS2VendorID",
    "openTypeOS2Panose",
    "openTypeOS2FamilyClass",
    "openTypeOS2UnicodeRanges",
    "openTypeOS2CodePageRanges",
    "openTypeOS2TypoLineGap",
    "openTypeOS2Type",
    "postscriptBlueValues",
    "postscriptOtherBlues",
    "postscriptFamilyBlues",
    "postscriptFamilyOtherBlues",
    "postscriptStemSnapH",
    "postscriptStemSnapV",
}

# ------------
# Main Methods
# ------------


def getAttrWithFallback(info, attr):
    """
    Get the value for *attr* from the *info* object.
    If the object does not have the attribute or the value
    for the atribute is None, this will either get a
    value from a predefined set of attributes or it
    will synthesize a value from the available data.
    """
    if hasattr(info, attr) and getattr(info, attr) is not None:
        value = getattr(info, attr)
    else:
        if attr in specialFallbacks:
            value = specialFallbacks[attr](info)
        else:
            value = staticFallbackData[attr]
    return value


def preflightInfo(info):
    """
    Returns a dict containing two items. The value for each
    item will be a list of info attribute names.

    ==================  ===
    missingRequired     Required data that is missing.
    missingRecommended  Recommended data that is missing.
    ==================  ===
    """
    missingRequired = set()
    missingRecommended = set()
    for attr in requiredAttributes:
        if not hasattr(info, attr) or getattr(info, attr) is None:
            missingRequired.add(attr)
    for attr in recommendedAttributes:
        if not hasattr(info, attr) or getattr(info, attr) is None:
            missingRecommended.add(attr)
    return dict(missingRequired=missingRequired, missingRecommended=missingRecommended)


# -----------------
# Low Level Support
# -----------------

# these should not be used outside of this package


def intListToNum(intList, start, length):
    all = []
    bin = ""
    for i in range(start, start + length):
        if i in intList:
            b = "1"
        else:
            b = "0"
        bin = b + bin
        if not (i + 1) % 8:
            all.append(bin)
            bin = ""
    if bin:
        all.append(bin)
    all.reverse()
    all = " ".join(all)
    return binary2num(all)


def dateStringToTimeValue(date):
    try:
        t = time.strptime(date, "%Y/%m/%d %H:%M:%S")
        return calendar.timegm(t)
    except ValueError:
        return 0
