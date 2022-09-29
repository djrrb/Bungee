"""ufoLib2 -- a package for dealing with UFO fonts."""

from __future__ import annotations

from ufoLib2.objects import Font

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"


__all__ = ["Font"]
