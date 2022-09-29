import logging

from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.bezierTools import (
    segmentSegmentIntersections,
    _split_segment_at_t,
)
from ufo2ft.filters import BaseFilter

logger = logging.getLogger(__name__)


def _pointIsLeftOfLine(line, aPoint):
    a, b = line
    return (
        (b[0] - a[0]) * (aPoint[1] - a[1]) - (b[1] - a[1]) * (aPoint[0] - a[0])
    ) >= 0


class EraseOpenCornersPen(BasePen):
    def __init__(self, outpen):
        self.segments = []
        self.is_closed = False
        self.affected = False
        self.outpen = outpen

    def _moveTo(self, p1):
        self.segments = []
        self.is_closed = False

    def _operate(self, *points):
        self.segments.append((self._getCurrentPoint(), *points))

    _qCurveTo = _curveTo = _lineTo = _qCurveToOne = _curveToOne = _operate

    def closePath(self):
        self.segments.append((self._getCurrentPoint(), self.segments[0][0]))
        self.is_closed = True
        self.endPath()

    def endPath(self):
        segs = self.segments
        if not segs:
            return

        ix = 0

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Starting open corner removal, count of segments now: %i", len(segs)
            )
            logger.debug("Segments: %s", segs)

        while ix < len(segs):
            next_ix = (ix + 1) % len(segs)

            # Am I a line segment?
            if not len(segs[ix]) == 2:
                ix = ix + 1
                continue

            logger.debug(
                "Considering line segment (%i,%i)-(%i,%i)", *segs[ix][0], *segs[ix][1]
            )
            # Are the incoming point from the previous segment and the outgoing point
            # from the next segment both on the right side of the line?
            # (see discussion at https://github.com/googlefonts/glyphsLib/pull/663)
            pt1 = segs[ix - 1][-2]
            pt2 = segs[next_ix][1]
            if _pointIsLeftOfLine(segs[ix], pt1) or _pointIsLeftOfLine(segs[ix], pt2):
                logger.debug(
                    "Crossing points (%i, %i) and (%i, %i) were not on "
                    "same side of line segment",
                    *pt1,
                    *pt2,
                )
                ix = ix + 1
                continue

            logger.debug(
                "Testing for intersections between %s and %s",
                segs[ix - 1],
                segs[next_ix],
            )

            intersection = [
                i
                for i in segmentSegmentIntersections(segs[ix - 1], segs[next_ix])
                if 0 <= i.t1 <= 1 and 0 <= i.t2 <= 1
            ]
            logger.debug("Intersections: %s", intersection)
            if not intersection:
                logger.debug("No intersections")
                ix = ix + 1
                continue

            # The t values of the intersection are measured as follows:
            #  line1 is coming *towards* the open corner line, i.e. t1=0.9 is very near
            #  the open corner.
            #  line2 is going *away from* the open corner line, i.e. t2=0.1 is very near
            #  the open corner.
            # This is a bit confusing, so we invert the value of t1 so that
            # both values mean 0 is at the open corner and 1 is far from it.
            t1 = 1 - intersection[0].t1
            t2 = intersection[0].t2

            # Glyphs logic provided by Georg at
            # https://github.com/googlefonts/glyphsLib/pull/663#issuecomment-925667615
            if (
                ((t1 < 0.5 and t2 < 0.5) or t1 < 0.3 or t2 < 0.3)
                and t1 > 0.0001
                and t2 > 0.0001
            ):
                logger.debug("Found an open corner")
                (segs[ix - 1], _) = _split_segment_at_t(
                    segs[ix - 1], intersection[0].t1
                )
                (_, segs[next_ix]) = _split_segment_at_t(
                    segs[next_ix], intersection[0].t2
                )
                # Ensure the ends match up
                segs[next_ix] = (segs[ix - 1][-1],) + segs[next_ix][1:]
                segs[ix : ix + 1] = []
                self.affected = True
                # Start again!
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "After removing seg %i, count of segments now: %i",
                        ix,
                        len(segs),
                    )
                    logger.debug("Segments: %s", segs)
                ix = 0
                continue
            ix = ix + 1

        self.outpen.moveTo(segs[0][0])
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("All done, count of segments now: %i", len(segs))
            logger.debug("Segments: %s", segs)

        for seg in segs:
            if len(seg) == 2:
                self.outpen.lineTo(*seg[1:])
            elif len(seg) == 3:
                self.outpen.qCurveTo(*seg[1:])
            elif len(seg) == 4:
                self.outpen.curveTo(*seg[1:])

        if self.is_closed:
            self.outpen.closePath()
        else:
            self.outpen.endPath()


class EraseOpenCornersFilter(BaseFilter):
    def filter(self, glyph):
        if not len(glyph):
            return False

        contours = list(glyph)
        outpen = RecordingPen()
        p = EraseOpenCornersPen(outpen)
        for contour in contours:
            contour.draw(p)
        if p.affected:
            glyph.clearContours()
            outpen.replay(glyph.getPen())
        return p.affected
