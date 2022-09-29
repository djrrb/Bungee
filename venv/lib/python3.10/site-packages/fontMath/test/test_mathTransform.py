import unittest
import math
from random import random
from fontMath.mathFunctions import _roundNumber
from fontMath.mathTransform import (
    Transform, FontMathWarning, matrixToMathTransform, mathTransformToMatrix,
    _polarDecomposeInterpolationTransformation,
    _mathPolarDecomposeInterpolationTransformation,
    _linearInterpolationTransformMatrix
)


class MathTransformToFunctionsTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)

    def test_matrixToTransform(self):
        pass

    def test_TransformToMatrix(self):
        pass


class ShallowTransformTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)


_testData = [
    (
        Transform().rotate(math.radians(0)),
        Transform().rotate(math.radians(90))
    ),

    (
        Transform().skew(math.radians(60), math.radians(10)),
        Transform().rotate(math.radians(90))
    ),

    (
        Transform().scale(.3, 1.3),
        Transform().rotate(math.radians(90))
    ),

    (
        Transform().scale(.3, 1.3).rotate(math.radians(-15)),
        Transform().rotate(math.radians(90)).scale(.7, .3)
    ),

    (
        Transform().translate(250, 250).rotate(math.radians(-15))
        .translate(-250, -250),
        Transform().translate(0, 400).rotate(math.radians(80))
        .translate(-100, 0).rotate(math.radians(80)),
    ),

    (
        Transform().skew(math.radians(50)).scale(1.5).rotate(math.radians(60)),
        Transform().rotate(math.radians(90))
    ),
]


class MathTransformTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)
        # Python 3 renamed assertRaisesRegexp to assertRaisesRegex,
        # and fires deprecation warnings if a program uses the old name.
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    # Disabling this test as it fails intermittently and it's not clear what it
    # does (cf. https://github.com/typesupply/fontMath/issues/35)
    #
    # def test_functions(self):
    #     """
    #     In this test various complex transformations are interpolated using
    #     3 different methods:
    #       - straight linear interpolation, the way glyphMath does it now.
    #       - using the MathTransform interpolation method.
    #       - using the ShallowTransform with an initial decompose and final
    #         compose.
    #     """
    #     value = random()
    #     testFunctions = [
    #         _polarDecomposeInterpolationTransformation,
    #         _mathPolarDecomposeInterpolationTransformation,
    #         _linearInterpolationTransformMatrix,
    #     ]
    #     with self.assertRaisesRegex(
    #             FontMathWarning,
    #             "Minor differences occured when "
    #             "comparing the interpolation functions."):
    #         for i, m in enumerate(_testData):
    #             m1, m2 = m
    #             results = []
    #             for func in testFunctions:
    #                 r = func(m1, m2, value)
    #                 results.append(r)
    #             if not results[0] == results[1]:
    #                 raise FontMathWarning(
    #                     "Minor differences occured when "
    #                     "comparing the interpolation functions.")

    def _wrapUnWrap(self, precision=12):
        """
        Wrap and unwrap a matrix with random values to establish rounding error
        """
        t1 = []
        for i in range(6):
            t1.append(random())
        m = matrixToMathTransform(t1)
        t2 = mathTransformToMatrix(m)

        if not sum([_roundNumber(t1[i] - t2[i], precision)
                    for i in range(len(t1))]) == 0:
            raise FontMathWarning(
                "Matrix round-tripping failed for precision value %s."
                % (precision))

    def test_wrapUnWrap(self):
        self._wrapUnWrap()

    def test_wrapUnWrapPrecision(self):
        """
        Wrap and unwrap should have no rounding errors at least up to
        a precision value of 12.
        Rounding errors seem to start occuring at a precision value of 14.
        """
        for p in range(5, 13):
            for i in range(1000):
                self._wrapUnWrap(p)
        with self.assertRaisesRegex(
                FontMathWarning,
                "Matrix round-tripping failed for precision value"):
            for p in range(14, 16):
                for i in range(1000):
                    self._wrapUnWrap(p)
