from __future__ import print_function, absolute_import
from copy import deepcopy
from collections import OrderedDict
from fontMath.mathFunctions import (
    add, addPt, div, divPt, mul, mulPt, _roundNumber, sub, subPt)
from fontMath.mathGuideline import (
    _compressGuideline, _expandGuideline, _pairGuidelines,
    _processMathOneGuidelines, _processMathTwoGuidelines, _roundGuidelines)
from fontTools.pens.pointPen import AbstractPointPen

# ------------------
# UFO 3 branch notes
# ------------------
#
# to do:
# X components
#   X identifiers
# X contours
#   X identifiers
# X points
#   X identifiers
# X guidelines
# X height
# X image
#
# - is there any cruft that can be removed?
# X why is divPt here? move all of those to the math functions
# - FilterRedundantPointPen._flushContour is a mess
# X for the pt math functions, always send (x, y) factors instead
#   of coercing within the function. the coercion can happen at
#   the beginning of the _processMathTwo method.
#   - try list comprehensions in the point math for speed
#
# Questionable stuff:
# X is getRef needed?
# X nothing is ever set to _structure. should it be?
# X should the compatibilty be a function or pen?
# X the lib import is shallow and modifications to
#   lower level objects (ie dict) could modify the
#   original object. this probably isn't desirable.
#   deepcopy won't work here since it will try to
#   maintain the original class. may need to write
#   a custom copier. or maybe something like this
#   would be sufficient:
#     self.lib = deepcopy(dict(glyph.lib))
#   the class would be maintained for everything but
#   the top level. that shouldn't matter for the
#   purposes here.
# - __cmp__ is dubious but harmless i suppose.
# X is generationCount needed?
# X can box become bounds? have both?

try:
    basestring, xrange
    range = xrange
except NameError:
    basestring = str


