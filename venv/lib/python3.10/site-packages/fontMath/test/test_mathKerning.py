from __future__ import unicode_literals
import unittest
from fontMath.mathFunctions import _roundNumber
from fontMath.mathKerning import MathKerning


class TestKerning(object):
    """Mockup Kerning class"""
    def __init__(self):
        self._kerning = {}

    def clear(self):
        self._kerning = {}

    def asDict(self, returnIntegers=True):
        if not returnIntegers:
            return self._kerning
        kerning = {k: _roundNumber(v) for (k, v) in self._kerning.items()}
        return kerning

    def update(self, kerningDict):
        self._kerning = {k: v for (k, v) in kerningDict.items()
                         if v != 0}


class TestFont(object):
    """Mockup Font class"""
    def __init__(self):
        self.kerning = TestKerning()
        self.groups = {}


class MathKerningTest(unittest.TestCase):

    def test_addTo(self):
        kerning = {
            ("A", "A"): 1,
            ("B", "B"): -1,
        }
        obj = MathKerning(kerning)
        obj.addTo(1)
        self.assertEqual(sorted(obj.items()),
                         [(('A', 'A'), 2), (('B', 'B'), 0)])

    def test_getitem(self):
        kerning = {
            ("public.kern1.A", "public.kern2.A"): 1,
            ("A1", "public.kern2.A"): 2,
            ("public.kern1.A", "A2"): 3,
            ("A3", "A3"): 4,
        }
        groups = {
            "public.kern1.A": ["A", "A1", "A2", "A3"],
            "public.kern2.A": ["A", "A1", "A2", "A3"],
        }
        obj = MathKerning(kerning, groups)
        self.assertEqual(obj["A", "A"], 1)
        self.assertEqual(obj["A1", "A"], 2)
        self.assertEqual(obj["A", "A2"], 3)
        self.assertEqual(obj["A3", "A3"], 4)
        self.assertEqual(obj["X", "X"], 0)
        self.assertEqual(obj["A3", "public.kern2.A"], 1)
        self.assertEqual(sorted(obj.keys())[1], ("A3", "A3"))
        self.assertEqual(sorted(obj.values())[3], 4)

    def test_guessPairType(self):
        kerning = {
            ("public.kern1.A", "public.kern2.A"): 1,
            ("A1", "public.kern2.A"): 2,
            ("public.kern1.A", "A2"): 3,
            ("A3", "A3"): 4,
            ("public.kern1.B", "public.kern2.B"): 5,
            ("public.kern1.B", "B"): 6,
            ("public.kern1.C", "public.kern2.C"): 7,
            ("C", "public.kern2.C"): 8,
        }
        groups = {
            "public.kern1.A": ["A", "A1", "A2", "A3"],
            "public.kern2.A": ["A", "A1", "A2", "A3"],
            "public.kern1.B": ["B"],
            "public.kern2.B": ["B"],
            "public.kern1.C": ["C"],
            "public.kern2.C": ["C"],
        }
        obj = MathKerning(kerning, groups)
        self.assertEqual(obj.guessPairType(("public.kern1.A", "public.kern2.A")),
                         ('group', 'group'))
        self.assertEqual(obj.guessPairType(("A1", "public.kern2.A")),
                         ('exception', 'group'))
        self.assertEqual(obj.guessPairType(("public.kern1.A", "A2")),
                         ('group', 'exception'))
        self.assertEqual(obj.guessPairType(("A3", "A3")),
                         ('exception', 'exception'))
        self.assertEqual(obj.guessPairType(("A", "A")),
                         ('group', 'group'))
        self.assertEqual(obj.guessPairType(("B", "B")),
                         ('group', 'exception'))
        self.assertEqual(obj.guessPairType(("C", "C")),
                         ('exception', 'group'))

    def test_copy(self):
        kerning1 = {
            ("A", "A"): 1,
            ("B", "B"): 1,
            ("NotIn2", "NotIn2"): 1,
            ("public.kern1.NotIn2", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups1 = {
            "public.kern1.NotIn1": ["C"],
            "public.kern1.D": ["D", "H"],
            "public.kern2.D": ["D", "H"],
        }
        obj1 = MathKerning(kerning1, groups1)
        obj2 = obj1.copy()
        self.assertEqual(sorted(obj1.items()), sorted(obj2.items()))

    def test_add(self):
        kerning1 = {
            ("A", "A"): 1,
            ("B", "B"): 1,
            ("NotIn2", "NotIn2"): 1,
            ("public.kern1.NotIn2", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups1 = {
            "public.kern1.NotIn1": ["C"],
            "public.kern1.D": ["D", "H"],
            "public.kern2.D": ["D", "H"],
        }
        kerning2 = {
            ("A", "A"): -1,
            ("B", "B"): 1,
            ("NotIn1", "NotIn1"): 1,
            ("public.kern1.NotIn1", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups2 = {
            "public.kern1.NotIn2": ["C"],
            "public.kern1.D": ["D", "H"],
            "public.kern2.D": ["D", "H"],
        }
        obj = MathKerning(kerning1, groups1) + MathKerning(kerning2, groups2)
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 2),
             (('NotIn1', 'NotIn1'), 1),
             (('NotIn2', 'NotIn2'), 1),
             (('public.kern1.D', 'public.kern2.D'), 2),
             (('public.kern1.NotIn1', 'C'), 1),
             (('public.kern1.NotIn2', 'C'), 1)])
        self.assertEqual(
            obj.groups()["public.kern1.D"],
            ['D', 'H'])
        self.assertEqual(
            obj.groups()["public.kern2.D"],
            ['D', 'H'])

    def test_add_same_groups(self):
        kerning1 = {
            ("A", "A"): 1,
            ("B", "B"): 1,
            ("NotIn2", "NotIn2"): 1,
            ("public.kern1.NotIn2", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups1 = {
            "public.kern1.D": ["D", "H"],
            "public.kern2.D": ["D", "H"],
        }
        kerning2 = {
            ("A", "A"): -1,
            ("B", "B"): 1,
            ("NotIn1", "NotIn1"): 1,
            ("public.kern1.NotIn1", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups2 = {
            "public.kern1.D": ["D", "H"],
            "public.kern2.D": ["D", "H"],
        }
        obj = MathKerning(kerning1, groups1) + MathKerning(kerning2, groups2)
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 2),
             (('NotIn1', 'NotIn1'), 1),
             (('NotIn2', 'NotIn2'), 1),
             (('public.kern1.D', 'public.kern2.D'), 2),
             (('public.kern1.NotIn1', 'C'), 1),
             (('public.kern1.NotIn2', 'C'), 1)])
        self.assertEqual(
            obj.groups()["public.kern1.D"],
            ['D', 'H'])
        self.assertEqual(
            obj.groups()["public.kern2.D"],
            ['D', 'H'])

    def test_sub(self):
        kerning1 = {
            ("A", "A"): 1,
            ("B", "B"): 1,
            ("NotIn2", "NotIn2"): 1,
            ("public.kern1.NotIn2", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups1 = {
            "public.kern1.NotIn1": ["C"],
            "public.kern1.D": ["D", "H"],
            "public.kern2.D": ["D", "H"],
        }
        kerning2 = {
            ("A", "A"): -1,
            ("B", "B"): 1,
            ("NotIn1", "NotIn1"): 1,
            ("public.kern1.NotIn1", "C"): 1,
            ("public.kern1.D", "public.kern2.D"): 1,
        }
        groups2 = {
            "public.kern1.NotIn2": ["C"],
            "public.kern1.D": ["D"],
            "public.kern2.D": ["D", "H"],
        }
        obj = MathKerning(kerning1, groups1) - MathKerning(kerning2, groups2)
        self.assertEqual(
            sorted(obj.items()),
            [(('A', 'A'), 2),
             (('NotIn1', 'NotIn1'), -1),
             (('NotIn2', 'NotIn2'), 1),
             (('public.kern1.NotIn1', 'C'), -1),
             (('public.kern1.NotIn2', 'C'), 1)])
        self.assertEqual(
            obj.groups()["public.kern1.D"],
            ['D', 'H'])
        self.assertEqual(
            obj.groups()["public.kern2.D"],
            ['D', 'H'])

    def test_mul(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 1,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 2,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        obj = MathKerning(kerning, groups) * 2
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 2),
             (('C2', 'public.kern2.C'), 0),
             (('public.kern1.C', 'public.kern2.C'), 4)])

    def test_mul_tuple_factor(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 1,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 2,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        obj = MathKerning(kerning, groups) * (3, 2)
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 3),
             (('C2', 'public.kern2.C'), 0),
             (('public.kern1.C', 'public.kern2.C'), 6)])

    def test_rmul(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 1,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 2,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        obj = 2 * MathKerning(kerning, groups)
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 2),
             (('C2', 'public.kern2.C'), 0),
             (('public.kern1.C', 'public.kern2.C'), 4)])

    def test_rmul_tuple_factor(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 1,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 2,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        obj = (3, 2) * MathKerning(kerning, groups)
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 3),
             (('C2', 'public.kern2.C'), 0),
             (('public.kern1.C', 'public.kern2.C'), 6)])

    def test_div(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        obj = MathKerning(kerning, groups) / 2
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 2),
             (('C2', 'public.kern2.C'), 0),
             (('public.kern1.C', 'public.kern2.C'), 2)])

    def test_compare_same_kerning_only(self):
        kerning1 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
        }
        kerning2 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
        }
        mathKerning1 = MathKerning(kerning1, {})
        mathKerning2 = MathKerning(kerning2, {})
        self.assertFalse(mathKerning1 < mathKerning2)
        self.assertFalse(mathKerning1 > mathKerning2)
        self.assertEqual(mathKerning1, mathKerning2)

    def test_compare_same_kerning_same_groups(self):
        kerning1 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        kerning2 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        mathKerning1 = MathKerning(kerning1, groups)
        mathKerning2 = MathKerning(kerning2, groups)
        self.assertFalse(mathKerning1 < mathKerning2)
        self.assertFalse(mathKerning1 > mathKerning2)
        self.assertEqual(mathKerning1, mathKerning2)

    def test_compare_diff_kerning_diff_groups(self):
        kerning1 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        kerning2 = {
            ("A", "A"): 0,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        groups1 = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2", "C3"],
        }
        groups2 = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        mathKerning1 = MathKerning(kerning1, groups1)
        mathKerning2 = MathKerning(kerning2, groups2)
        self.assertFalse(mathKerning1 < mathKerning2)
        self.assertTrue(mathKerning1 > mathKerning2)
        self.assertNotEqual(mathKerning1, mathKerning2)

    def test_compare_diff_kerning_same_groups(self):
        kerning1 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        kerning2 = {
            ("A", "A"): 0,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        mathKerning1 = MathKerning(kerning1, groups)
        mathKerning2 = MathKerning(kerning2, groups)
        self.assertFalse(mathKerning1 < mathKerning2)
        self.assertTrue(mathKerning1 > mathKerning2)
        self.assertNotEqual(mathKerning1, mathKerning2)

    def test_compare_same_kerning_diff_groups(self):
        kerning1 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        kerning2 = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        groups1 = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        groups2 = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2", "C3"],
        }
        mathKerning1 = MathKerning(kerning1, groups1)
        mathKerning2 = MathKerning(kerning2, groups2)
        self.assertTrue(mathKerning1 < mathKerning2)
        self.assertFalse(mathKerning1 > mathKerning2)
        self.assertNotEqual(mathKerning1, mathKerning2)

    def test_div_tuple_factor(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 4,
            ("C2", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 4,
        }
        groups = {
            "public.kern1.C": ["C1", "C2"],
            "public.kern2.C": ["C1", "C2"],
        }
        obj = MathKerning(kerning, groups) / (4, 2)
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 1),
             (('C2', 'public.kern2.C'), 0),
             (('public.kern1.C', 'public.kern2.C'), 1)])

    def test_round(self):
        kerning = {
            ("A", "A"): 1.99,
            ("B", "B"): 4,
            ("C", "C"): 7,
            ("D", "D"): 9.01,
        }
        obj = MathKerning(kerning)
        obj.round(5)
        self.assertEqual(
            sorted(obj.items()),
            [(('A', 'A'), 0), (('B', 'B'), 5),
             (('C', 'C'), 5), (('D', 'D'), 10)])

    def test_cleanup(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 1,
            ("C", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 1,
            ("D", "D"): 1.0,
            ("E", "E"): 1.2,
        }
        groups = {
            "public.kern1.C": ["C", "C1"],
            "public.kern2.C": ["C", "C1"]
        }
        obj = MathKerning(kerning, groups)
        obj.cleanup()
        self.assertEqual(
            sorted(obj.items()),
            [(('B', 'B'), 1),
             (('C', 'public.kern2.C'), 0),
             (('D', 'D'), 1),
             (('E', 'E'), 1.2),
             (('public.kern1.C', 'public.kern2.C'), 1)])

    def test_extractKerning(self):
        kerning = {
            ("A", "A"): 0,
            ("B", "B"): 1,
            ("C", "public.kern2.C"): 0,
            ("public.kern1.C", "public.kern2.C"): 1,
            ("D", "D"): 1.0,
            ("E", "E"): 1.2,
        }
        groups = {
            "public.kern1.C": ["C", "C1"],
            "public.kern2.C": ["C", "C1"]
        }
        font = TestFont()
        self.assertEqual(font.kerning.asDict(), {})
        self.assertEqual(list(font.groups.items()), [])
        obj = MathKerning(kerning, groups)
        obj.extractKerning(font)
        self.assertEqual(
            sorted(font.kerning.asDict().items()),
            [(('B', 'B'), 1),
             (('D', 'D'), 1), (('E', 'E'), 1),
             (('public.kern1.C', 'public.kern2.C'), 1)])
        self.assertEqual(
            sorted(font.groups.items()),
            [('public.kern1.C', ['C', 'C1']),
             ('public.kern2.C', ['C', 'C1'])])

    def test_fallback(self):
        groups = {
            "public.kern1.A" : ["A", "A.alt"],
            "public.kern2.O" : ["O", "O.alt"]
        }
        kerning1 = {
            ("A", "O") : 1000,
            ("public.kern1.A", "public.kern2.O") : 100
        }
        kerning2 = {
            ("public.kern1.A", "public.kern2.O") : 200
        }

        kerning1 = MathKerning(kerning1, groups)
        kerning2 = MathKerning(kerning2, groups)

        kerning3 = kerning1 + kerning2

        self.assertEqual(
            kerning3["A", "O"],
            1200)


if __name__ == "__main__":
    unittest.main()
