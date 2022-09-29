import importlib
import logging
from inspect import getfullargspec, isclass

from ufo2ft.constants import FEATURE_WRITERS_KEY
from ufo2ft.util import _loadPluginFromString

from .baseFeatureWriter import BaseFeatureWriter
from .cursFeatureWriter import CursFeatureWriter
from .gdefFeatureWriter import GdefFeatureWriter
from .kernFeatureWriter import KernFeatureWriter
from .markFeatureWriter import MarkFeatureWriter

__all__ = [
    "BaseFeatureWriter",
    "CursFeatureWriter",
    "GdefFeatureWriter",
    "KernFeatureWriter",
    "MarkFeatureWriter",
    "loadFeatureWriters",
]

logger = logging.getLogger(__name__)


def isValidFeatureWriter(klass):
    """Return True if 'klass' is a valid feature writer class.
    A valid feature writer class is a class (of type 'type'), that has
    two required attributes:
    1) 'tableTag' (str), which can be "GSUB", "GPOS", or other similar tags.
    2) 'write' (bound method), with the signature matching the same method
       from the BaseFeatureWriter class:

           def write(self, font, feaFile, compiler=None)
    """
    if not isclass(klass):
        logger.error("%r is not a class", klass)
        return False
    if not hasattr(klass, "tableTag"):
        logger.error("%r does not have required 'tableTag' attribute", klass)
        return False
    if not hasattr(klass, "write"):
        logger.error("%r does not have a required 'write' method", klass)
        return False
    if getfullargspec(klass.write).args != getfullargspec(BaseFeatureWriter.write).args:
        logger.error("%r 'write' method has incorrect signature", klass)
        return False
    return True


def loadFeatureWriters(ufo, ignoreErrors=True):
    """Check UFO lib for key "com.github.googlei18n.ufo2ft.featureWriters",
    containing a list of dicts, each having the following key/value pairs:
    For example:

      {
        "module": "myTools.featureWriters",  # default: ufo2ft.featureWriters
        "class": "MyKernFeatureWriter",  # required
        "options": {"doThis": False, "doThat": True},
      }

    Import each feature writer class from the specified module (default is
    the built-in ufo2ft.featureWriters), and instantiate it with the given
    'options' dict.

    Return the list of feature writer objects.
    If the 'featureWriters' key is missing from the UFO lib, return None.

    If an exception occurs and 'ignoreErrors' is True, the exception message
    is logged and the invalid writer is skipped, otrherwise it's propagated.
    """
    if FEATURE_WRITERS_KEY not in ufo.lib:
        return None
    writers = []
    for wdict in ufo.lib[FEATURE_WRITERS_KEY]:
        try:
            moduleName = wdict.get("module", __name__)
            className = wdict["class"]
            options = wdict.get("options", {})
            if not isinstance(options, dict):
                raise TypeError(type(options))
            module = importlib.import_module(moduleName)
            klass = getattr(module, className)
            if not isValidFeatureWriter(klass):
                raise TypeError(klass)
            writer = klass(**options)
        except Exception:
            if ignoreErrors:
                logger.exception("failed to load feature writer: %r", wdict)
                continue
            raise
        writers.append(writer)
    return writers


def loadFeatureWriterFromString(spec):
    """Take a string specifying a feature writer class to load (either a
    built-in writer or one defined in an external, user-defined module),
    initialize it with given options and return the writer object.

    The string must conform to the following notation:
    - an optional python module, followed by '::'
    - a required class name; the class must have a method call 'write'
      with the same signature as the BaseFeatureWriter.
    - an optional list of keyword-only arguments enclosed by parentheses

    Raises ValueError if the string doesn't conform to this specification;
    TypeError if imported name is not a feature writer class; and
    ImportError if the user-defined module cannot be imported.

    Examples:

    >>> loadFeatureWriterFromString("KernFeatureWriter")
    <ufo2ft.featureWriters.kernFeatureWriter.KernFeatureWriter object at ...>
    >>> w = loadFeatureWriterFromString("KernFeatureWriter(ignoreMarks=False)")
    >>> w.options.ignoreMarks
    False
    >>> w = loadFeatureWriterFromString("MarkFeatureWriter(features=['mkmk'])")
    >>> w.features == frozenset(['mkmk'])
    True
    >>> loadFeatureWriterFromString("ufo2ft.featureWriters::KernFeatureWriter")
    <ufo2ft.featureWriters.kernFeatureWriter.KernFeatureWriter object at ...>
    """
    return _loadPluginFromString(spec, "ufo2ft.featureWriters", isValidFeatureWriter)