class MathGlyph(object):

    """
    A very shallow glyph object for rapid math operations.

    Notes about glyph math:
    -   absolute contour compatibility is required
    -   absolute component, anchor, guideline and image compatibility is NOT required.
        in cases of incompatibility in this data, only compatible data is processed and
        returned. becuase of this, anchors and components may not be returned in the
        same order as the original.
    """

    def __init__(self, glyph, scaleComponentTransform=True, strict=False):
        """Initialize a new MathGlyph object.

        Args:
            glyph: Input defcon or defcon-like Glyph object to copy from. Set to None to
                to make an empty MathGlyph.
            scaleComponentTransform (bool): when performing multiplication or division, by
                default all elements of a component's affine transformation matrix are
                multiplied by the given scalar. If scaleComponentTransform is False, then
                only the component's xOffset and yOffset attributes are scaled, whereas the
                xScale, xyScale, yxScale and yScale attributes are kept unchanged.
            strict (bool): when set to False, offcurve points will be added to all
                straight segments to improve compatibility. Any offcurves that are
                still on-point will be filtered when extracted. When set to True,
                no offcurves will be added or filtered.
        """
        self.scaleComponentTransform = scaleComponentTransform
        self.contours = []
        self.components = []
        self.strict = strict
        if glyph is None:
            self.anchors = []
            self.guidelines = []
            self.image = _expandImage(None)
            self.lib = {}
            self.name = None
            self.unicodes = None
            self.width = None
            self.height = None
            self.note = None
        else:
            p = MathGlyphPen(self, strict=self.strict)
            glyph.drawPoints(p)
            self.anchors = [dict(anchor) for anchor in glyph.anchors]
            self.guidelines = [_expandGuideline(guideline) for guideline in glyph.guidelines]
            self.image = _expandImage(glyph.image)
            self.lib = deepcopy(dict(glyph.lib))
            self.name = glyph.name
            self.unicodes = list(glyph.unicodes)
            self.width = glyph.width
            self.height = glyph.height
            self.note = glyph.note

    def __eq__(self, other):
        try:
            return all(getattr(self, attr) == getattr(other, attr)
                       for attr in ("name", "unicodes", "width", "height",
                                    "note", "lib", "contours", "components",
                                    "anchors", "guidelines", "image"))
        except AttributeError:
            return NotImplemented

    def __ne__(self, other):
        return not self == other

    # ----
    # Copy
    # ----

    def copy(self):
        """return a new MathGlyph containing all data in self"""
        return MathGlyph(self)

    def copyWithoutMathSubObjects(self):
        """
        return a new MathGlyph containing all data except:
        contours
        components
        anchors
        guidelines

        this is used mainly for internal glyph math.
        """
        n = MathGlyph(None)
        n.name = self.name
        if self.unicodes is not None:
            n.unicodes = list(self.unicodes)
        n.width = self.width
        n.height = self.height
        n.note = self.note
        n.lib = deepcopy(dict(self.lib))
        return n

    # ----
    # Math
    # ----

    # math with other glyph

    def __add__(self, otherGlyph):
        copiedGlyph = self.copyWithoutMathSubObjects()
        self._processMathOne(copiedGlyph, otherGlyph, addPt, add)
        return copiedGlyph

    def __sub__(self, otherGlyph):
        copiedGlyph = self.copyWithoutMathSubObjects()
        self._processMathOne(copiedGlyph, otherGlyph, subPt, sub)
        return copiedGlyph

    def _processMathOne(self, copiedGlyph, otherGlyph, ptFunc, func):
        # width
        copiedGlyph.width = func(self.width, otherGlyph.width)
        # height
        copiedGlyph.height = func(self.height, otherGlyph.height)
        # contours
        copiedGlyph.contours = []
        if self.contours:
            copiedGlyph.contours = _processMathOneContours(self.contours, otherGlyph.contours, ptFunc)
        # components
        copiedGlyph.components = []
        if self.components:
            componentPairs = _pairComponents(self.components, otherGlyph.components)
            copiedGlyph.components = _processMathOneComponents(componentPairs, ptFunc)
        # anchors
        copiedGlyph.anchors = []
        if self.anchors:
            anchorTree1 = _anchorTree(self.anchors)
            anchorTree2 = _anchorTree(otherGlyph.anchors)
            anchorPairs = _pairAnchors(anchorTree1, anchorTree2)
            copiedGlyph.anchors = _processMathOneAnchors(anchorPairs, ptFunc)
        # guidelines
        copiedGlyph.guidelines = []
        if self.guidelines:
            guidelinePairs = _pairGuidelines(self.guidelines, otherGlyph.guidelines)
            copiedGlyph.guidelines = _processMathOneGuidelines(guidelinePairs, ptFunc, func)
        # image
        copiedGlyph.image = _expandImage(None)
        imagePair = _pairImages(self.image, otherGlyph.image)
        if imagePair:
            copiedGlyph.image = _processMathOneImage(imagePair, ptFunc)

    # math with factor

    def __mul__(self, factor):
        if not isinstance(factor, tuple):
            factor = (factor, factor)
        copiedGlyph = self.copyWithoutMathSubObjects()
        self._processMathTwo(copiedGlyph, factor, mulPt, mul)
        return copiedGlyph

    __rmul__ = __mul__

    def __div__(self, factor):
        if not isinstance(factor, tuple):
            factor = (factor, factor)
        copiedGlyph = self.copyWithoutMathSubObjects()
        self._processMathTwo(copiedGlyph, factor, divPt, div)
        return copiedGlyph

    __truediv__ = __div__

    __rdiv__ = __div__

    __rtruediv__ = __rdiv__

    def _processMathTwo(self, copiedGlyph, factor, ptFunc, func):
        # width
        copiedGlyph.width = func(self.width, factor[0])
        # height
        copiedGlyph.height = func(self.height, factor[1])
        # contours
        copiedGlyph.contours = []
        if self.contours:
            copiedGlyph.contours = _processMathTwoContours(self.contours, factor, ptFunc)
        # components
        copiedGlyph.components = []
        if self.components:
            copiedGlyph.components = _processMathTwoComponents(
                self.components, factor, ptFunc, scaleComponentTransform=self.scaleComponentTransform
            )
        # anchors
        copiedGlyph.anchors = []
        if self.anchors:
            copiedGlyph.anchors = _processMathTwoAnchors(self.anchors, factor, ptFunc)
        # guidelines
        copiedGlyph.guidelines = []
        if self.guidelines:
            copiedGlyph.guidelines = _processMathTwoGuidelines(self.guidelines, factor, func)
        # image
        if self.image:
            copiedGlyph.image = _processMathTwoImage(self.image, factor, ptFunc)

    # -------
    # Additional math
    # -------
    def round(self, digits=None):
        """round the geometry."""
        copiedGlyph = self.copyWithoutMathSubObjects()
        # misc
        copiedGlyph.width = _roundNumber(self.width, digits)
        copiedGlyph.height = _roundNumber(self.height, digits)
        # contours
        copiedGlyph.contours = []
        if self.contours:
            copiedGlyph.contours = _roundContours(self.contours, digits)
        # components
        copiedGlyph.components = []
        if self.components:
            copiedGlyph.components = _roundComponents(self.components, digits)
        # guidelines
        copiedGlyph.guidelines = []
        if self.guidelines:
            copiedGlyph.guidelines = _roundGuidelines(self.guidelines, digits)
        # anchors
        copiedGlyph.anchors = []
        if self.anchors:
            copiedGlyph.anchors = _roundAnchors(self.anchors, digits)
        # image
        copiedGlyph.image = None
        if self.image:
            copiedGlyph.image = _roundImage(self.image, digits)
        return copiedGlyph


    # -------
    # Pen API
    # -------

    def getPointPen(self):
        """get a point pen for drawing to this object"""
        return MathGlyphPen(self)

    def drawPoints(self, pointPen, filterRedundantPoints=False):
        """draw self using pointPen"""
        if filterRedundantPoints:
            pointPen = FilterRedundantPointPen(pointPen)
        for contour in self.contours:
            pointPen.beginPath(identifier=contour["identifier"])
            for segmentType, pt, smooth, name, identifier in contour["points"]:
                pointPen.addPoint(pt=pt, segmentType=segmentType, smooth=smooth, name=name, identifier=identifier)
            pointPen.endPath()
        for component in self.components:
            pointPen.addComponent(component["baseGlyph"], component["transformation"], identifier=component["identifier"])

    def draw(self, pen, filterRedundantPoints=False):
        """draw self using pen"""
        from fontTools.pens.pointPen import PointToSegmentPen
        pointPen = PointToSegmentPen(pen)
        self.drawPoints(pointPen, filterRedundantPoints=filterRedundantPoints)

    # ----------
    # Extraction
    # ----------

    def extractGlyph(self, glyph, pointPen=None, onlyGeometry=False):
        """
        "rehydrate" to a glyph. this requires
        a glyph as an argument. if a point pen other
        than the type of pen returned by glyph.getPointPen()
        is required for drawing, send this the needed point pen.
        """
        if pointPen is None:
            pointPen = glyph.getPointPen()
        glyph.clearContours()
        glyph.clearComponents()
        glyph.clearAnchors()
        glyph.clearGuidelines()
        glyph.lib.clear()
        if self.strict:
            self.drawPoints(pointPen)
        else:
            cleanerPen = FilterRedundantPointPen(pointPen)
            self.drawPoints(cleanerPen)
        glyph.anchors = [dict(anchor) for anchor in self.anchors]
        glyph.guidelines = [_compressGuideline(guideline) for guideline in self.guidelines]
        glyph.image = _compressImage(self.image)
        glyph.lib = deepcopy(dict(self.lib))
        glyph.width = self.width
        glyph.height = self.height
        glyph.note = self.note
        if not onlyGeometry:
            glyph.name = self.name
            glyph.unicodes = list(self.unicodes)
        return glyph


