from __future__ import annotations

import warnings
from collections.abc import MutableSequence
from typing import TYPE_CHECKING, Iterable, Iterator, List, Optional, overload

from attr import define, field
from fontTools.pens.basePen import AbstractPen
from fontTools.pens.pointPen import AbstractPointPen, PointToSegmentPen

from ufoLib2.objects.misc import BoundingBox, getBounds, getControlBounds
from ufoLib2.objects.point import Point
from ufoLib2.typing import GlyphSet

# For Python 3.7 compatibility.
if TYPE_CHECKING:
    ContourMapping = MutableSequence[Point]
else:
    ContourMapping = MutableSequence


@define
class Contour(ContourMapping):
    """Represents a contour as a list of points.

    Behavior:
        The Contour object has list-like behavior. This behavior allows you to interact
        with point data directly. For example, to get a particular point::

            point = contour[0]

        To iterate over all points::

            for point in contour:
                ...

        To get the number of points::

            pointCount = len(contour)

        To delete a particular point::

            del contour[0]

        To set a particular point to another Point object::

            contour[0] = anotherPoint
    """

    points: List[Point] = field(factory=list)
    """The list of points in the contour."""

    identifier: Optional[str] = field(default=None, repr=False)
    """The globally unique identifier of the contour."""

    # collections.abc.MutableSequence interface

    def __delitem__(self, index: int | slice) -> None:
        del self.points[index]

    @overload
    def __getitem__(self, index: int) -> Point:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[Point]:  # noqa: F811
        ...

    def __getitem__(self, index: int | slice) -> Point | list[Point]:  # noqa: F811
        return self.points[index]

    def __setitem__(  # noqa: F811
        self, index: int | slice, point: Point | Iterable[Point]
    ) -> None:
        if isinstance(index, int) and isinstance(point, Point):
            self.points[index] = point
        elif (
            isinstance(index, slice)
            and isinstance(point, Iterable)
            and all(isinstance(p, Point) for p in point)
        ):
            self.points[index] = point
        else:
            raise TypeError(
                f"Expected Point or Iterable[Point], found {type(point).__name__}."
            )

    def __iter__(self) -> Iterator[Point]:
        return iter(self.points)

    def __len__(self) -> int:
        return len(self.points)

    def insert(self, index: int, value: Point) -> None:
        """Insert Point object ``value`` into the contour at ``index``."""
        if not isinstance(value, Point):
            raise TypeError(f"Expected Point, found {type(value).__name__}.")
        self.points.insert(index, value)

    # TODO: rotate method?

    @property
    def open(self) -> bool:
        """Returns whether the contour is open or closed."""
        if not self.points:
            return True
        return self.points[0].type == "move"

    def move(self, delta: tuple[float, float]) -> None:
        """Moves contour by (x, y) font units."""
        for point in self.points:
            point.move(delta)

    def getBounds(self, layer: GlyphSet | None = None) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the glyph,
        taking the actual contours into account.

        Args:
            layer: Not applicable to contours, here for API symmetry.
        """
        return getBounds(self, layer)

    @property
    def bounds(self) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the glyph,
        taking the actual contours into account.

        |defcon_compat|
        """
        return self.getBounds()

    def getControlBounds(self, layer: GlyphSet | None = None) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the glyph,
        taking only the control points into account.

        Args:
            layer: Not applicable to contours, here for API symmetry.
        """
        return getControlBounds(self, layer)

    @property
    def controlPointBounds(self) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the glyph,
        taking only the control points into account.

        |defcon_compat|
        """
        return self.getControlBounds()

    # -----------
    # Pen methods
    # -----------

    def draw(self, pen: AbstractPen) -> None:
        """Draws contour into given pen."""
        pointPen = PointToSegmentPen(pen)
        self.drawPoints(pointPen)

    def drawPoints(self, pointPen: AbstractPointPen) -> None:
        """Draws points of contour into given point pen."""
        try:
            pointPen.beginPath(identifier=self.identifier)
            for p in self.points:
                pointPen.addPoint(
                    (p.x, p.y),
                    segmentType=p.type,
                    smooth=p.smooth,
                    name=p.name,
                    identifier=p.identifier,
                )
        except TypeError:
            pointPen.beginPath()
            for p in self.points:
                pointPen.addPoint(
                    (p.x, p.y), segmentType=p.type, smooth=p.smooth, name=p.name
                )
            warnings.warn(
                "The pointPen needs an identifier kwarg. "
                "Identifiers have been discarded.",
                UserWarning,
            )
        pointPen.endPath()
