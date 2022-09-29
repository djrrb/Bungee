from __future__ import annotations

from typing import Optional

from attr import define

from ufoLib2.objects.misc import AttrDictMixin


@define
class Anchor(AttrDictMixin):
    """Represents a single anchor.

    See http://unifiedfontobject.org/versions/ufo3/glyphs/glif/#anchor.
    """

    x: float
    """The x coordinate of the anchor."""

    y: float
    """The y coordinate of the anchor."""

    name: Optional[str] = None
    """The name of the anchor."""

    color: Optional[str] = None
    """The color of the anchor."""

    identifier: Optional[str] = None
    """The globally unique identifier of the anchor."""

    def move(self, delta: tuple[float, float]) -> None:
        """Moves anchor by (x, y) font units."""
        x, y = delta
        self.x += x
        self.y += y
