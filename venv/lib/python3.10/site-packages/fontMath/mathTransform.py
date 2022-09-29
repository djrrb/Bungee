from __future__ import print_function
import math
from fontTools.misc.transform import Transform

"""

    This is a more sophisticated approach to performing math on transformation matrices.
    Traditionally glyphMath applies the math straight to the elements in the matrix.
    By decomposing the matrix into offset, scale and rotation factors, the interpoations
    are much more natural. Or more intuitive.

    This could help in complex glyphs in which the rotation of a component plays am important role.

    This MathTransform object itself has its own interpolation method. But in order to be able
    to participate in (for instance) superpolator math, it is necessary to keep the
    offset, scale and rotation decomposed for more than one math operation.
    So, MathTransform decomposes the matrix, ShallowTransform carries it through the math,
    then MathTransform is used again to compose the new matrix. If you don't need to math with
    the transformation object itself, the MathTransform object is fine.

    MathTransform by Frederik Berlaen

    Transformation decomposition algorithm from
        http://dojotoolkit.org/reference-guide/1.9/dojox/gfx.html#decompose-js
        http://dojotoolkit.org/license


"""

def matrixToMathTransform(matrix):
    """ Take a 6-tuple and return a ShallowTransform object."""
    if isinstance(matrix, ShallowTransform):
        return matrix
    off, scl, rot = MathTransform(matrix).decompose()
    return ShallowTransform(off, scl, rot)

def mathTransformToMatrix(mathTransform):
    """ Take a ShallowTransform object and return a 6-tuple. """
    m = MathTransform().compose(mathTransform.offset, mathTransform.scale, mathTransform.rotation)
    return tuple(m)

class ShallowTransform(object):
    """ A shallow math container for offset, scale and rotation. """
    def __init__(self, offset, scale, rotation):
        self.offset = offset
        self.scale = scale
        self.rotation = rotation

    def __repr__(self):
        return "<ShallowTransform offset(%3.3f,%3.3f) scale(%3.3f,%3.3f) rotation(%3.3f,%3.3f)>"%(self.offset[0], self.offset[1], self.scale[0], self.scale[1], self.rotation[0], self.rotation[1])

    def __add__(self, other):
        newOffset = self.offset[0]+other.offset[0],self.offset[1]+other.offset[1]
        newScale = self.scale[0]+other.scale[0],self.scale[1]+other.scale[1]
        newRotation = self.rotation[0]+other.rotation[0],self.rotation[1]+other.rotation[1]
        return self.__class__(newOffset, newScale, newRotation)

    def __sub__(self, other):
        newOffset = self.offset[0]-other.offset[0],self.offset[1]-other.offset[1]
        newScale = self.scale[0]-other.scale[0],self.scale[1]-other.scale[1]

        newRotation = self.rotation[0]-other.rotation[0],self.rotation[1]-other.rotation[1]
        return self.__class__(newOffset, newScale, newRotation)

    def __mul__(self, factor):
        if isinstance(factor, (int, float)):
            fx = fy = float(factor)
        else:
            fx, fy = float(factor[0]), float(factor[1])
        newOffset = self.offset[0]*fx,self.offset[1]*fy
        newScale = self.scale[0]*fx,self.scale[1]*fy
        newRotation = self.rotation[0]*fx,self.rotation[1]*fy
        return self.__class__(newOffset, newScale, newRotation)

    __rmul__ = __mul__

    def __truediv__(self, factor):
        """ XXX why not __div__ ?"""
        if isinstance(factor, (int, float)):
            fx = fy = float(factor)
        else:
            fx, fy = float(factor)
        if fx==0 or fy==0:
            raise ZeroDivisionError((fx, fy))
        newOffset = self.offset[0]/fx,self.offset[1]/fy
        newScale = self.scale[0]/fx,self.scale[1]/fy
        newRotation = self.rotation[0]/fx,self.rotation[1]/fy
        return self.__class__(newOffset, newScale, newRotation)

    def asTuple(self):
        m = MathTransform().compose(self.offset, self.scale, self.rotation)
        return tuple(m)



