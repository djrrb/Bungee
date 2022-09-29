from __future__ import annotations

import os
import sys
from typing import TypeVar, Union

from fontTools.pens.basePen import AbstractPen
from fontTools.pens.pointPen import AbstractPointPen

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol


T = TypeVar("T")
"""Generic variable for mypy for trivial generic function signatures."""

PathLike = Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]
"""Represents a path in various possible forms."""


class Drawable(Protocol):
    """Stand-in for an object that can draw itself with a given pen.

    See :mod:`fontTools.pens.basePen` for an introduction to pens.
    """

    def draw(self, pen: AbstractPen) -> None:
        ...


class DrawablePoints(Protocol):
    """Stand-in for an object that can draw its points with a given pen.

    See :mod:`fontTools.pens.pointPen` for an introduction to point pens.
    """

    def drawPoints(self, pen: AbstractPointPen) -> None:
        ...


class HasIdentifier(Protocol):
    """Any object that has a unique identifier in some context that can be
    used as a key in a public.objectLibs dictionary."""

    identifier: str | None


class GlyphSet(Protocol):
    """Any container that holds drawable objects.

    In ufoLib2, this usually refers to :class:`.Font` (referencing glyphs in the
    default layer) and :class:`.Layer` (referencing glyphs in that particular layer).
    Ideally, this would be a simple subclass of ``Mapping[str, Union[Drawable, DrawablePoints]]``,
    but due to historic reasons, the established objects don't conform to ``Mapping``
    exactly.

    The protocol contains what is used in :mod:`fontTools.pens` at v4.18.2
    (grep for ``.glyphSet``).
    """

    # "object" instead of "str" because that's what typeshed says a Mapping should have.
    def __contains__(self, name: object) -> bool:
        ...

    def __getitem__(self, name: str) -> Drawable | DrawablePoints:
        ...
