from __future__ import division, absolute_import
from copy import deepcopy
from fontMath.mathFunctions import add, sub, mul, div, round2

"""
An object that serves kerning data from a
class kerning dictionary.

It scans a group dictionary and stores
a mapping of glyph to group relationships.
this map is then used to lookup kerning values.
"""


side1Prefix = "public.kern1."
side2Prefix = "public.kern2."


class MathKerning(object):

    def __init__(self, kerning=None, groups=None):
        if kerning is None:
            kerning = {}
        if groups is None:
            groups = {}
        self.update(kerning)
        self.updateGroups(groups)

    # -------
    # Loading
    # -------

    def update(self, kerning):
        self._kerning = dict(kerning)

    def updateGroups(self, groups):
        self._groups = {}
        self._side1GroupMap = {}
        self._side2GroupMap = {}
        self._side1Groups = {}
        self._side2Groups = {}
        for groupName, glyphList in groups.items():
            if groupName.startswith(side1Prefix):
                self._groups[groupName] = list(glyphList)
                self._side1Groups[groupName] = glyphList
                for glyphName in glyphList:
                    self._side1GroupMap[glyphName] = groupName
            elif groupName.startswith(side2Prefix):
                self._groups[groupName] = list(glyphList)
                self._side2Groups[groupName] = glyphList
                for glyphName in glyphList:
                    self._side2GroupMap[glyphName] = groupName

    def addTo(self, value):
        for k, v in self._kerning.items():
            self._kerning[k] = v + value

    # -------------
    # dict Behavior
    # -------------

    def keys(self):
        return self._kerning.keys()

    def values(self):
        return self._kerning.values()

    def items(self):
        return self._kerning.items()

    def groups(self):
        return deepcopy(self._groups)

    def __contains__(self, pair):
        return pair in self._kerning

    def __getitem__(self, pair):
        if pair in self._kerning:
            return self._kerning[pair]
        side1, side2 = pair
        if side1.startswith(side1Prefix):
            side1Group = side1
            side1 = None
        else:
            side1Group = self._side1GroupMap.get(side1)
        if side2.startswith(side2Prefix):
            side2Group = side2
            side2 = None
        else:
            side2Group = self._side2GroupMap.get(side2)
        if (side1Group, side2) in self._kerning:
            return self._kerning[side1Group, side2]
        elif (side1, side2Group) in self._kerning:
            return self._kerning[side1, side2Group]
        elif (side1Group, side2Group) in self._kerning:
            return self._kerning[side1Group, side2Group]
        else:
            return 0

    def get(self, pair):
        v = self[pair]
        return v

    # ---------
    # Pair Type
    # ---------

    def guessPairType(self, pair):
        side1, side2 = pair
        if side1.startswith(side1Prefix):
            side1Group = side1
        else:
            side1Group = self._side1GroupMap.get(side1)
        if side2.startswith(side2Prefix):
            side2Group = side2
        else:
            side2Group = self._side2GroupMap.get(side2)
        side1Type = side2Type = "glyph"
        if pair in self:
            if side1 == side1Group:
                side1Type = "group"
            elif side1Group is not None:
                side1Type = "exception"
            if side2 == side2Group:
                side2Type = "group"
            elif side2Group is not None:
                side2Type = "exception"
        elif (side1Group, side2) in self:
            side1Type = "group"
            if side2Group is not None:
                if side2 != side2Group:
                    side2Type = "exception"
        elif (side1, side2Group) in self:
            side2Type = "group"
            if side1Group is not None:
                if side1 != side1Group:
                    side1Type = "exception"
        else:
            if side1Group is not None:
                side1Type = "group"
            if side2Group is not None:
                side2Type = "group"
        return side1Type, side2Type

    # ----
    # Copy
    # ----

    def copy(self):
        k = MathKerning(self._kerning, self._groups)
        return k

    # ----
    # Math
    # ----

    # math with other kerning

    def __add__(self, other):
        k = self._processMathOne(other, add)
        k.cleanup()
        return k

    def __sub__(self, other):
        k = self._processMathOne(other, sub)
        k.cleanup()
        return k

    def _processMathOne(self, other, funct):
        comboPairs = set(self._kerning.keys()) | set(other._kerning.keys())
        kerning = dict.fromkeys(comboPairs, None)
        for k in comboPairs:
            v1 = self.get(k)
            v2 = other.get(k)
            v = funct(v1, v2)
            kerning[k] = v
        g1 = self.groups()
        g2 = other.groups()
        if g1 == g2 or not g1 or not g2:
            groups = g1 or g2
        else:
            comboGroups = set(g1.keys()) | set(g2.keys())
            groups = dict.fromkeys(comboGroups, None)
            for groupName in comboGroups:
                s1 = set(g1.get(groupName, []))
                s2 = set(g2.get(groupName, []))
                groups[groupName] = sorted(list(s1 | s2))
        ks = MathKerning(kerning, groups)
        return ks

    # math with factor

    def __mul__(self, factor):
        if isinstance(factor, tuple):
            factor = factor[0]
        k = self._processMathTwo(factor, mul)
        k.cleanup()
        return k

    def __rmul__(self, factor):
        if isinstance(factor, tuple):
            factor = factor[0]
        k = self._processMathTwo(factor, mul)
        k.cleanup()
        return k

    def __div__(self, factor):
        if isinstance(factor, tuple):
            factor = factor[0]
        k = self._processMathTwo(factor, div)
        k.cleanup()
        return k

    __truediv__ = __div__

    def _processMathTwo(self, factor, funct):
        kerning = deepcopy(self._kerning)
        for k, v in self._kerning.items():
            v = funct(v, factor)
            kerning[k] = v
        ks = MathKerning(kerning, self._groups)
        return ks

    # ---------
    # More math
    # ---------

    def round(self, multiple=1):
        multiple = float(multiple)
        for k, v in self._kerning.items():
            self._kerning[k] = int(round2(int(round2(v / multiple)) * multiple))

    # -------
    # Cleanup
    # -------

    def cleanup(self):
        for (side1, side2), v in list(self._kerning.items()):
            if int(v) == v:
                v = int(v)
                self._kerning[side1, side2] = v
            if v == 0:
                side1Type, side2Type = self.guessPairType((side1, side2))
                if side1Type != "exception" and side2Type != "exception":
                    del self._kerning[side1, side2]

    # ----------
    # Extraction
    # ----------

    def extractKerning(self, font):
        font.kerning.clear()
        font.kerning.update(self._kerning)
        font.groups.update(self.groups())

    # -------
    # Sorting
    # -------
    def _isLessish(self, first, second):
        if len(first) < len(second):
            return True
        elif len(first) > len(second):
            return False

        first_keys = sorted(first)
        second_keys = sorted(second)
        for i, key in enumerate(first_keys):
            if first_keys[i] < second_keys[i]:
                return True
            elif first_keys[i] > second_keys[i]:
                return False
            elif first[key] < second[key]:
                return True
        return None

    def __lt__(self, other):
        if other is None:
            return False

        lessish = self._isLessish(self._kerning, other._kerning)
        if lessish is not None:
            return lessish

        lessish = self._isLessish(self._side1Groups, other._side1Groups)
        if lessish is not None:
            return lessish

        lessish = self._isLessish(self._side2Groups, other._side2Groups)
        if lessish is not None:
            return lessish

        return False

    def __eq__(self, other):
        if self._kerning != other._kerning:
            return False
        if self._side1Groups != other._side1Groups:
            return False
        if self._side2Groups != other._side2Groups:
            return False
        return True


if __name__ == "__main__":
    import sys
    import doctest
    sys.exit(doctest.testmod().failed)
