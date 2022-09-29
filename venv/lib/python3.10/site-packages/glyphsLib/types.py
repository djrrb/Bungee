# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import re
import datetime
import copy
import binascii

__all__ = [
    "Transform",
    "Point",
    "Rect",
    "Size",
    "ValueType",
    "parse_datetime",
    "parse_color",
    "floatToString3",
    "floatToString5",
    "readIntlist",
    "UnicodesList",
    "BinaryData",
    "parse_float_or_int",
]


def parse_float_or_int(value_string):
    v = float(value_string)
    if v.is_integer():
        return int(v)
    return v


class ValueType:
    """A base class for value types that are comparable in the Python sense
    and readable/writable using the glyphsLib parser/writer.
    """

    default = None

    def __init__(self, value=None):
        if value:
            self.value = self.fromString(value)
        else:
            self.value = copy.deepcopy(self.default)

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.plistValue())

    def fromString(self, src):
        """Return a typed value representing the structured glyphs strings."""
        raise NotImplementedError("%s read" % type(self).__name__)

    def plistValue(self, format_version=2):
        """Return structured glyphs strings representing the typed value."""
        raise NotImplementedError("%s write" % type(self).__name__)

    # https://stackoverflow.com/questions/390250/
    # elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(self, other.__class__):
            return self.value == other.value
        return NotImplemented

    def __hash__(self):
        """Overrides the default implementation"""
        return hash(self.value)


# class Vector<dimension>
def Vector(dim):
    class Vector(ValueType):
        """Base type for number vectors (points, rects, transform matrices)."""

        dimension = dim
        default = [0.0] * dimension
        regex = re.compile("[({]%s[})]" % ", ".join(["([-.e\\d]+)"] * dimension))

        def fromString(self, src):
            if isinstance(src, list):
                assert len(src) == self.dimension
                return src
            src = src.replace('"', "")
            return [parse_float_or_int(i) for i in self.regex.match(src).groups()]

        def plistValue(self, format_version=2):
            assert isinstance(self.value, list) and len(self.value) == self.dimension
            if format_version == 2:
                return '"{%s}"' % (", ".join(floatToString3(v) for v in self.value))
            else:
                return "(%s)" % (",".join(floatToString3(v) for v in self.value))

        def __getitem__(self, key):
            assert isinstance(self.value, list) and len(self.value) == self.dimension
            return self.value[key]

        def __setitem__(self, key, value):
            assert isinstance(self.value, list) and len(self.value) == self.dimension
            self.value[key] = value

        def __len__(self):
            return self.dimension

    return Vector


class Point(Vector(2)):
    """Read/write a vector in curly braces."""

    __slots__ = ("value", "rect")

    def __init__(self, value=None, value2=None, rect=None):
        self.rect = rect

        # Invoked like Point(100, 200) or Point(value=100, value2=200).
        if value is not None and value2 is not None:
            self.value = [value, value2]
        # Invoked like Point("{800, 10}").
        elif isinstance(value, str):
            self.value = self.fromString(value)
        # Invoked like Point([100, 200]).
        elif isinstance(value, (list, tuple)):
            self.value = value
        # 🤷
        else:
            raise TypeError(
                "Point must be constructed with two ints or a string representing "
                "a point or a list representing a point."
            )

    def __repr__(self):
        return "<point x={} y={}>".format(self.value[0], self.value[1])

    @property
    def x(self):
        return self.value[0]

    @x.setter
    def x(self, value):
        self.value[0] = value
        # Update parent rect
        if self.rect:
            self.rect.value[0] = value

    @property
    def y(self):
        return self.value[1]

    @y.setter
    def y(self, value):
        self.value[1] = value
        # Update parent rect
        if self.rect:
            self.rect.value[1] = value


class Size(Point):
    def __repr__(self):
        return "<size width={} height={}>".format(self.value[0], self.value[1])

    @property
    def width(self):
        return self.value[0]

    @width.setter
    def width(self, value):
        self.value[0] = value
        # Update parent rect
        if self.rect:
            self.rect.value[2] = value

    @property
    def height(self):
        return self.value[1]

    @height.setter
    def height(self, value):
        self.value[1] = value
        # Update parent rect
        if self.rect:
            self.rect.value[3] = value


class Rect(Vector(4)):
    """Read/write a rect of two points in curly braces."""

    regex = re.compile(r"{{([-.e\d]+), ([-.e\d]+)}, {([-.e\d]+), ([-.e\d]+)}}")

    def __init__(self, value=None, value2=None):
        if value is not None and value2 is not None:
            value = [value[0], value[1], value2[0], value2[1]]
        super().__init__(value)

    def plistValue(self, format_version=2):
        assert isinstance(self.value, list) and len(self.value) == self.dimension
        return '"{{%s, %s}, {%s, %s}}"' % tuple(floatToString3(v) for v in self.value)

    def __repr__(self):
        return "<rect origin={} size={}>".format(str(self.origin), str(self.size))

    @property
    def origin(self):
        return Point(self.value[0], self.value[1], rect=self)

    @origin.setter
    def origin(self, value):
        self.value[0] = value.x
        self.value[1] = value.y

    @property
    def size(self):
        return Size(self.value[2], self.value[3], rect=self)

    @size.setter
    def size(self, value):
        self.value[2] = value.width
        self.value[3] = value.height


