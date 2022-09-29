"""
A set of fast glyph and font objects for math operations.

This was inspired, and is more or less a clone, of Erik van Blokland's
brilliant glyph math in RoboFab.
"""

try:
    from ._version import __version__
except ImportError:
    try:
        from setuptools_scm import get_version
        __version__ = get_version()
    except ImportError:
        __version__ = 'unknown'

from fontMath.mathGlyph import MathGlyph
from fontMath.mathInfo import MathInfo
from fontMath.mathKerning import MathKerning