class MathTransform(object):
    """ A Transform object that can compose and decompose the matrix into offset, scale and rotation."""
    transformClass = Transform

    def __init__(self, *matrixes):
        matrix = self.transformClass()
        if matrixes:
            if isinstance(matrixes[0], (int, float)):
                matrixes = [matrixes]
            for m in matrixes:
                matrix = matrix.transform(m)
        self.matrix = matrix

    def _get_matrix(self):
        return (self.xx, self.xy, self.yx, self.yy, self.dx, self.dy)

    def _set_matrix(self, matrix):
        self.xx, self.xy, self.yx, self.yy, self.dx, self.dy = matrix

    matrix = property(_get_matrix, _set_matrix)

    def __repr__(self):
        return "< %.8f %.8f %.8f %.8f %.8f %.8f >" % (self.xx, self.xy, self.yx, self.yy, self.dx, self.dy)

    def __len__(self):
        return 6

    def __getitem__(self, index):
        return self.matrix[index]

    def __getslice__(self, i, j):
        return self.matrix[i:j]

    def __eq__(self, other):
        return str(self) == str(other)

    ## transformations

    def translate(self, x=0, y=0):
        return self.__class__(self.transformClass(*self.matrix).translate(x, y))

    def scale(self, x=1, y=None):
        return self.__class__(self.transformClass(*self.matrix).scale(x, y))

    def rotate(self, angle):
        return self.__class__(self.transformClass(*self.matrix).rotate(angle))

    def rotateDegrees(self, angle):
        return self.rotate(math.radians(angle))

    def skew(self, x=0, y=0):
        return self.__class__(self.transformClass(*self.matrix).skew(x, y))

    def skewDegrees(self, x=0, y=0):
        return self.skew(math.radians(x), math.radians(y))

    def transform(self, other):
        return self.__class__(self.transformClass(*self.matrix).transform(other))

    def reverseTransform(self, other):
        return self.__class__(self.transformClass(*self.matrix).reverseTransform(other))

    def inverse(self):
        return self.__class__(self.transformClass(*self.matrix).inverse())

    def copy(self):
        return self.__class__(self.matrix)
    ## tools

    def scaleSign(self):
        if self.xx * self.yy < 0 or self.xy * self.yx > 0:
            return -1
        return 1

    def eq(self, a, b):
        return abs(a - b) <= 1e-6 * (abs(a) + abs(b))

    def calcFromValues(self, r1, m1, r2, m2):
        m1 = abs(m1)
        m2 = abs(m2)
        return (m1 * r1 + m2 * r2) / (m1 + m2)

    def transpose(self):
        return self.__class__(self.xx, self.yx, self.xy, self.yy, 0, 0)

    def decompose(self):
        self.translateX = self.dx
        self.translateY = self.dy
        self.scaleX = 1
        self.scaleY = 1
        self.angle1 = 0
        self.angle2 = 0

        if self.eq(self.xy, 0) and self.eq(self.yx, 0):
            self.scaleX = self.xx
            self.scaleY = self.yy

        elif self.eq(self.xx * self.yx, -self.xy * self.yy):
            self._decomposeScaleRotate()

        elif self.eq(self.xx * self.xy, -self.yx * self.yy):
            self._decomposeRotateScale()

        else:
            transpose = self.transpose()
            (vx1, vy1), (vx2, vy2) = self._eigenvalueDecomposition(self.matrix, transpose.matrix)
            u = self.__class__(vx1, vx2, vy1, vy2, 0, 0)

            (vx1, vy1), (vx2, vy2) = self._eigenvalueDecomposition(transpose.matrix, self.matrix)
            vt = self.__class__(vx1, vy1, vx2, vy2, 0, 0)

            s = self.__class__(self.__class__().reverseTransform(u), self, self.__class__().reverseTransform(vt))

            vt._decomposeScaleRotate()
            self.angle1 = -vt.angle2

            u._decomposeRotateScale()
            self.angle2 = -u.angle1

            self.scaleX = s.xx * vt.scaleX * u.scaleX
            self.scaleY = s.yy * vt.scaleY * u.scaleY

        return (self.translateX, self.translateY), (self.scaleX, self.scaleY), (self.angle1, self.angle2)

    def _decomposeScaleRotate(self):
        sign = self.scaleSign()
        a = (math.atan2(self.yx, self.yy) + math.atan2(-sign * self.xy, sign * self.xx)) * .5
        c = math.cos(a)
        s = math.sin(a)
        if c == 0: ## ????
            c = 0.0000000000000000000000000000000001
        if s == 0:
            s = 0.0000000000000000000000000000000001
        self.angle2 = -a
        self.scaleX = self.calcFromValues(self.xx / float(c), c, -self.xy / float(s), s)
        self.scaleY = self.calcFromValues(self.yy / float(c), c,  self.yx / float(s), s)

    def _decomposeRotateScale(self):
        sign = self.scaleSign()
        a = (math.atan2(sign * self.yx, sign * self.xx) + math.atan2(-self.xy, self.yy)) * .5
        c = math.cos(a)
        s = math.sin(a)
        if c == 0:
            c = 0.0000000000000000000000000000000001
        if s == 0:
            s = 0.0000000000000000000000000000000001
        self.angle1 = -a
        self.scaleX = self.calcFromValues(self.xx / float(c), c,  self.yx / float(s), s)
        self.scaleY = self.calcFromValues(self.yy / float(c), c, -self.xy / float(s), s)

    def _eigenvalueDecomposition(self, *matrixes):
        m = self.__class__(*matrixes)
        b = -m.xx - m.yy
        c = m.xx * m.yy - m.xy * m.yx
        d = math.sqrt(abs(b * b - 4 * c))
        if b < 0:
            d *= -1
        l1 = -(b + d) * .5
        l2 = c / float(l1)

        vx1 = vy2 = None
        if l1 - m.xx != 0:
            vx1 = m.xy / (l1 - m.xx)
            vy1 = 1
        elif m.xy != 0:
            vx1 = 1
            vy1 = (l1 - m.xx) / m.xy
        elif m.yx != 0:
            vx1 = (l1 - m.yy) / m.yx
            vy1 = 1
        elif l1 - m.yy != 0:
            vx1 = 1
            vy1 = m.yx / (l1 - m.yy)

        vx2 = vy2 = None
        if l2 - m.xx != 0:
            vx2 = m.xy / (l2 - m.xx)
            vy2 = 1
        elif m.xy != 0:
            vx2 = 1
            vy2 = (l2 - m.xx) / m.xy
        elif m.yx != 0:
            vx2 = (l2 - m.yy) / m.yx
            vy2 = 1
        elif l2 - m.yy != 0:
            vx2 = 1
            vy2 = m.yx / (l2 - m.yy)


        if self.eq(l1, l2):
            vx1 = 1
            vy1 = 0
            vx2 = 0
            vy2 = 1

        d1 = math.sqrt(vx1 * vx1 + vy1 * vy1)
        d2 = math.sqrt(vx2 * vx2 + vy2 * vy2)

        vx1 /= d1
        vy1 /= d1
        vx2 /= d2
        vy2 /= d2

        return (vx1, vy1), (vx2, vy2)

    def compose(self, translate, scale, angle):
        translateX, translateY = translate
        scaleX, scaleY = scale
        angle1, angle2 = angle
        matrix = self.transformClass()
        matrix = matrix.translate(translateX, translateY)
        matrix = matrix.rotate(angle2)
        matrix = matrix.scale(scaleX, scaleY)
        matrix = matrix.rotate(angle1)
        return self.__class__(matrix)

    def _interpolate(self, v1, v2, value):
        return v1 * (1 - value) + v2 * value

    def interpolate(self, other, value):
        if isinstance(value, (int, float)):
            x = y = value
        else:
            x, y = value

        self.decompose()
        other.decompose()

        translateX = self._interpolate(self.translateX, other.translateX, x)
        translateY = self._interpolate(self.translateY, other.translateY, y)
        scaleX = self._interpolate(self.scaleX, other.scaleX, x)
        scaleY = self._interpolate(self.scaleY, other.scaleY, y)
        angle1 = self._interpolate(self.angle1, other.angle1, x)
        angle2 = self._interpolate(self.angle2, other.angle2, y)
        return self.compose((translateX, translateY), (scaleX, scaleY), (angle1, angle2))