class Transform(Vector(6)):
    """Read/write a six-element vector."""

    def __init__(
        self,
        value=None,
        value2=None,
        value3=None,
        value4=None,
        value5=None,
        value6=None,
    ):
        if all(v is not None for v in (value, value2, value3, value4, value5, value6)):
            value = [value, value2, value3, value4, value5, value6]
        super().__init__(value)

    def __repr__(self):
        return "<affine transformation %s>" % (" ".join(map(str, self.value)))

    def plistValue(self, format_version=2):
        assert isinstance(self.value, list) and len(self.value) == self.dimension
        return '"{%s}"' % (", ".join(floatToString5(v) for v in self.value))


UTC_OFFSET_RE = re.compile(r".* (?P<sign>[+-])(?P<hours>\d\d)(?P<minutes>\d\d)$")


def parse_datetime(src=None):
    """Parse a datetime object from a string."""
    if src is None:
        return None
    string = src.replace('"', "")
    # parse timezone ourselves, since %z is not always supported
    # see: http://bugs.python.org/issue6641
    m = UTC_OFFSET_RE.match(string)
    if m:
        sign = 1 if m.group("sign") == "+" else -1
        tz_hours = sign * int(m.group("hours"))
        tz_minutes = sign * int(m.group("minutes"))
        offset = datetime.timedelta(hours=tz_hours, minutes=tz_minutes)
        string = string[:-6]
    else:
        # no explicit timezone
        offset = datetime.timedelta(0)
    if "AM" in string or "PM" in string:
        datetime_obj = datetime.datetime.strptime(string, "%Y-%m-%d %I:%M:%S %p")
    else:
        datetime_obj = datetime.datetime.strptime(string, "%Y-%m-%d %H:%M:%S")
    return datetime_obj + offset


# FIXME: (jany) Not sure this should be used
class Datetime(ValueType):
    """Read/write a datetime.  Doesn't maintain time zone offset."""

    def fromString(self, src):
        return parse_datetime(src)

    def plistValue(self, format_version=2):
        return '"%s +0000"' % self.value

    def strftime(self, val):
        return self.value.strftime(val)


def parse_color(src=None):
    """Parse a string representing a color value.

    Color is either a fixed color (when coloring something from the UI, see
    the GLYPHS_COLORS constant) or a list of the format [u8, u8, u8, u8],

    Glyphs does not support an alpha channel as of 2.5.1 (confirmed by Georg
    Seifert), and always writes a 1 to it. This was brought up and is probably
    corrected in the next versions.
    https://github.com/googlefonts/glyphsLib/pull/363#issuecomment-390418497
    """
    if src is None:
        return None

    # Tuple.
    if src[0] == "(":
        rgba = tuple(int(v) for v in src[1:-1].split(",") if v)

        if not (len(rgba) == 4 and all(0 <= v < 256 for v in rgba)):
            raise ValueError(
                "Broken color tuple: {}. Must have four values from 0 to 255.".format(
                    src
                )
            )

        return rgba

    # Constant.
    return int(src)


# FIXME: (jany) not sure this is used
class Color(ValueType):
    def fromString(self, src):
        return parse_color(src)

    def __repr__(self):
        return self.value.__repr__()

    def plistValue(self, format_version=2):
        return str(self.value)


# mutate list in place
def _mutate_list(fn, l):
    assert isinstance(l, list)
    for i in range(len(l)):
        l[i] = fn(l[i])
    return l


def readIntlist(src):
    return _mutate_list(int, src)


def writeIntlist(val):
    return _mutate_list(str, val)


def floatToString3(f: float) -> str:
    """Return float f as a string with three decimal places without trailing zeros
    and dot.

    Intended for places where three decimals are enough, e.g. node positions.
    """
    return f"{f:.3f}".rstrip("0").rstrip(".")


def floatToString5(f: float) -> str:
    """Return float f as a string with five decimal places without trailing zeros
    and dot.

    Intended for places where five decimals are needed, e.g. transformations.
    """
    return f"{f:.5f}".rstrip("0").rstrip(".")


class UnicodesList(list):
    """Represent a PLIST-able list of unicode codepoints as strings."""

    def __init__(self, value=None):
        if value is None:
            unicodes = []
        elif isinstance(value, str):
            unicodes = value.split(",")
        else:
            unicodes = [str(v) for v in value]
        super().__init__(unicodes)

    def plistValue(self, format_version=2):
        if not self:
            return None
        if len(self) == 1:
            if format_version == 3:
                return str(int(self[0], 16))
            return self[0]
        if format_version == 2:
            return '"%s"' % ",".join(self)
        else:
            return "(%s)" % ",".join([str(int(x, 16)) for x in self])


class BinaryData(bytes):
    @classmethod
    def fromHex(cls, data):
        return cls(binascii.unhexlify(data))

    def plistValue(self, format_version=2):
        # TODO write hex bytes in chunks and split over multiple lines
        # for better readability, like the fonttools xmlWriter does
        return "<%s>" % binascii.hexlify(self).decode()
