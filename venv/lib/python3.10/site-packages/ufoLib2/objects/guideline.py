from __future__ import annotations

from typing import Optional

from attr import define

from ufoLib2.objects.misc import AttrDictMixin


@define
class Guideline(AttrDictMixin):
    """Represents a single guideline.

    See http://unifiedfontobject.org/versions/ufo3/glyphs/glif/#guideline. Has some
    data composition restrictions.
    """

    x: Optional[float] = None
    """The origin x coordinate of the guideline."""

    y: Optional[float] = None
    """The origin y coordinate of the guideline."""

    angle: Optional[float] = None
    """The angle of the guideline."""

    name: Optional[str] = None
    """The name of the guideline, no uniqueness required."""

    color: Optional[str] = None
    """The color of the guideline."""

    identifier: Optional[str] = None
    """The globally unique identifier of the guideline."""

    def __attrs_post_init__(self) -> None:
        x, y, angle = self.x, self.y, self.angle
        if x is None and y is None:
            raise ValueError("x or y must be present")
        if x is None or y is None:
            if angle is not None:
                raise ValueError("if 'x' or 'y' are None, 'angle' must not be present")
        if x is not None and y is not None and angle is None:
            raise ValueError("if 'x' and 'y' are defined, 'angle' must be defined")
        if angle is not None and not (0 <= angle <= 360):
            raise ValueError("angle must be between 0 and 360")
