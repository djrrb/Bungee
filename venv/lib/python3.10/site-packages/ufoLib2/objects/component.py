from __future__ import annotations

import warnings
from typing import Optional

from attr import define, field
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.basePen import AbstractPen
from fontTools.pens.pointPen import AbstractPointPen, PointToSegmentPen

from ufoLib2.objects.misc import BoundingBox
from ufoLib2.typing import GlyphSet

from .misc import _convert_transform, getBounds, getControlBounds


@define
class Component:
    """Represents a reference to another glyph in the same layer.

    See http://unifiedfontobject.org/versions/ufo3/glyphs/glif/#component.

    Note:
        Components always refer to glyphs in the same layer. Referencing different
        layers is currently not possible in the UFO data model.
    """

    baseGlyph: str
    """The name of the glyph in the same layer to insert."""

    transformation: Transform = field(default=Identity, converter=_convert_transform)
    """The affine transformation to apply to the :attr:`.Component.baseGlyph`."""

    identifier: Optional[str] = None
    """The globally unique identifier of the component."""

    def move(self, delta: tuple[float, float]) -> None:
        """Moves this component by (x, y) font units.

        NOTE: This interprets the delta to be the visual delta, as in, it
        replaces the x and y offsets of the component's transformation
        directly, rather than going through
        :meth:`fontTools.misc.transform.Transform.translate`. Otherwise,
        composites that use flipped components (imagine a ``quotedblleft``
        composite using two x- and y-inverted ``comma`` components)
        would move in the opposite direction of the delta.
        """
        x, y = delta
        xx, xy, yx, yy, dx, dy = self.transformation
        self.transformation = Transform(xx, xy, yx, yy, dx + x, dy + y)

    def getBounds(self, layer: GlyphSet) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the component,
        taking the actual contours into account.

        Args:
            layer: The layer of the containing glyph to look up components.
        """
        return getBounds(self, layer)

    def getControlBounds(self, layer: GlyphSet) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the component,
        taking only the control points into account.

        Args:
            layer: The layer of the containing glyph to look up components.
        """
        return getControlBounds(self, layer)

    # -----------
    # Pen methods
    # -----------

    def draw(self, pen: AbstractPen) -> None:
        """Draws component with given pen."""
        pointPen = PointToSegmentPen(pen)
        self.drawPoints(pointPen)

    def drawPoints(self, pointPen: AbstractPointPen) -> None:
        """Draws points of component with given point pen."""
        try:
            pointPen.addComponent(
                self.baseGlyph, self.transformation, identifier=self.identifier
            )
        except TypeError:
            pointPen.addComponent(self.baseGlyph, self.transformation)
            warnings.warn(
                "The addComponent method needs an identifier kwarg. "
                "The component's identifier value has been discarded.",
                UserWarning,
            )
