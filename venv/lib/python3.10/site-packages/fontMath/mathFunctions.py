from __future__ import division
import math
import sys

__all__ = [
    "add",
    "addPt",
    "sub",
    "subPt",
    "mul",
    "mulPt",
    "div",
    "divPt",
    "factorAngle",
    "_roundNumber",
]

def add(v1, v2):
    return v1 + v2

def addPt(pt1, pt2):
    return pt1[0] + pt2[0], pt1[1] + pt2[1]

def sub(v1, v2):
    return v1 - v2

def subPt(pt1, pt2):
    return pt1[0] - pt2[0], pt1[1] - pt2[1]

def mul(v, f):
    return v * f

def mulPt(pt1, f):
    (f1, f2) = f
    return pt1[0] * f1, pt1[1] * f2

def div(v, f):
    return v / f

def divPt(pt, f):
    (f1, f2) = f
    return pt[0] / f1, pt[1] / f2

def factorAngle(angle, f, func):
    (f1, f2) = f
    # If both factors are equal, assume a scalar factor and scale the angle as such.
    if f1 == f2:
        return func(angle, f1)
    # Otherwise, scale x and y components separately.
    rangle = math.radians(angle)
    x = math.cos(rangle)
    y = math.sin(rangle)
    return math.degrees(
        math.atan2(
            func(y, f2), func(x, f1)
        )
    )


def round2(number, ndigits=None):
    """
    Implementation of Python 2 built-in round() function.
    Rounds a number to a given precision in decimal digits (default
    0 digits). The result is a floating point number. Values are rounded
    to the closest multiple of 10 to the power minus ndigits; if two
    multiples are equally close, rounding is done away from 0.
    ndigits may be negative.
    See Python 2 documentation:
    https://docs.python.org/2/library/functions.html?highlight=round#round

    This is taken from the to-be-deprecated py23 fuction of fonttools
    """
    import decimal as _decimal

    if ndigits is None:
        ndigits = 0

    if ndigits < 0:
        exponent = 10 ** (-ndigits)
        quotient, remainder = divmod(number, exponent)
        if remainder >= exponent // 2 and number >= 0:
            quotient += 1
        return float(quotient * exponent)
    else:
        exponent = _decimal.Decimal("10") ** (-ndigits)

        d = _decimal.Decimal.from_float(number).quantize(
            exponent, rounding=_decimal.ROUND_HALF_UP
        )

        return float(d)


def setRoundIntegerFunction(func):
    """ Globally set function for rounding floats to integers.

    The function signature must be:

        def func(value: float) -> int
    """
    global _ROUND_INTEGER_FUNC
    _ROUND_INTEGER_FUNC = func


def setRoundFloatFunction(func):
    """ Globally set function for rounding floats within given precision.

    The function signature must be:

        def func(value: float, ndigits: int) -> float
    """
    global _ROUND_FLOAT_FUNC
    _ROUND_FLOAT_FUNC = func


_ROUND_INTEGER_FUNC = round
_ROUND_FLOAT_FUNC = round


def _roundNumber(value, ndigits=None):
    """Round number using the Python 3 built-in round function.

    You can change the default rounding functions using setRoundIntegerFunction
    and/or setRoundFloatFunction.
    """
    if ndigits is not None:
        return _ROUND_FLOAT_FUNC(value, ndigits)
    return _ROUND_INTEGER_FUNC(value)


if __name__ == "__main__":
    import sys
    import doctest
    sys.exit(doctest.testmod().failed)
