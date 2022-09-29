from __future__ import division, absolute_import
from fontMath.mathFunctions import (
    add, addPt, div, factorAngle, mul, _roundNumber, sub, subPt, round2)
from fontMath.mathGuideline import (
    _expandGuideline, _pairGuidelines, _processMathOneGuidelines,
    _processMathTwoGuidelines, _roundGuidelines)


class MathInfo(object):

    def __init__(self, infoObject):
        for attr in _infoAttrs.keys():
            if hasattr(infoObject, attr):
                setattr(self, attr, getattr(infoObject, attr))
        if isinstance(infoObject, MathInfo):
            self.guidelines = [dict(guideline) for guideline in infoObject.guidelines]
        elif infoObject.guidelines is not None:
            self.guidelines = [_expandGuideline(guideline) for guideline in infoObject.guidelines]
        else:
            self.guidelines = []

    # ----
    # Copy
    # ----

    def copy(self):
        copied = MathInfo(self)
        return copied

    # ----
    # Math
    # ----

    # math with other info

    def __add__(self, otherInfo):
        copiedInfo = self.copy()
        self._processMathOne(copiedInfo, otherInfo, addPt, add)
        return copiedInfo

    def __sub__(self, otherInfo):
        copiedInfo = self.copy()
        self._processMathOne(copiedInfo, otherInfo, subPt, sub)
        return copiedInfo

    def _processMathOne(self, copiedInfo, otherInfo, ptFunc, func):
        # basic attributes
        for attr in _infoAttrs.keys():
            a = None
            b = None
            v = None
            if hasattr(copiedInfo, attr):
                a = getattr(copiedInfo, attr)
            if hasattr(otherInfo, attr):
                b = getattr(otherInfo, attr)
            if a is not None and b is not None:
                if isinstance(a, (list, tuple)):
                    v = self._processMathOneNumberList(a, b, func)
                else:
                    v = self._processMathOneNumber(a, b, func)
            # when one of the terms is undefined, we treat addition and subtraction
            # differently...
            # https://github.com/robotools/fontMath/issues/175
            # https://github.com/robotools/fontMath/issues/136
            elif a is not None and b is None:
                if func == add:
                    v = a
                else:
                    v = None if attr in _numberListAttrs else 0
            elif b is not None and a is None:
                if func is add:
                    v = b
                else:
                    v = None if attr in _numberListAttrs else 0
            setattr(copiedInfo, attr, v)
        # special attributes
        self._processPostscriptWeightName(copiedInfo)
        # guidelines
        copiedInfo.guidelines = []
        if self.guidelines:
            guidelinePairs = _pairGuidelines(self.guidelines, otherInfo.guidelines)
            copiedInfo.guidelines = _processMathOneGuidelines(guidelinePairs, ptFunc, func)

    def _processMathOneNumber(self, a, b, func):
        return func(a, b)

    def _processMathOneNumberList(self, a, b, func):
        if len(a) != len(b):
            return None
        v = []
        for index, aItem in enumerate(a):
            bItem = b[index]
            v.append(func(aItem, bItem))
        return v

    # math with factor

    def __mul__(self, factor):
        if not isinstance(factor, tuple):
            factor = (factor, factor)
        copiedInfo = self.copy()
        self._processMathTwo(copiedInfo, factor, mul)
        return copiedInfo

    __rmul__ = __mul__

    def __div__(self, factor):
        if not isinstance(factor, tuple):
            factor = (factor, factor)
        copiedInfo = self.copy()
        self._processMathTwo(copiedInfo, factor, div)
        return copiedInfo

    __truediv__ = __div__

    __rdiv__ = __div__

    __rtruediv__ = __rdiv__

    def _processMathTwo(self, copiedInfo, factor, func):
        # basic attributes
        for attr, (formatter, factorIndex) in _infoAttrs.items():
            if hasattr(copiedInfo, attr):
                v = getattr(copiedInfo, attr)
                if v is not None and factor is not None:
                    if factorIndex == 3:
                        v = self._processMathTwoAngle(v, factor, func)
                    else:
                        if isinstance(v, (list, tuple)):
                            v = self._processMathTwoNumberList(v, factor[factorIndex], func)
                        else:
                            v = self._processMathTwoNumber(v, factor[factorIndex], func)
                else:
                    v = None
                setattr(copiedInfo, attr, v)
        # special attributes
        self._processPostscriptWeightName(copiedInfo)
        # guidelines
        copiedInfo.guidelines = []
        if self.guidelines:
            copiedInfo.guidelines = _processMathTwoGuidelines(self.guidelines, factor, func)

    def _processMathTwoNumber(self, v, factor, func):
        return func(v, factor)

    def _processMathTwoNumberList(self, v, factor, func):
        return [func(i, factor) for i in v]

    def _processMathTwoAngle(self, angle, factor, func):
        return factorAngle(angle, factor, func)

    # special attributes

    def _processPostscriptWeightName(self, copiedInfo):
        # handle postscriptWeightName by taking the value
        # of openTypeOS2WeightClass and getting the closest
        # value from the OS/2 specification.
        name = None
        if hasattr(copiedInfo, "openTypeOS2WeightClass") and copiedInfo.openTypeOS2WeightClass is not None:
            v = copiedInfo.openTypeOS2WeightClass
            # here we use Python 2 rounding (i.e. away from 0) instead of Python 3:
            # e.g. 150 -> 200 and 250 -> 300, instead of 150 -> 200 and 250 -> 200
            v = int(round2(v, -2))
            if v < 100:
                v = 100
            elif v > 900:
                v = 900
            name = _postscriptWeightNameOptions[v]
        copiedInfo.postscriptWeightName = name

    # ----------
    # More math
    # ----------

    def round(self, digits=None):
        excludeFromRounding = ['postscriptBlueScale', 'italicAngle']
        copiedInfo = self.copy()
        # basic attributes
        for attr, (formatter, factorIndex) in _infoAttrs.items():
            if attr in excludeFromRounding:
                continue
            if hasattr(copiedInfo, attr):
                v = getattr(copiedInfo, attr)
                if v is not None:
                    if factorIndex == 3:
                        v = _roundNumber(v)
                    else:
                        if isinstance(v, (list, tuple)):
                            v = [_roundNumber(a, digits) for a in v]
                        else:
                            v = _roundNumber(v, digits)
                else:
                    v = None
                setattr(copiedInfo, attr, v)
        # special attributes
        self._processPostscriptWeightName(copiedInfo)
        # guidelines
        copiedInfo.guidelines = []
        if self.guidelines:
            copiedInfo.guidelines = _roundGuidelines(self.guidelines, digits)
        return copiedInfo

    # ----------
    # Extraction
    # ----------

    def extractInfo(self, otherInfoObject):
        """
        >>> from fontMath.test.test_mathInfo import _TestInfoObject, _testData
        >>> from fontMath.mathFunctions import _roundNumber
        >>> info1 = MathInfo(_TestInfoObject())
        >>> info2 = info1 * 2.5
        >>> info3 = _TestInfoObject()
        >>> info2.extractInfo(info3)
        >>> written = {}
        >>> expected = {}
        >>> for attr, value in _testData.items():
        ...     if value is None:
        ...         continue
        ...     written[attr] = getattr(info2, attr)
        ...     if isinstance(value, list):
        ...         expectedValue = [_roundNumber(v * 2.5) for v in value]
        ...     elif isinstance(value, int):
        ...         expectedValue = _roundNumber(value * 2.5)
        ...     else:
        ...         expectedValue = value * 2.5
        ...     expected[attr] = expectedValue
        >>> sorted(expected) == sorted(written)
        True
        """
        for attr, (formatter, factorIndex) in _infoAttrs.items():
            if hasattr(self, attr):
                v = getattr(self, attr)
                if v is not None:
                    if formatter is not None:
                        v = formatter(v)
                setattr(otherInfoObject, attr, v)
        if hasattr(self, "postscriptWeightName"):
            otherInfoObject.postscriptWeightName = self.postscriptWeightName

    # -------
    # Sorting
    # -------

    def __lt__(self, other):
        if set(self.__dict__.keys()) < set(other.__dict__.keys()):
            return True
        elif set(self.__dict__.keys()) > set(other.__dict__.keys()):
            return False
        for attr, value in self.__dict__.items():
            other_value = getattr(other, attr)
            if value is not None and other_value is not None:
                # guidelines is a list of dicts
                if attr == "guidelines":
                    if len(value) < len(other_value):
                        return True
                    elif len(value) > len(other_value):
                        return False
                    for i, guide in enumerate(value):
                        if set(guide) < set(other_value[i]):
                            return True
                        elif set(guide) > set(other_value[i]):
                            return False
                        for key, val in guide.items():
                            if key in other_value[i]:
                                if val < other_value[i][key]:
                                    return True
                elif value < other_value:
                    return True
        return False

    def __eq__(self, other):
        if set(self.__dict__.keys()) != set(other.__dict__.keys()):
            return False
        for attr, value in self.__dict__.items():
            if hasattr(other, attr) and value != getattr(other, attr):
                return False
        return True