# ----------
# Point Pens
# ----------

class MathGlyphPen(AbstractPointPen):

    """
    Point pen for building MathGlyph data structures.
    """

    def __init__(self, glyph=None, strict=False):
        self.strict = strict # do not add offcurvess
        if glyph is None:
            self.contours = []
            self.components = []
        else:
            self.contours = glyph.contours
            self.components = glyph.components
        self._contourIdentifier = None
        self._points = []

    def _flushContour(self):
        """
        This normalizes the contour so that:
        - there are no line segments. in their place will be
          curve segments with the off curves positioned on top
          of the previous on curve and the new curve on curve.
        - the contour starts with an on curve
        """
        self.contours.append(
            dict(identifier=self._contourIdentifier, points=[])
        )
        contourPoints = self.contours[-1]["points"]
        points = self._points
        # move offcurves at the beginning of the contour to the end
        haveOnCurve = False
        for point in points:
            if point[0] is not None:
                haveOnCurve = True
                break
        if haveOnCurve:
            while 1:
                if points[0][0] is None:
                    point = points.pop(0)
                    points.append(point)
                else:
                    break
        # convert lines to curves
        holdingOffCurves = []
        for index, point in enumerate(points):
            segmentType = point[0]
            if segmentType == "line" and not self.strict:
                pt, smooth, name, identifier = point[1:]
                prevPt = points[index - 1][1]
                if index == 0:
                    holdingOffCurves.append((None, prevPt, False, None, None))
                    holdingOffCurves.append((None, pt, False, None, None))
                else:
                    contourPoints.append((None, prevPt, False, None, None))
                    contourPoints.append((None, pt, False, None, None))
                contourPoints.append(("curve", pt, smooth, name, identifier))
            else:
                contourPoints.append(point)
        contourPoints.extend(holdingOffCurves)

    def beginPath(self, identifier=None):
        self._contourIdentifier = identifier
        self._points = []

    def addPoint(self, pt, segmentType=None, smooth=False, name=None, identifier=None, **kwargs):
        self._points.append((segmentType, pt, smooth, name, identifier))

    def endPath(self):
        self._flushContour()

    def addComponent(self, baseGlyph, transformation, identifier=None, **kwargs):
        self.components.append(dict(baseGlyph=baseGlyph, transformation=transformation, identifier=identifier))


