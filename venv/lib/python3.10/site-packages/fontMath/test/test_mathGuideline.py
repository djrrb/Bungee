import unittest
from fontMath.mathFunctions import add, addPt, mul, _roundNumber
from fontMath.mathGuideline import (
    _expandGuideline, _compressGuideline, _pairGuidelines,
    _processMathOneGuidelines, _processMathTwoGuidelines, _roundGuidelines
)


class MathGuidelineTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)

    def test_expandGuideline(self):
        guideline = dict(x=100, y=None, angle=None)
        self.assertEqual(
            sorted(_expandGuideline(guideline).items()),
            [('angle', 90), ('x', 100), ('y', 0)]
        )

        guideline = dict(y=100, x=None, angle=None)
        self.assertEqual(
            sorted(_expandGuideline(guideline).items()),
            [('angle', 0), ('x', 0), ('y', 100)]
        )

    def test_compressGuideline(self):
        guideline = dict(x=100, y=0, angle=90)
        self.assertEqual(
            sorted(_compressGuideline(guideline).items()),
            [('angle', None), ('x', 100), ('y', None)]
        )

        guideline = dict(x=100, y=0, angle=270)
        self.assertEqual(
            sorted(_compressGuideline(guideline).items()),
            [('angle', None), ('x', 100), ('y', None)]
        )

        guideline = dict(y=100, x=0, angle=0)
        self.assertEqual(
            sorted(_compressGuideline(guideline).items()),
            [('angle', None), ('x', None), ('y', 100)]
        )

        guideline = dict(y=100, x=0, angle=180)
        self.assertEqual(
            sorted(_compressGuideline(guideline).items()),
            [('angle', None), ('x', None), ('y', 100)]
        )

    def test_pairGuidelines_name_identifier_x_y_angle(self):
        guidelines1 = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="foo", identifier="2", x=3, y=4, angle=2),
        ]
        guidelines2 = [
            dict(name="foo", identifier="2", x=3, y=4, angle=2),
            dict(name="foo", identifier="1", x=1, y=2, angle=1)
        ]
        expected = [
            (
                dict(name="foo", identifier="1", x=1, y=2, angle=1),
                dict(name="foo", identifier="1", x=1, y=2, angle=1)
            ),
            (
                dict(name="foo", identifier="2", x=3, y=4, angle=2),
                dict(name="foo", identifier="2", x=3, y=4, angle=2)
            )
        ]
        self.assertEqual(
            _pairGuidelines(guidelines1, guidelines2),
            expected
        )

    def test_pairGuidelines_name_identifier(self):
        guidelines1 = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="foo", identifier="2", x=1, y=2, angle=2),
        ]
        guidelines2 = [
            dict(name="foo", identifier="2", x=3, y=4, angle=3),
            dict(name="foo", identifier="1", x=3, y=4, angle=4)
        ]
        expected = [
            (
                dict(name="foo", identifier="1", x=1, y=2, angle=1),
                dict(name="foo", identifier="1", x=3, y=4, angle=4)
            ),
            (
                dict(name="foo", identifier="2", x=1, y=2, angle=2),
                dict(name="foo", identifier="2", x=3, y=4, angle=3)
            )
        ]
        self.assertEqual(
            _pairGuidelines(guidelines1, guidelines2),
            expected
        )

    def test_pairGuidelines_name_x_y_angle(self):
        guidelines1 = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="foo", identifier="2", x=3, y=4, angle=2),
        ]
        guidelines2 = [
            dict(name="foo", identifier="3", x=3, y=4, angle=2),
            dict(name="foo", identifier="4", x=1, y=2, angle=1)
        ]
        expected = [
            (
                dict(name="foo", identifier="1", x=1, y=2, angle=1),
                dict(name="foo", identifier="4", x=1, y=2, angle=1)
            ),
            (
                dict(name="foo", identifier="2", x=3, y=4, angle=2),
                dict(name="foo", identifier="3", x=3, y=4, angle=2)
            )
        ]
        self.assertEqual(
            _pairGuidelines(guidelines1, guidelines2),
            expected
        )

    def test_pairGuidelines_identifier_x_y_angle(self):
        guidelines1 = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="bar", identifier="2", x=3, y=4, angle=2),
        ]
        guidelines2 = [
            dict(name="xxx", identifier="2", x=3, y=4, angle=2),
            dict(name="yyy", identifier="1", x=1, y=2, angle=1)
        ]
        expected = [
            (
                dict(name="foo", identifier="1", x=1, y=2, angle=1),
                dict(name="yyy", identifier="1", x=1, y=2, angle=1)
            ),
            (
                dict(name="bar", identifier="2", x=3, y=4, angle=2),
                dict(name="xxx", identifier="2", x=3, y=4, angle=2)
            )
        ]
        self.assertEqual(
            _pairGuidelines(guidelines1, guidelines2),
            expected
        )

    def test_pairGuidelines_name(self):
        guidelines1 = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="bar", identifier="2", x=1, y=2, angle=2),
        ]
        guidelines2 = [
            dict(name="bar", identifier="3", x=3, y=4, angle=3),
            dict(name="foo", identifier="4", x=3, y=4, angle=4)
        ]
        expected = [
            (
                dict(name="foo", identifier="1", x=1, y=2, angle=1),
                dict(name="foo", identifier="4", x=3, y=4, angle=4)
            ),
            (
                dict(name="bar", identifier="2", x=1, y=2, angle=2),
                dict(name="bar", identifier="3", x=3, y=4, angle=3)
            )
        ]
        self.assertEqual(
            _pairGuidelines(guidelines1, guidelines2),
            expected
        )

    def test_pairGuidelines_identifier(self):
        guidelines1 = [
            dict(name="foo", identifier="1", x=1, y=2, angle=1),
            dict(name="bar", identifier="2", x=1, y=2, angle=2),
        ]
        guidelines2 = [
            dict(name="xxx", identifier="2", x=3, y=4, angle=3),
            dict(name="yyy", identifier="1", x=3, y=4, angle=4)
        ]
        expected = [
            (
                dict(name="foo", identifier="1", x=1, y=2, angle=1),
                dict(name="yyy", identifier="1", x=3, y=4, angle=4)
            ),
            (
                dict(name="bar", identifier="2", x=1, y=2, angle=2),
                dict(name="xxx", identifier="2", x=3, y=4, angle=3)
            )
        ]
        self.assertEqual(
            _pairGuidelines(guidelines1, guidelines2),
            expected
        )

    def test_processMathOneGuidelines(self):
        guidelines = [
            (
                dict(x=1, y=3, angle=5, name="test", identifier="1", color="0,0,0,0"),
                dict(x=6, y=8, angle=10, name=None, identifier=None, color=None)
            )
        ]
        expected = [
            dict(x=7, y=11, angle=15, name="test", identifier="1", color="0,0,0,0")
        ]
        self.assertEqual(
            _processMathOneGuidelines(guidelines, addPt, add),
            expected
        )

    def test_processMathTwoGuidelines(self):
        guidelines = [
            dict(x=2, y=3, angle=5, name="test", identifier="1", color="0,0,0,0")
        ]
        expected = [
            dict(x=4, y=4.5, angle=3.75, name="test", identifier="1", color="0,0,0,0")
        ]
        result = _processMathTwoGuidelines(guidelines, (2, 1.5), mul)
        result[0]["angle"] = _roundNumber(result[0]["angle"], 2)
        self.assertEqual(result, expected)

    def test_roundGuidelines(self):
        guidelines = [
            dict(x=1.99, y=3.01, angle=5, name="test", identifier="1", color="0,0,0,0")
        ]
        expected = [
            dict(x=2, y=3, angle=5, name="test", identifier="1", color="0,0,0,0")
        ]
        result = _roundGuidelines(guidelines)
        self.assertEqual(result, expected)