class FontMathWarning(Exception): pass

def _interpolateValue(data1, data2, value):
    return data1 * (1 - value) + data2 * value

def _linearInterpolationTransformMatrix(matrix1, matrix2, value):
    """ Linear, 'oldstyle' interpolation of the transform matrix."""
    return tuple(_interpolateValue(matrix1[i], matrix2[i], value) for i in range(len(matrix1)))

def _polarDecomposeInterpolationTransformation(matrix1, matrix2, value):
    """ Interpolate using the MathTransform method. """
    m1 = MathTransform(matrix1)
    m2 = MathTransform(matrix2)
    return tuple(m1.interpolate(m2, value))

def _mathPolarDecomposeInterpolationTransformation(matrix1, matrix2, value):
    """ Interpolation with ShallowTransfor, wrapped by decompose / compose actions."""
    off, scl, rot = MathTransform(matrix1).decompose()
    m1 = ShallowTransform(off, scl, rot)
    off, scl, rot = MathTransform(matrix2).decompose()
    m2 = ShallowTransform(off, scl, rot)
    m3 = m1 + value * (m2-m1)
    m3 = MathTransform().compose(m3.offset, m3.scale, m3.rotation)
    return tuple(m3)


if __name__ == "__main__":
    from random import random
    import sys
    import doctest
    sys.exit(doctest.testmod().failed)