class FilterRedundantPointPen(AbstractPointPen):

    def __init__(self, anotherPointPen):
        self._pen = anotherPointPen
        self._points = []

    def _flushContour(self):
        # keep the point order and
        # change the removed flag if the point should be removed
        points = self._points
        for index, data in enumerate(points):
            if data["segmentType"] == "curve":
                prevOnCurve = points[index - 3]
                prevOffCurve1 = points[index - 2]
                prevOffCurve2 = points[index - 1]
                # check if the curve is a super bezier
                if prevOnCurve["segmentType"] is not None:
                    if prevOnCurve["pt"] == prevOffCurve1["pt"] and prevOffCurve2["pt"] == data["pt"]:
                        # the off curves are on top of the on curve point
                        # change the segmentType
                        data["segmentType"] = "line"
                        # flag the off curves to be removed
                        prevOffCurve1["removed"] = True
                        prevOffCurve2["removed"] = True

        for data in points:
            if not data["removed"]:
                self._pen.addPoint(
                    data["pt"],
                    data["segmentType"],
                    smooth=data["smooth"],
                    name=data["name"],
                    identifier=data["identifier"]
                )

    def beginPath(self, identifier=None, **kwargs):
        self._points = []
        self._pen.beginPath(identifier=identifier)

    def addPoint(self, pt, segmentType=None, smooth=False, name=None, identifier=None, **kwargs):
        self._points.append(
            dict(
                pt=pt,
                segmentType=segmentType,
                smooth=smooth,
                name=name,
                identifier=identifier,
                removed=False
            )
        )

    def endPath(self):
        self._flushContour()
        self._pen.endPath()

    def addComponent(self, baseGlyph, transformation, identifier=None, **kwargs):
        self._pen.addComponent(baseGlyph, transformation, identifier)


# -------
# Support
# -------

# contours

def _processMathOneContours(contours1, contours2, func):
    result = []
    for index, contour1 in enumerate(contours1):
        contourIdentifier = contour1["identifier"]
        points1 = contour1["points"]
        points2 = contours2[index]["points"]
        resultPoints = []
        for index, point in enumerate(points1):
            segmentType, pt1, smooth, name, identifier = point
            pt2 = points2[index][1]
            pt = func(pt1, pt2)
            resultPoints.append((segmentType, pt, smooth, name, identifier))
        result.append(dict(identifier=contourIdentifier, points=resultPoints))
    return result

def _processMathTwoContours(contours, factor, func):
    result = []
    for contour in contours:
        contourIdentifier = contour["identifier"]
        points = contour["points"]
        resultPoints = []
        for point in points:
            segmentType, pt, smooth, name, identifier = point
            pt = func(pt, factor)
            resultPoints.append((segmentType, pt, smooth, name, identifier))
        result.append(dict(identifier=contourIdentifier, points=resultPoints))
    return result

# anchors

def _anchorTree(anchors):
    tree = OrderedDict()
    for anchor in anchors:
        x = anchor["x"]
        y = anchor["y"]
        name = anchor.get("name")
        identifier = anchor.get("identifier")
        color = anchor.get("color")
        if name not in tree:
            tree[name] = []
        tree[name].append((identifier, x, y, color))
    return tree