# ----------
# Formatters
# ----------

def _numberFormatter(value):
    v = int(value)
    if v == value:
        return v
    return value

def _integerFormatter(value):
    return _roundNumber(value)

def _floatFormatter(value):
    return float(value)

def _nonNegativeNumberFormatter(value):
    """
    >>> _nonNegativeNumberFormatter(-10)
    0
    """
    if value < 0:
        return 0
    return value

def _nonNegativeIntegerFormatter(value):
    value = _integerFormatter(value)
    if value < 0:
        return 0
    return value

def _integerListFormatter(value):
    """
    >>> _integerListFormatter([.9, 40.3, 16.0001])
    [1, 40, 16]
    """
    return [_integerFormatter(v) for v in value]

def _numberListFormatter(value):
    return [_numberFormatter(v) for v in value]

def _openTypeOS2WidthClassFormatter(value):
    """
    >>> _openTypeOS2WidthClassFormatter(-2)
    1
    >>> _openTypeOS2WidthClassFormatter(0)
    1
    >>> _openTypeOS2WidthClassFormatter(5.4)
    5
    >>> _openTypeOS2WidthClassFormatter(9.6)
    9
    >>> _openTypeOS2WidthClassFormatter(12)
    9
    """
    value = int(round2(value))
    if value > 9:
        value = 9
    elif value < 1:
        value = 1
    return value

