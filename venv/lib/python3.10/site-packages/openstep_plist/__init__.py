from .parser import load, loads, ParseError
from .writer import dump, dumps

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"


__all__ = ["load", "loads", "dump", "dumps", "ParseError"]