def _pairAnchors(anchorDict1, anchorDict2):
    """
    Anchors are paired using the following rules:


    Matching Identifiers
    --------------------
    >>> anchors1 = {
    ...     "test" : [
    ...         (None, 1, 2, None),
    ...         ("identifier 1", 3, 4, None)
    ...      ]
    ... }
    >>> anchors2 = {
    ...     "test" : [
    ...         ("identifier 1", 1, 2, None),
    ...         (None, 3, 4, None)
    ...      ]
    ... }
    >>> expected = [
    ...     (
    ...         dict(name="test", identifier=None, x=1, y=2, color=None),
    ...         dict(name="test", identifier=None, x=3, y=4, color=None)
    ...     ),
    ...     (
    ...         dict(name="test", identifier="identifier 1", x=3, y=4, color=None),
    ...         dict(name="test", identifier="identifier 1", x=1, y=2, color=None)
    ...     )
    ... ]
    >>> _pairAnchors(anchors1, anchors2) == expected
    True

    Mismatched Identifiers
    ----------------------
    >>> anchors1 = {
    ...     "test" : [
    ...         ("identifier 1", 3, 4, None)
    ...      ]
    ... }
    >>> anchors2 = {
    ...     "test" : [
    ...         ("identifier 2", 1, 2, None),
    ...      ]
    ... }
    >>> expected = [
    ...     (
    ...         dict(name="test", identifier="identifier 1", x=3, y=4, color=None),
    ...         dict(name="test", identifier="identifier 2", x=1, y=2, color=None)
    ...     )
    ... ]
    >>> _pairAnchors(anchors1, anchors2) == expected
    True
    """
    pairs = []
    for name, anchors1 in anchorDict1.items():
        if name not in anchorDict2:
            continue
        anchors2 = anchorDict2[name]
        # align with matching identifiers
        removeFromAnchors1 = []
        for anchor1 in anchors1:
            match = None
            identifier = anchor1[0]
            for anchor2 in anchors2:
                if anchor2[0] == identifier:
                    match = anchor2
                    break
            if match is not None:
                anchor2 = match
                anchors2.remove(anchor2)
                removeFromAnchors1.append(anchor1)
                a1 = dict(name=name, identifier=identifier)
                a1["x"], a1["y"], a1["color"] = anchor1[1:]
                a2 = dict(name=name, identifier=identifier)
                a2["x"], a2["y"], a2["color"] = anchor2[1:]
                pairs.append((a1, a2))
        for anchor1 in removeFromAnchors1:
            anchors1.remove(anchor1)
        if not anchors1 or not anchors2:
            continue
        # align by index
        while 1:
            anchor1 = anchors1.pop(0)
            anchor2 = anchors2.pop(0)
            a1 = dict(name=name)
            a1["identifier"], a1["x"], a1["y"], a1["color"] = anchor1
            a2 = dict(name=name, identifier=identifier)
            a2["identifier"], a2["x"], a2["y"], a2["color"] = anchor2
            pairs.append((a1, a2))
            if not anchors1:
                break
            if not anchors2:
                break
    return pairs

def _processMathOneAnchors(anchorPairs, func):
    result = []
    for anchor1, anchor2 in anchorPairs:
        anchor = dict(anchor1)
        pt1 = (anchor1["x"], anchor1["y"])
        pt2 = (anchor2["x"], anchor2["y"])
        anchor["x"], anchor["y"] = func(pt1, pt2)
        result.append(anchor)
    return result

def _processMathTwoAnchors(anchors, factor, func):
    result = []
    for anchor in anchors:
        anchor = dict(anchor)
        pt = (anchor["x"], anchor["y"])
        anchor["x"], anchor["y"] = func(pt, factor)
        result.append(anchor)
    return result

# components

def _pairComponents(components1, components2):
    components1 = list(components1)
    components2 = list(components2)
    pairs = []
    # align with matching identifiers
    removeFromComponents1 = []
    for component1 in components1:
        baseGlyph = component1["baseGlyph"]
        identifier = component1["identifier"]
        match = None
        for component2 in components2:
            if component2["baseGlyph"] == baseGlyph and component2["identifier"] == identifier:
                match = component2
                break
        if match is not None:
            component2 = match
            removeFromComponents1.append(component1)
            components2.remove(component2)
            pairs.append((component1, component2))
    for component1 in removeFromComponents1:
        components1.remove(component1)
    # align with index
    for component1 in components1:
        baseGlyph = component1["baseGlyph"]
        for component2 in components2:
            if component2["baseGlyph"] == baseGlyph:
                components2.remove(component2)
                pairs.append((component1, component2))
                break
    return pairs

def _processMathOneComponents(componentPairs, func):
    result = []
    for component1, component2 in componentPairs:
        component = dict(component1)
        component["transformation"] = _processMathOneTransformation(component1["transformation"], component2["transformation"], func)
        result.append(component)
    return result

def _processMathTwoComponents(components, factor, func, scaleComponentTransform=True):
    result = []
    for component in components:
        component = dict(component)
        component["transformation"] = _processMathTwoTransformation(
            component["transformation"], factor, func, doScale=scaleComponentTransform
        )
        result.append(component)
    return result