def _openTypeOS2WeightClassFormatter(value):
    """
    >>> _openTypeOS2WeightClassFormatter(-20)
    0
    >>> _openTypeOS2WeightClassFormatter(0)
    0
    >>> _openTypeOS2WeightClassFormatter(50.4)
    50
    >>> _openTypeOS2WeightClassFormatter(90.6)
    91
    >>> _openTypeOS2WeightClassFormatter(120)
    120
    """
    value = _roundNumber(value)
    if value < 0:
        value = 0
    return value

_infoAttrs = dict(
    # these are structured as:
    #   attribute name = (formatter function, factor direction)
    # where factor direction 0 = x, 1 = y and 3 = x, y (for angles)

    unitsPerEm=(_nonNegativeNumberFormatter, 1),
    descender=(_numberFormatter, 1),
    xHeight=(_numberFormatter, 1),
    capHeight=(_numberFormatter, 1),
    ascender=(_numberFormatter, 1),
    italicAngle=(_numberFormatter, 3),

    openTypeHeadLowestRecPPEM=(_nonNegativeIntegerFormatter, 1),

    openTypeHheaAscender=(_integerFormatter, 1),
    openTypeHheaDescender=(_integerFormatter, 1),
    openTypeHheaLineGap=(_integerFormatter, 1),
    openTypeHheaCaretSlopeRise=(_integerFormatter, 1),
    openTypeHheaCaretSlopeRun=(_integerFormatter, 1),
    openTypeHheaCaretOffset=(_integerFormatter, 1),

    openTypeOS2WidthClass=(_openTypeOS2WidthClassFormatter, 0),
    openTypeOS2WeightClass=(_openTypeOS2WeightClassFormatter, 0),
    openTypeOS2TypoAscender=(_integerFormatter, 1),
    openTypeOS2TypoDescender=(_integerFormatter, 1),
    openTypeOS2TypoLineGap=(_integerFormatter, 1),
    openTypeOS2WinAscent=(_nonNegativeIntegerFormatter, 1),
    openTypeOS2WinDescent=(_nonNegativeIntegerFormatter, 1),
    openTypeOS2SubscriptXSize=(_integerFormatter, 0),
    openTypeOS2SubscriptYSize=(_integerFormatter, 1),
    openTypeOS2SubscriptXOffset=(_integerFormatter, 0),
    openTypeOS2SubscriptYOffset=(_integerFormatter, 1),
    openTypeOS2SuperscriptXSize=(_integerFormatter, 0),
    openTypeOS2SuperscriptYSize=(_integerFormatter, 1),
    openTypeOS2SuperscriptXOffset=(_integerFormatter, 0),
    openTypeOS2SuperscriptYOffset=(_integerFormatter, 1),
    openTypeOS2StrikeoutSize=(_integerFormatter, 1),
    openTypeOS2StrikeoutPosition=(_integerFormatter, 1),

    openTypeVheaVertTypoAscender=(_integerFormatter, 1),
    openTypeVheaVertTypoDescender=(_integerFormatter, 1),
    openTypeVheaVertTypoLineGap=(_integerFormatter, 1),
    openTypeVheaCaretSlopeRise=(_integerFormatter, 1),
    openTypeVheaCaretSlopeRun=(_integerFormatter, 1),
    openTypeVheaCaretOffset=(_integerFormatter, 1),

    postscriptSlantAngle=(_numberFormatter, 3),
    postscriptUnderlineThickness=(_numberFormatter, 1),
    postscriptUnderlinePosition=(_numberFormatter, 1),
    postscriptBlueValues=(_numberListFormatter, 1),
    postscriptOtherBlues=(_numberListFormatter, 1),
    postscriptFamilyBlues=(_numberListFormatter, 1),
    postscriptFamilyOtherBlues=(_numberListFormatter, 1),
    postscriptStemSnapH=(_numberListFormatter, 0),
    postscriptStemSnapV=(_numberListFormatter, 1),
    postscriptBlueFuzz=(_numberFormatter, 1),
    postscriptBlueShift=(_numberFormatter, 1),
    postscriptBlueScale=(_floatFormatter, 1),
    postscriptDefaultWidthX=(_numberFormatter, 0),
    postscriptNominalWidthX=(_numberFormatter, 0),
    # this will be handled in a special way
    # postscriptWeightName=unicode
)

_numberListAttrs = {
    attr
    for attr, (formatter, _) in _infoAttrs.items()
    if formatter is _numberListFormatter
}

_postscriptWeightNameOptions = {
    100 : "Thin",
    200 : "Extra-light",
    300 : "Light",
    400 : "Normal",
    500 : "Medium",
    600 : "Semi-bold",
    700 : "Bold",
    800 : "Extra-bold",
    900 : "Black"
}

if __name__ == "__main__":
    import sys
    import doctest
    sys.exit(doctest.testmod().failed)
