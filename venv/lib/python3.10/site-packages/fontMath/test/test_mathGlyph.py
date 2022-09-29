from __future__ import division
import unittest
from fontTools.pens.pointPen import AbstractPointPen
from fontMath.mathFunctions import addPt, mulPt
from fontMath.mathGlyph import (
    MathGlyph, MathGlyphPen, FilterRedundantPointPen,
    _processMathOneContours, _processMathTwoContours, _anchorTree,
    _pairAnchors, _processMathOneAnchors, _processMathTwoAnchors,
    _pairComponents, _processMathOneComponents, _processMathTwoComponents,
    _expandImage, _compressImage, _pairImages, _processMathOneImage,
    _processMathTwoImage, _processMathOneTransformation,
    _processMathTwoTransformation, _roundContours, _roundTransformation,
    _roundImage, _roundComponents, _roundAnchors
)


try:
    basestring, xrange
    range = xrange
except NameError:
    basestring = str


class MathGlyphTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)

    def _setupTestGlyph(self):
        glyph = MathGlyph(None)
        glyph.width = 0
        glyph.height = 0
        return glyph

    def test__eq__(self):
        glyph1 = self._setupTestGlyph()
        glyph2 = self._setupTestGlyph()
        self.assertEqual(glyph1, glyph2)

        glyph2.width = 1
        self.assertFalse(glyph1 == glyph2)

        nonglyph = object()
        self.assertFalse(glyph1 == nonglyph)

        glyph1 = MathGlyph(None)
        glyph1.name = 'space'
        glyph1.width = 100

        class MyGlyph(object):
            pass
        other = MyGlyph()
        other.name = 'space'
        other.width = 100
        other.height = None
        other.contours = []
        other.components = []
        other.anchors = []
        other.guidelines = []
        other.image = {'fileName': None,
                       'transformation': (1, 0, 0, 1, 0, 0),
                       'color': None}
        other.lib = {}
        other.unicodes = None
        other.note = None
        self.assertEqual(glyph1, other)

    def test__ne__(self):
        glyph1 = self._setupTestGlyph()
        glyph2 = MathGlyph(None)
        glyph2.width = 1
        glyph2.name = 'a'
        self.assertNotEqual(glyph1, glyph2)
        self.assertNotEqual(glyph1, 'foo')

    def test_width_add(self):
        glyph1 = self._setupTestGlyph()
        glyph1.width = 1
        glyph2 = self._setupTestGlyph()
        glyph2.width = 2
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.width, 3)

    def test_width_sub(self):
        glyph1 = self._setupTestGlyph()
        glyph1.width = 3
        glyph2 = self._setupTestGlyph()
        glyph2.width = 2
        glyph3 = glyph1 - glyph2
        self.assertEqual(glyph3.width, 1)

    def test_width_mul(self):
        glyph1 = self._setupTestGlyph()
        glyph1.width = 2
        glyph2 = glyph1 * 3
        self.assertEqual(glyph2.width, 6)
        glyph1 = self._setupTestGlyph()
        glyph1.width = 2
        glyph2 = glyph1 * (3, 1)
        self.assertEqual(glyph2.width, 6)

    def test_width_div(self):
        glyph1 = self._setupTestGlyph()
        glyph1.width = 7
        glyph2 = glyph1 / 2
        self.assertEqual(glyph2.width, 3.5)
        glyph1 = self._setupTestGlyph()
        glyph1.width = 7
        glyph2 = glyph1 / (2, 1)
        self.assertEqual(glyph2.width, 3.5)

    def test_width_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.width = 6.99
        glyph2 = glyph1.round()
        self.assertEqual(glyph2.width, 7)

    def test_height_add(self):
        glyph1 = self._setupTestGlyph()
        glyph1.height = 1
        glyph2 = self._setupTestGlyph()
        glyph2.height = 2
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.height, 3)

    def test_height_sub(self):
        glyph1 = self._setupTestGlyph()
        glyph1.height = 3
        glyph2 = self._setupTestGlyph()
        glyph2.height = 2
        glyph3 = glyph1 - glyph2
        self.assertEqual(glyph3.height, 1)

    def test_height_mul(self):
        glyph1 = self._setupTestGlyph()
        glyph1.height = 2
        glyph2 = glyph1 * 3
        self.assertEqual(glyph2.height, 6)
        glyph1 = self._setupTestGlyph()
        glyph1.height = 2
        glyph2 = glyph1 * (1, 3)
        self.assertEqual(glyph2.height, 6)

    def test_height_div(self):
        glyph1 = self._setupTestGlyph()
        glyph1.height = 7
        glyph2 = glyph1 / 2
        self.assertEqual(glyph2.height, 3.5)
        glyph1 = self._setupTestGlyph()
        glyph1.height = 7
        glyph2 = glyph1 / (1, 2)
        self.assertEqual(glyph2.height, 3.5)

    def test_height_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.height = 6.99
        glyph2 = glyph1.round()
        self.assertEqual(glyph2.height, 7)

    def test_contours_add(self):
        glyph1 = self._setupTestGlyph()
        glyph1.contours = [
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), True, "test", "1")])
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.contours = [
            dict(identifier="contour 1",
                 points=[("line", (1.55, 4.1), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (1.55, 4.1), True, "test", "1")])
        ]
        glyph3 = glyph1 + glyph2
        expected = [
            dict(identifier="contour 1",
                 points=[("line", (0.55 + 1.55, 3.1 + 4.1), False, "test",
                          "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55 + 1.55, 3.1 + 4.1), True, "test",
                          "1")])
        ]
        self.assertEqual(glyph3.contours, expected)

    def test_contours_sub(self):
        glyph1 = self._setupTestGlyph()
        glyph1.contours = [
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), True, "test", "1")])
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.contours = [
            dict(identifier="contour 1",
                 points=[("line", (1.55, 4.1), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (1.55, 4.1), True, "test", "1")])
        ]
        glyph3 = glyph1 - glyph2
        expected = [
            dict(identifier="contour 1",
                 points=[("line", (0.55 - 1.55, 3.1 - 4.1), False, "test",
                          "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55 - 1.55, 3.1 - 4.1), True, "test",
                          "1")])
        ]
        self.assertEqual(glyph3.contours, expected)

    def test_contours_mul(self):
        glyph1 = self._setupTestGlyph()
        glyph1.contours = [
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), True, "test", "1")])
        ]
        glyph2 = glyph1 * 2
        expected = [
            dict(identifier="contour 1",
                 points=[("line", (0.55 * 2, 3.1 * 2), False, "test",
                          "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55 * 2, 3.1 * 2), True, "test",
                          "1")])
        ]
        self.assertEqual(glyph2.contours, expected)

    def test_contours_div(self):
        glyph1 = self._setupTestGlyph()
        glyph1.contours = [
            dict(identifier="contour 1",
                 points=[("line", (1, 3.4), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (2, 3.1), True, "test", "1")])
        ]
        glyph2 = glyph1 / 2
        expected = [
            dict(identifier="contour 1",
                 points=[("line", (1/2, 3.4/2), False, "test",
                          "1")]),
            dict(identifier="contour 1",
                 points=[("line", (2/2, 3.1/2), True, "test",
                          "1")])
        ]
        self.assertEqual(glyph2.contours, expected)

    def test_contours_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.contours = [
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (0.55, 3.1), True, "test", "1")])
        ]
        glyph2 = glyph1.round()
        expected = [
            dict(identifier="contour 1",
                 points=[("line", (1, 3), False, "test", "1")]),
            dict(identifier="contour 1",
                 points=[("line", (1, 3), True, "test", "1")])
        ]
        self.assertEqual(glyph2.contours, expected)

    def test_components_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.components = [
            dict(baseGlyph="A", transformation=(1, 2, 3, 4, 5.1, 5.99),
                 identifier="1"),
        ]
        glyph2 = glyph1.round()
        expected = [
            dict(baseGlyph="A", transformation=(1, 2, 3, 4, 5, 6),
                 identifier="1")
        ]
        self.assertEqual(glyph2.components, expected)

    def test_guidelines_add_same_name_identifier_x_y_angle(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="foo", identifier="2", x=3, y=4, angle=2)
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="foo", identifier="2", x=3, y=4, angle=2),
            dict(name="foo", identifier="1", x=1, y=2, angle=1)
        ]
        expected = [
            dict(name="foo", identifier="1", x=2, y=4, angle=2),
            dict(name="foo", identifier="2", x=6, y=8, angle=4)
        ]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected)

    def test_guidelines_add_same_name_identifier(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="foo", identifier="2", x=1, y=2, angle=2),
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="foo", identifier="2", x=3, y=4, angle=3),
            dict(name="foo", identifier="1", x=3, y=4, angle=4)
        ]
        expected = [
            dict(name="foo", identifier="1", x=4, y=6, angle=5),
            dict(name="foo", identifier="2", x=4, y=6, angle=5)
        ]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected)

    def test_guidelines_add_same_name_x_y_angle(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="foo", identifier="2", x=3, y=4, angle=2),
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="foo", identifier="3", x=3, y=4, angle=2),
            dict(name="foo", identifier="4", x=1, y=2, angle=1)
        ]
        expected = [
            dict(name="foo", identifier="1", x=2, y=4, angle=2),
            dict(name="foo", identifier="2", x=6, y=8, angle=4)
        ]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected)

    def test_guidelines_add_same_identifier_x_y_angle(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="bar", identifier="2", x=3, y=4, angle=2),
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="xxx", identifier="2", x=3, y=4, angle=2),
            dict(name="yyy", identifier="1", x=1, y=2, angle=1)
        ]
        expected = [
            dict(name="foo", identifier="1", x=2, y=4, angle=2),
            dict(name="bar", identifier="2", x=6, y=8, angle=4)
        ]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected)

    def test_guidelines_add_same_name(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="bar", identifier="2", x=1, y=2, angle=2),
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="bar", identifier="3", x=3, y=4, angle=3),
            dict(name="foo", identifier="4", x=3, y=4, angle=4)
        ]
        expected = [
            dict(name="foo", identifier="1", x=4, y=6, angle=5),
            dict(name="bar", identifier="2", x=4, y=6, angle=5)
        ]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected)

    def test_guidelines_add_same_identifier(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="bar", identifier="2", x=1, y=2, angle=2),
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="xxx", identifier="2", x=3, y=4, angle=3),
            dict(name="yyy", identifier="1", x=3, y=4, angle=4)
        ]
        expected = [
            dict(name="foo", identifier="1", x=4, y=6, angle=5),
            dict(name="bar", identifier="2", x=4, y=6, angle=5)
        ]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected)

    def test_guidelines_mul(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(x=1, y=3, angle=5, name="test", identifier="1",
                 color="0,0,0,0")
        ]
        glyph2 = glyph1 * 3
        expected = [
            dict(x=1 * 3, y=3 * 3, angle=15, name="test", identifier="1",
                 color="0,0,0,0")
        ]
        self.assertEqual(glyph2.guidelines, expected)

    def test_guidelines_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(x=1.99, y=3.01, angle=5, name="test", identifier="1",
                 color="0,0,0,0")
        ]
        glyph2 = glyph1.round()
        expected = [
            dict(x=2, y=3, angle=5, name="test", identifier="1",
                 color="0,0,0,0")
        ]
        self.assertEqual(glyph2.guidelines, expected)

    def test_guidelines_valid_angle(self):
        glyph1 = self._setupTestGlyph()
        glyph1.guidelines = [
            dict(name="foo", identifier="1", x=0, y=0, angle=1)
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.guidelines = [
            dict(name="foo", identifier="1", x=0, y=0, angle=359)
        ]

        expected_add = [dict(name="foo", identifier="1", x=0, y=0, angle=0)]
        glyph3 = glyph1 + glyph2
        self.assertEqual(glyph3.guidelines, expected_add)

        expected_sub = [dict(name="foo", identifier="1", x=0, y=0, angle=2)]
        glyph4 = glyph1 - glyph2
        self.assertEqual(glyph4.guidelines, expected_sub)

        expected_mul = [dict(name="foo", identifier="1", x=0, y=0, angle=355)]
        glyph5 = glyph2 * 5
        self.assertEqual(glyph5.guidelines, expected_mul)

        expected_div = [dict(name="foo", identifier="1", x=0, y=0, angle=71.8)]
        glyph6 = glyph2 / 5
        self.assertEqual(glyph6.guidelines, expected_div)

    def test_anchors_add(self):
        glyph1 = self._setupTestGlyph()
        glyph1.anchors = [
            dict(x=1, y=-2, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.anchors = [
            dict(x=3, y=-4, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph3 = glyph1 + glyph2
        expected = [
            dict(x=4, y=-6, name="foo", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(glyph3.anchors, expected)

    def test_anchors_sub(self):
        glyph1 = self._setupTestGlyph()
        glyph1.anchors = [
            dict(x=1, y=-2, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph2 = self._setupTestGlyph()
        glyph2.anchors = [
            dict(x=3, y=-4, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph3 = glyph1 - glyph2
        expected = [
            dict(x=-2, y=2, name="foo", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(glyph3.anchors, expected)

    def test_anchors_mul(self):
        glyph1 = self._setupTestGlyph()
        glyph1.anchors = [
            dict(x=1, y=-2, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph2 = glyph1 * 2
        expected = [
            dict(x=2, y=-4, name="foo", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(glyph2.anchors, expected)

    def test_anchors_div(self):
        glyph1 = self._setupTestGlyph()
        glyph1.anchors = [
            dict(x=1, y=-2, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph2 = glyph1 / 2
        expected = [
            dict(x=0.5, y=-1, name="foo", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(glyph2.anchors, expected)

    def test_anchors_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.anchors = [
            dict(x=99.9, y=-100.1, name="foo", identifier="1", color="0,0,0,0")
        ]
        glyph2 = glyph1.round()
        expected = [
            dict(x=100, y=-100, name="foo", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(glyph2.anchors, expected)

    def test_image_round(self):
        glyph1 = self._setupTestGlyph()
        glyph1.image = dict(fileName="foo",
                            transformation=(1, 2, 3, 4, 4.99, 6.01),
                            color="0,0,0,0")
        expected = dict(fileName="foo", transformation=(1, 2, 3, 4, 5, 6),
                        color="0,0,0,0")
        glyph2 = glyph1.round()
        self.assertEqual(glyph2.image, expected)


class MathGlyphPenTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)

    def test_pen_with_lines(self):
        pen = MathGlyphPen()
        pen.beginPath(identifier="contour 1")
        pen.addPoint((0,   100), "line", smooth=False, name="name 1",
                     identifier="point 1")
        pen.addPoint((100, 100), "line", smooth=False, name="name 2",
                     identifier="point 2")
        pen.addPoint((100, 0),   "line", smooth=False, name="name 3",
                     identifier="point 3")
        pen.addPoint((0,   0),   "line", smooth=False, name="name 4",
                     identifier="point 4")
        pen.endPath()
        expected = [
            ("curve", (0,   100), False, "name 1", "point 1"),
            (None,    (0,   100), False, None,     None),
            (None,    (100, 100), False, None,     None),
            ("curve", (100, 100), False, "name 2", "point 2"),
            (None,    (100, 100), False, None,     None),
            (None,    (100, 0),   False, None,     None),
            ("curve", (100, 0),   False, "name 3", "point 3"),
            (None,    (100, 0),   False, None,     None),
            (None,    (0,   0),   False, None,     None),
            ("curve", (0,   0),   False, "name 4", "point 4"),
            (None,    (0,   0),   False, None,     None),
            (None,    (0,   100), False, None,     None),
        ]
        self.assertEqual(pen.contours[-1]["points"], expected)
        self.assertEqual(pen.contours[-1]["identifier"], 'contour 1')

    def test_pen_with_lines_strict(self):
        pen = MathGlyphPen(strict=True)
        pen.beginPath(identifier="contour 1")
        pen.addPoint((0,   100), "line", smooth=False, name="name 1",
                     identifier="point 1")
        pen.addPoint((100, 100), "line", smooth=False, name="name 2",
                     identifier="point 2")
        pen.addPoint((100, 0),   "line", smooth=False, name="name 3",
                     identifier="point 3")
        pen.addPoint((0,   0),   "line", smooth=False, name="name 4",
                     identifier="point 4")
        pen.endPath()
        expected = [
            ("line", (0,   100), False, "name 1", "point 1"),
            ("line", (100, 100), False, "name 2", "point 2"),
            ("line", (100, 0),   False, "name 3", "point 3"),
            ("line", (0,   0),   False, "name 4", "point 4"),
        ]
        self.assertEqual(pen.contours[-1]["points"], expected)
        self.assertEqual(pen.contours[-1]["identifier"], 'contour 1')

    def test_pen_with_lines_and_curves(self):
        pen = MathGlyphPen()
        pen.beginPath(identifier="contour 1")
        pen.addPoint((0,   50), "curve", smooth=False, name="name 1",
                     identifier="point 1")
        pen.addPoint((50, 100), "line",  smooth=False, name="name 2",
                     identifier="point 2")
        pen.addPoint((75, 100), None)
        pen.addPoint((100, 75), None)
        pen.addPoint((100, 50), "curve", smooth=True,  name="name 3",
                     identifier="point 3")
        pen.addPoint((100, 25), None)
        pen.addPoint((75,   0), None)
        pen.addPoint((50,   0), "curve", smooth=False, name="name 4",
                     identifier="point 4")
        pen.addPoint((25,   0), None)
        pen.addPoint((0,   25), None)
        pen.endPath()
        expected = [
            ("curve", (0,   50), False, "name 1", "point 1"),
            (None,    (0,   50), False, None,     None),
            (None,    (50, 100), False, None,     None),
            ("curve", (50, 100), False, "name 2", "point 2"),
            (None,    (75, 100), False, None,     None),
            (None,    (100, 75), False, None,     None),
            ("curve", (100, 50), True, "name 3", "point 3"),
            (None,    (100, 25), False, None,     None),
            (None,    (75,   0), False, None,     None),
            ("curve", (50,   0), False, "name 4", "point 4"),
            (None,    (25,   0), False, None,     None),
            (None,    (0,   25), False, None,     None),
        ]
        self.assertEqual(pen.contours[-1]["points"], expected)
        self.assertEqual(pen.contours[-1]["identifier"], 'contour 1')

    def test_pen_with_lines_and_curves_strict(self):
        pen = MathGlyphPen(strict=True)
        pen.beginPath(identifier="contour 1")
        pen.addPoint((0,   50), "curve", smooth=False, name="name 1",
                     identifier="point 1")
        pen.addPoint((50, 100), "line",  smooth=False, name="name 2",
                     identifier="point 2")
        pen.addPoint((75, 100), None)
        pen.addPoint((100, 75), None)
        pen.addPoint((100, 50), "curve", smooth=True,  name="name 3",
                     identifier="point 3")
        pen.addPoint((100, 25), None)
        pen.addPoint((75,   0), None)
        pen.addPoint((50,   0), "curve", smooth=False, name="name 4",
                     identifier="point 4")
        pen.addPoint((25,   0), None)
        pen.addPoint((0,   25), None)
        pen.endPath()
        expected = [
            ("curve", (0,   50), False, "name 1", "point 1"),
            ("line", (50, 100), False, "name 2", "point 2"),
            (None,    (75, 100), False, None,     None),
            (None,    (100, 75), False, None,     None),
            ("curve", (100, 50), True, "name 3", "point 3"),
            (None,    (100, 25), False, None,     None),
            (None,    (75,   0), False, None,     None),
            ("curve", (50,   0), False, "name 4", "point 4"),
            (None,    (25,   0), False, None,     None),
            (None,    (0,   25), False, None,     None),
        ]
        self.assertEqual(pen.contours[-1]["points"], expected)
        self.assertEqual(pen.contours[-1]["identifier"], 'contour 1')


class _TestPointPen(AbstractPointPen):

    def __init__(self):
        self._text = []

    def dump(self):
        return "\n".join(self._text)

    def _prep(self, i):
        if isinstance(i, basestring):
            i = "\"%s\"" % i
        return str(i)

    def beginPath(self, identifier=None, **kwargs):
        self._text.append("beginPath(identifier=%s)" % self._prep(identifier))

    def addPoint(self, pt, segmentType=None, smooth=False, name=None,
                 identifier=None, **kwargs):
        self._text.append(
            "addPoint(%s, segmentType=%s, smooth=%s, name=%s, "
            "identifier=%s)" % (
                self._prep(pt),
                self._prep(segmentType),
                self._prep(smooth),
                self._prep(name),
                self._prep(identifier)
                )
        )

    def endPath(self):
        self._text.append("endPath()")

    def addComponent(self, baseGlyph, transformation, identifier=None,
                     **kwargs):
        self._text.append(
            "addComponent(baseGlyph=%s, transformation=%s, identifier=%s)" % (
                self._prep(baseGlyph),
                self._prep(transformation),
                self._prep(identifier)
                )
        )


class FilterRedundantPointPenTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)

    def test_flushContour(self):
        points = [
            ("curve", (0,   100), False, "name 1", "point 1"),
            (None,    (0,   100), False, None,     None),
            (None,    (100, 100), False, None,     None),
            ("curve", (100, 100), False, "name 2", "point 2"),
            (None,    (100, 100), False, None,     None),
            (None,    (100,   0), False, None,     None),
            ("curve", (100,   0), False, "name 3", "point 3"),
            (None,    (100,   0), False, None,     None),
            (None,    (0,     0), False, None,     None),
            ("curve", (0,     0), False, "name 4", "point 4"),
            (None,    (0,     0), False, None,     None),
            (None,    (0,   100), False, None,     None),
        ]
        testPen = _TestPointPen()
        filterPen = FilterRedundantPointPen(testPen)
        filterPen.beginPath(identifier="contour 1")
        for segmentType, pt, smooth, name, identifier in points:
            filterPen.addPoint(pt, segmentType=segmentType, smooth=smooth,
                               name=name, identifier=identifier)
        filterPen.endPath()
        self.assertEqual(
            testPen.dump(),
            'beginPath(identifier="contour 1")\n'
            'addPoint((0, 100), segmentType="line", smooth=False, '
            'name="name 1", identifier="point 1")\n'
            'addPoint((100, 100), segmentType="line", smooth=False, '
            'name="name 2", identifier="point 2")\n'
            'addPoint((100, 0), segmentType="line", smooth=False, '
            'name="name 3", identifier="point 3")\n'
            'addPoint((0, 0), segmentType="line", smooth=False, '
            'name="name 4", identifier="point 4")\n'
            'endPath()'
        )


class PrivateFuncsTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)

    def test_processMathOneContours(self):
        contours1 = [
            dict(identifier="contour 1",
                 points=[("line", (1, 3), False, "test", "1")])
        ]
        contours2 = [
            dict(identifier=None, points=[(None, (4, 6), True, None, None)])
        ]
        self.assertEqual(
            _processMathOneContours(contours1, contours2, addPt),
            [
                dict(identifier="contour 1",
                     points=[("line", (5, 9), False, "test", "1")])
            ]
        )

    def test_processMathTwoContours(self):
        contours = [
            dict(identifier="contour 1",
                 points=[("line", (1, 3), False, "test", "1")])
        ]
        self.assertEqual(
            _processMathTwoContours(contours, (2, 1.5), mulPt),
            [
                dict(identifier="contour 1",
                     points=[("line", (2, 4.5), False, "test", "1")])
            ]
        )
    True

    def test_anchorTree(self):
        anchors = [
            dict(identifier="1", name="test", x=1, y=2, color=None),
            dict(name="test", x=1, y=2, color=None),
            dict(name="test", x=3, y=4, color=None),
            dict(name="test", x=2, y=3, color=None),
            dict(name="c", x=1, y=2, color=None),
            dict(name="a", x=0, y=0, color=None),
        ]
        self.assertEqual(
            list(_anchorTree(anchors).items()),
            [
                ("test", [
                    ("1", 1, 2, None),
                    (None, 1, 2, None),
                    (None, 3, 4, None),
                    (None, 2, 3, None)
                ]),
                ("c", [
                    (None, 1, 2, None)
                ]),
                ("a", [
                    (None, 0, 0, None)
                ])
            ]
        )

    def test_pairAnchors_matching_identifiers(self):
        anchors1 = {
            "test": [
                (None, 1, 2, None),
                ("identifier 1", 3, 4, None)
            ]
        }
        anchors2 = {
            "test": [
                ("identifier 1", 1, 2, None),
                (None, 3, 4, None)
            ]
        }
        self.assertEqual(
            _pairAnchors(anchors1, anchors2),
            [
                (
                    dict(name="test", identifier=None, x=1, y=2, color=None),
                    dict(name="test", identifier=None, x=3, y=4, color=None)
                ),
                (
                    dict(name="test", identifier="identifier 1", x=3, y=4,
                         color=None),
                    dict(name="test", identifier="identifier 1", x=1, y=2,
                         color=None)
                )
            ]
        )

    def test_pairAnchors_mismatched_identifiers(self):
        anchors1 = {
            "test": [
                ("identifier 1", 3, 4, None)
            ]
        }
        anchors2 = {
            "test": [
                ("identifier 2", 1, 2, None),
            ]
        }
        self.assertEqual(
            _pairAnchors(anchors1, anchors2),
            [
                (
                    dict(name="test", identifier="identifier 1", x=3, y=4,
                         color=None),
                    dict(name="test", identifier="identifier 2", x=1, y=2,
                         color=None)
                )
            ]
        )

    def test_processMathOneAnchors(self):
        anchorPairs = [
            (
                dict(x=100, y=-100, name="foo", identifier="1",
                     color="0,0,0,0"),
                dict(x=200, y=-200, name="bar", identifier="2",
                     color="1,1,1,1")
            )
        ]
        self.assertEqual(
            _processMathOneAnchors(anchorPairs, addPt),
            [
                dict(x=300, y=-300, name="foo", identifier="1",
                     color="0,0,0,0")
            ]
        )

    def test_processMathTwoAnchors(self):
        anchors = [
            dict(x=100, y=-100, name="foo", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(
            _processMathTwoAnchors(anchors, (2, 1.5), mulPt),
            [
                dict(x=200, y=-150, name="foo", identifier="1",
                     color="0,0,0,0")
            ]
        )

    def test_pairComponents(self):
        components1 = [
            dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                 identifier="1"),
            dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                 identifier="1"),
            dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                 identifier=None)
        ]
        components2 = [
            dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                 identifier=None),
            dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                 identifier="1"),
            dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                 identifier="1")
        ]
        self.assertEqual(
            _pairComponents(components1, components2),
            [
                (
                    dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                         identifier="1"),
                    dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                         identifier="1")
                ),
                (
                    dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                         identifier="1"),
                    dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                         identifier="1")
                ),
                (
                    dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                         identifier=None),
                    dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                         identifier=None)
                ),
            ]
        )

        components1 = [
            dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                 identifier=None),
            dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                 identifier=None)
        ]
        components2 = [
            dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                 identifier=None),
            dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                 identifier=None)
        ]
        self.assertEqual(
            _pairComponents(components1, components2),
            [
                (
                    dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                         identifier=None),
                    dict(baseGlyph="A", transformation=(0, 0, 0, 0, 0, 0),
                         identifier=None)
                ),
                (
                    dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                         identifier=None),
                    dict(baseGlyph="B", transformation=(0, 0, 0, 0, 0, 0),
                         identifier=None)
                ),
            ]
        )

    def test_processMathOneComponents(self):
        components = [
            (
                dict(baseGlyph="A", transformation=(1,  3,  5,  7,  9, 11),
                     identifier="1"),
                dict(baseGlyph="A", transformation=(12, 14, 16, 18, 20, 22),
                     identifier=None)
            )
        ]
        self.assertEqual(
            _processMathOneComponents(components, addPt),
            [
                dict(baseGlyph="A", transformation=(13, 17, 21, 25, 29, 33),
                     identifier="1")
            ]
        )

    def test_processMathTwoComponents(self):
        components = [
            dict(baseGlyph="A", transformation=(1, 2, 3, 4, 5, 6), identifier="1")
        ]
        scaled_components = [
            dict(baseGlyph="A", transformation=(2, 4, 4.5, 6, 10, 9), identifier="1")
        ]
        self.assertEqual(
            _processMathTwoComponents(components, (2, 1.5), mulPt),
            scaled_components
        )
        self.assertEqual(
            _processMathTwoComponents(
                components, (2, 1.5), mulPt, scaleComponentTransform=True
            ),
            scaled_components
        )
        self.assertEqual(
            _processMathTwoComponents(
                components, (2, 1.5), mulPt, scaleComponentTransform=False
            ),
            [
                dict(
                    baseGlyph="A",
                    transformation=(1, 2, 3, 4, 10, 9),
                    identifier="1"
                )
            ],
        )

    def test_expandImage(self):
        self.assertEqual(
            _expandImage(None),
            dict(fileName=None, transformation=(1, 0, 0, 1, 0, 0), color=None)
        )
        self.assertEqual(
            _expandImage(dict(fileName="foo")),
            dict(fileName="foo", transformation=(1, 0, 0, 1, 0, 0), color=None)
        )

    def test_compressImage(self):
        self.assertEqual(
            _compressImage(
                dict(fileName="foo",
                     transformation=(1, 0, 0, 1, 0, 0), color=None)),
            dict(fileName="foo", color=None, xScale=1,
                 xyScale=0, yxScale=0, yScale=1, xOffset=0, yOffset=0)
        )

    def test_pairImages(self):
        image1 = dict(fileName="foo", transformation=(1, 0, 0, 1, 0, 0),
                      color=None)
        image2 = dict(fileName="foo", transformation=(2, 0, 0, 2, 0, 0),
                      color="0,0,0,0")
        self.assertEqual(
            _pairImages(image1, image2),
            (image1, image2)
        )

        image1 = dict(fileName="foo", transformation=(1, 0, 0, 1, 0, 0),
                      color=None)
        image2 = dict(fileName="bar", transformation=(1, 0, 0, 1, 0, 0),
                      color=None)
        self.assertEqual(
            _pairImages(image1, image2),
            ()
        )

    def test_processMathOneImage(self):
        image1 = dict(fileName="foo", transformation=(1,  3,  5,  7,  9, 11),
                      color="0,0,0,0")
        image2 = dict(fileName="bar", transformation=(12, 14, 16, 18, 20, 22),
                      color=None)
        self.assertEqual(
            _processMathOneImage((image1, image2), addPt),
            dict(fileName="foo", transformation=(13, 17, 21, 25, 29, 33),
                 color="0,0,0,0")
        )

    def test_processMathTwoImage(self):
        image = dict(fileName="foo", transformation=(1, 2, 3, 4, 5, 6),
                     color="0,0,0,0")
        self.assertEqual(
            _processMathTwoImage(image, (2, 1.5), mulPt),
            dict(fileName="foo", transformation=(2, 4, 4.5, 6, 10, 9),
                 color="0,0,0,0")
        )

    def test_processMathOneTransformation(self):
        transformation1 = (1,  3,  5,  7,  9, 11)
        transformation2 = (12, 14, 16, 18, 20, 22)
        self.assertEqual(
            _processMathOneTransformation(transformation1, transformation2,
                                          addPt),
            (13, 17, 21, 25, 29, 33)
        )

    def test_processMathTwoTransformation(self):
        transformation = (1, 2, 3, 4, 5, 6)
        self.assertEqual(
            _processMathTwoTransformation(transformation, (2, 1.5), mulPt),
            (2, 4, 4.5, 6, 10, 9)
        )
        self.assertEqual(
            _processMathTwoTransformation(transformation, (2, 1.5), mulPt, doScale=True),
            (2, 4, 4.5, 6, 10, 9)
        )
        self.assertEqual(
            _processMathTwoTransformation(transformation, (2, 1.5), mulPt, doScale=False),
            (1, 2, 3, 4, 10, 9)
        )

    def test_roundContours(self):
        contour = [
            dict(identifier="contour 1", points=[("line", (0.55, 3.1), False,
                 "test", "1")]),
            dict(identifier="contour 1", points=[("line", (0.55, 3.1), True,
                 "test", "1")])
        ]
        self.assertEqual(
            _roundContours(contour),
            [
                dict(identifier="contour 1", points=[("line", (1, 3), False,
                     "test", "1")]),
                dict(identifier="contour 1", points=[("line", (1, 3), True,
                     "test", "1")])
            ]
        )

    def test_roundTransformation(self):
        transformation = (1, 2, 3, 4, 4.99, 6.01)
        self.assertEqual(
            _roundTransformation(transformation),
            (1, 2, 3, 4, 5, 6)
        )

    def test_roundImage(self):
        image = dict(fileName="foo", transformation=(1, 2, 3, 4, 4.99, 6.01),
                     color="0,0,0,0")
        self.assertEqual(
            _roundImage(image),
            dict(fileName="foo", transformation=(1, 2, 3, 4, 5, 6),
                 color="0,0,0,0")
        )

    def test_roundComponents(self):
        components = [
            dict(baseGlyph="A", transformation=(1, 2, 3, 4, 5.1, 5.99),
                 identifier="1"),
        ]
        self.assertEqual(
            _roundComponents(components),
            [
                dict(baseGlyph="A", transformation=(1, 2, 3, 4, 5, 6),
                     identifier="1")
            ]
        )

    def test_roundAnchors(self):
        anchors = [
            dict(x=99.9, y=-100.1, name="foo", identifier="1",
                 color="0,0,0,0")
        ]
        self.assertEqual(
            _roundAnchors(anchors),
            [
                dict(x=100, y=-100, name="foo", identifier="1",
                     color="0,0,0,0")
            ]
        )

if __name__ == "__main__":
    unittest.main()
