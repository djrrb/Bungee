from __future__ import annotations

from typing import Optional

from attr import define


@define
class Point:
    """Represents a single point.

    See http://unifiedfontobject.org/versions/ufo3/glyphs/glif/#point.
    """

    x: float
    """The x coordinate of the point."""

    y: float
    """The y coordinate of the point."""

    type: Optional[str] = None
    """The type of the point.

    ``None`` means "offcurve".

    See http://unifiedfontobject.org/versions/ufo3/glyphs/glif/#point-types.
    """

    smooth: bool = False
    """Whether a smooth curvature should be maintained at this point."""

    name: Optional[str] = None
    """The name of the point, no uniqueness required."""

    identifier: Optional[str] = None
    """The globally unique identifier of the point."""

    # XXX: Add post_init to check spec-mandated invariants?

    @property
    def segmentType(self) -> str | None:
        """Returns the type of the point.

        |defcon_compat|
        """
        return self.type

    def move(self, delta: tuple[float, float]) -> None:
        """Moves point by (x, y) font units."""
        x, y = delta
        self.x += x
        self.y += y
