import unittest
from fontMath.mathFunctions import _roundNumber
from fontMath.mathInfo import MathInfo, _numberListAttrs


class MathInfoTest(unittest.TestCase):

    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)
        self.maxDiff = None

    def test_add(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = MathInfo(_TestInfoObject())
        info3 = info1 + info2
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info3, attr)
            if isinstance(value, list):
                expectedValue = [v + v for v in value]
            else:
                expectedValue = value + value
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected.items()), sorted(written.items()))

    def test_add_data_subset_1st_operand(self):
        info1 = MathInfo(_TestInfoObject(_testDataSubset))
        info2 = MathInfo(_TestInfoObject())
        info3 = info1 + info2
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info3, attr)
            if isinstance(value, list):
                expectedValue = [v + v for v in value]
            else:
                expectedValue = value + value
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected), sorted(written))
        # self.assertEqual(sorted(expected.items()), sorted(written.items()))

    def test_add_data_subset_2nd_operand(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = MathInfo(_TestInfoObject(_testDataSubset))
        info3 = info1 + info2
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info3, attr)
            if isinstance(value, list):
                expectedValue = [v + v for v in value]
            else:
                expectedValue = value + value
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected), sorted(written))
        # self.assertEqual(sorted(expected.items()), sorted(written.items()))

    def test_sub(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = MathInfo(_TestInfoObject())
        info3 = info1 - info2
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info3, attr)
            if isinstance(value, list):
                expectedValue = [v - v for v in value]
            else:
                expectedValue = value - value
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected.items()), sorted(written.items()))

    def test_mul(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = info1 * 2.5
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info2, attr)
            if isinstance(value, list):
                expectedValue = [v * 2.5 for v in value]
            else:
                expectedValue = value * 2.5
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected.items()), sorted(written.items()))

    def test_angle(self):
        info1 = MathInfo(_TestInfoObject())
        info1.italicAngle = 10

        info2 = info1 - info1
        self.assertEqual(info2.italicAngle, 0)
        info2 = info1 + info1 + info1
        self.assertEqual(info2.italicAngle, 30)
        info2 = 10 * info1
        self.assertEqual(info2.italicAngle, 100)
        info2 = info1 / 20 
        self.assertEqual(info2.italicAngle, 0.5)

        info2 = info1 * 2.5
        self.assertEqual(info2.italicAngle, 25)
        info2 = info1 * (2.5, 2.5)
        self.assertEqual(info2.italicAngle, 25)
        info2 = info1 * (2.5, 5)
        self.assertEqual(round(info2.italicAngle), 19)

    def test_mul_data_subset(self):
        info1 = MathInfo(_TestInfoObject(_testDataSubset))
        info2 = info1 * 2.5
        written = {}
        expected = {}
        for attr, value in _testDataSubset.items():
            if value is None:
                continue
            written[attr] = getattr(info2, attr)
        expected = {"descender": -500.0,
                    "guidelines": [{"y": 250.0, "x": 0.0, "identifier": "2",
                                    "angle": 0.0, "name": "bar"}],
                    "postscriptBlueValues": [-25.0, 0.0, 1000.0, 1025.0, 1625.0],
                    "unitsPerEm": 2500.0}
        self.assertEqual(sorted(expected.items()), sorted(written.items()))

    def test_div(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = info1 / 2
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info2, attr)
            if isinstance(value, list):
                expectedValue = [v / 2 for v in value]
            else:
                expectedValue = value / 2
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected), sorted(written))

    def test_compare_same(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = MathInfo(_TestInfoObject())
        self.assertFalse(info1 < info2)
        self.assertFalse(info1 > info2)
        self.assertEqual(info1, info2)

    def test_compare_different(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = MathInfo(_TestInfoObject())
        info2.ascender = info2.ascender - 1
        self.assertFalse(info1 < info2)
        self.assertTrue(info1 > info2)
        self.assertNotEqual(info1, info2)

    def test_weight_name(self):
        info1 = MathInfo(_TestInfoObject())
        info2 = MathInfo(_TestInfoObject())
        info2.openTypeOS2WeightClass = 0
        info3 = info1 + info2
        self.assertEqual(info3.openTypeOS2WeightClass, 500)
        self.assertEqual(info3.postscriptWeightName, "Medium")
        info2.openTypeOS2WeightClass = 49
        info3 = info1 + info2
        self.assertEqual(info3.openTypeOS2WeightClass, 549)
        self.assertEqual(info3.postscriptWeightName, "Medium")
        info2.openTypeOS2WeightClass = 50
        info3 = info1 + info2
        self.assertEqual(info3.openTypeOS2WeightClass, 550)
        self.assertEqual(info3.postscriptWeightName, "Semi-bold")
        info2.openTypeOS2WeightClass = 50
        info3 = info1 - info2
        self.assertEqual(info3.openTypeOS2WeightClass, 450)
        self.assertEqual(info3.postscriptWeightName, "Medium")
        info2.openTypeOS2WeightClass = 51
        info3 = info1 - info2
        self.assertEqual(info3.openTypeOS2WeightClass, 449)
        self.assertEqual(info3.postscriptWeightName, "Normal")
        info2.openTypeOS2WeightClass = 500
        info3 = info1 - info2
        self.assertEqual(info3.openTypeOS2WeightClass, 0)
        self.assertEqual(info3.postscriptWeightName, "Thin")
        info2.openTypeOS2WeightClass = 1500
        info3 = info1 - info2
        self.assertEqual(info3.openTypeOS2WeightClass, -1000)
        self.assertEqual(info3.postscriptWeightName, "Thin")
        info2.openTypeOS2WeightClass = 500
        info3 = info1 + info2
        self.assertEqual(info3.openTypeOS2WeightClass, 1000)
        self.assertEqual(info3.postscriptWeightName, "Black")

    def test_round(self):
        m = _TestInfoObject()
        m.ascender = 699.99
        m.descender = -199.99
        m.xHeight = 399.66
        m.postscriptSlantAngle = None
        m.postscriptStemSnapH = [80.1, 90.2]
        m.guidelines = [{'y': 100.99, 'x': None, 'angle': None, 'name': 'bar'}]
        m.italicAngle = -9.4
        m.postscriptBlueScale = 0.137
        info = MathInfo(m)
        info = info.round()
        self.assertEqual(info.ascender, 700)
        self.assertEqual(info.descender, -200)
        self.assertEqual(info.xHeight, 400)
        self.assertEqual(m.italicAngle, -9.4)
        self.assertEqual(m.postscriptBlueScale, 0.137)
        self.assertIsNone(info.postscriptSlantAngle)
        self.assertEqual(info.postscriptStemSnapH, [80, 90])
        self.assertEqual(
            [sorted(gl.items()) for gl in info.guidelines],
            [[('angle', 0), ('name', 'bar'), ('x', 0), ('y', 101)]]
        )
        written = {}
        expected = {}
        for attr, value in _testData.items():
            if value is None:
                continue
            written[attr] = getattr(info, attr)
            if isinstance(value, list):
                expectedValue = [_roundNumber(v) for v in value]
            else:
                expectedValue = _roundNumber(value)
            expected[attr] = expectedValue
        self.assertEqual(sorted(expected), sorted(written))

    def test_sub_undefined_number_list_sets_None(self):
        self.assertIn("postscriptBlueValues", _numberListAttrs)

        info1 = _TestInfoObject()
        info1.postscriptBlueValues = None
        m1 = MathInfo(info1)

        info2 = _TestInfoObject()
        info2.postscriptBlueValues = [1, 2, 3]
        m2 = MathInfo(info2)

        m3 = m2 - m1

        self.assertIsNone(m3.postscriptBlueValues)

        m4 = m1 - m2

        self.assertIsNone(m4.postscriptBlueValues)

    def test_number_lists_with_different_lengths(self):
        self.assertIn("postscriptBlueValues", _numberListAttrs)

        info1 = _TestInfoObject()
        info1.postscriptBlueValues = [1, 2]
        m1 = MathInfo(info1)

        info2 = _TestInfoObject()
        info2.postscriptBlueValues = [1, 2, 3]
        m2 = MathInfo(info2)

        m3 = m2 - m1

        self.assertIsNone(m3.postscriptBlueValues)

        m4 = m1 - m2

        self.assertIsNone(m4.postscriptBlueValues)

        m5 = m1 + m2

        self.assertIsNone(m5.postscriptBlueValues)


# ----
# Test Data
# ----

_testData = dict(
    # generic
    unitsPerEm=1000,
    descender=-200,
    xHeight=400,
    capHeight=650,
    ascender=700,
    italicAngle=5,
    # head
    openTypeHeadLowestRecPPEM=5,
    # hhea
    openTypeHheaAscender=700,
    openTypeHheaDescender=-200,
    openTypeHheaLineGap=200,
    openTypeHheaCaretSlopeRise=1,
    openTypeHheaCaretSlopeRun=1,
    openTypeHheaCaretOffset=1,
    # OS/2
    openTypeOS2WidthClass=5,
    openTypeOS2WeightClass=500,
    openTypeOS2TypoAscender=700,
    openTypeOS2TypoDescender=-200,
    openTypeOS2TypoLineGap=200,
    openTypeOS2WinAscent=700,
    openTypeOS2WinDescent=-200,
    openTypeOS2SubscriptXSize=300,
    openTypeOS2SubscriptYSize=300,
    openTypeOS2SubscriptXOffset=0,
    openTypeOS2SubscriptYOffset=-200,
    openTypeOS2SuperscriptXSize=300,
    openTypeOS2SuperscriptYSize=300,
    openTypeOS2SuperscriptXOffset=0,
    openTypeOS2SuperscriptYOffset=500,
    openTypeOS2StrikeoutSize=50,
    openTypeOS2StrikeoutPosition=300,
    # Vhea
    openTypeVheaVertTypoAscender=700,
    openTypeVheaVertTypoDescender=-200,
    openTypeVheaVertTypoLineGap=200,
    openTypeVheaCaretSlopeRise=1,
    openTypeVheaCaretSlopeRun=1,
    openTypeVheaCaretOffset=1,
    # postscript
    postscriptSlantAngle=-5,
    postscriptUnderlineThickness=100,
    postscriptUnderlinePosition=-150,
    postscriptBlueValues=[-10, 0, 400, 410, 650, 660, 700, 710],
    postscriptOtherBlues=[-210, -200],
    postscriptFamilyBlues=[-10, 0, 400, 410, 650, 660, 700, 710],
    postscriptFamilyOtherBlues=[-210, -200],
    postscriptStemSnapH=[80, 90],
    postscriptStemSnapV=[110, 130],
    postscriptBlueFuzz=1,
    postscriptBlueShift=7,
    postscriptBlueScale=0.039625,
    postscriptDefaultWidthX=400,
    postscriptNominalWidthX=400,
    # guidelines
    guidelines=None
)

_testDataSubset = dict(
    # generic
    unitsPerEm=1000,
    descender=-200,
    xHeight=None,
    # postscript
    postscriptBlueValues=[-10, 0, 400, 410, 650],
    # guidelines
    guidelines=[
        {'y': 100, 'x': None, 'angle': None, 'name': 'bar', 'identifier': '2'}
    ]
)


class _TestInfoObject(object):

    def __init__(self, data=_testData):
        for attr, value in data.items():
            setattr(self, attr, value)

if __name__ == "__main__":
    unittest.main()