# image

_imageTransformationKeys = "xScale xyScale yxScale yScale xOffset yOffset".split(" ")
_defaultImageTransformation = (1, 0, 0, 1, 0, 0)
_defaultImageTransformationDict = {}
for key, value in zip(_imageTransformationKeys, _defaultImageTransformation):
    _defaultImageTransformationDict[key] = value

def _expandImage(image):
    if image is None:
        fileName = None
        transformation = _defaultImageTransformation
        color = None
    else:
        if hasattr(image, "naked"):
            image = image.naked()
        fileName = image["fileName"]
        color = image.get("color")
        transformation = tuple([
            image.get(key, _defaultImageTransformationDict[key])
            for key in _imageTransformationKeys
        ])
    return dict(fileName=fileName, transformation=transformation, color=color)

def _compressImage(image):
    fileName = image["fileName"]
    transformation = image["transformation"]
    color = image["color"]
    if fileName is None:
        return
    image = dict(fileName=fileName, color=color)
    for index, key in enumerate(_imageTransformationKeys):
        image[key] = transformation[index]
    return image

def _pairImages(image1, image2):
    if image1["fileName"] != image2["fileName"]:
        return ()
    return (image1, image2)

def _processMathOneImage(imagePair, func):
    image1, image2 = imagePair
    fileName = image1["fileName"]
    color = image1["color"]
    transformation = _processMathOneTransformation(image1["transformation"], image2["transformation"], func)
    return dict(fileName=fileName, transformation=transformation, color=color)

def _processMathTwoImage(image, factor, func):
    fileName = image["fileName"]
    color = image["color"]
    transformation = _processMathTwoTransformation(image["transformation"], factor, func)
    return dict(fileName=fileName, transformation=transformation, color=color)


# transformations

def _processMathOneTransformation(transformation1, transformation2, func):
    xScale1, xyScale1, yxScale1, yScale1, xOffset1, yOffset1 = transformation1
    xScale2, xyScale2, yxScale2, yScale2, xOffset2, yOffset2 = transformation2
    xScale, yScale = func((xScale1, yScale1), (xScale2, yScale2))
    xyScale, yxScale = func((xyScale1, yxScale1), (xyScale2, yxScale2))
    xOffset, yOffset = func((xOffset1, yOffset1), (xOffset2, yOffset2))
    return (xScale, xyScale, yxScale, yScale, xOffset, yOffset)

def _processMathTwoTransformation(transformation, factor, func, doScale=True):
    xScale, xyScale, yxScale, yScale, xOffset, yOffset = transformation
    if doScale:
        xScale, yScale = func((xScale, yScale), factor)
        xyScale, yxScale = func((xyScale, yxScale), factor)
    xOffset, yOffset = func((xOffset, yOffset), factor)
    return (xScale, xyScale, yxScale, yScale, xOffset, yOffset)


# rounding

def _roundContours(contours, digits=None):
    results = []
    for contour in contours:
        contour = dict(contour)
        roundedPoints = []
        for segmentType, pt, smooth, name, identifier in contour["points"]:
            roundedPt = (_roundNumber(pt[0],digits), _roundNumber(pt[1],digits))
            roundedPoints.append((segmentType, roundedPt, smooth, name, identifier))
        contour["points"] = roundedPoints
        results.append(contour)
    return results

def _roundTransformation(transformation, digits=None):
    xScale, xyScale, yxScale, yScale, xOffset, yOffset = transformation
    return (xScale, xyScale, yxScale, yScale, _roundNumber(xOffset, digits), _roundNumber(yOffset, digits))

def _roundImage(image, digits=None):
    image = dict(image)
    fileName = image["fileName"]
    color = image["color"]
    transformation = _roundTransformation(image["transformation"], digits)
    return dict(fileName=fileName, transformation=transformation, color=color)

def _roundComponents(components, digits=None):
    result = []
    for component in components:
        component = dict(component)
        component["transformation"] = _roundTransformation(component["transformation"], digits)
        result.append(component)
    return result

def _roundAnchors(anchors, digits=None):
    result = []
    for anchor in anchors:
        anchor = dict(anchor)
        anchor["x"], anchor["y"] = _roundNumber(anchor["x"], digits), _roundNumber(anchor["y"], digits)
        result.append(anchor)
    return result


if __name__ == "__main__":
    import sys
    import doctest
    sys.exit(doctest.testmod().failed)
