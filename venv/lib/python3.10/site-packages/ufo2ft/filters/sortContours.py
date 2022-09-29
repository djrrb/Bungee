import logging

import fontTools.pens.boundsPen

from ufo2ft.filters import BaseFilter

logger = logging.getLogger(__name__)


class SortContoursFilter(BaseFilter):
    """Sort contours by their bounding box.

    ATTENTION: This filter should be run after decomposition! Mixed contours and
    components cannot meaningfully be sorted.

    This is to work around the undefined contour order in pyclipper, see
    https://sourceforge.net/p/polyclipping/bugs/195/. It only strikes on glyphs
    that contain a lot of contours on the same height (think word marks or glyphs
    like U+FFFC OBJECT REPLACEMENT CHARACTER, U+034F COMBINING GRAPHEME JOINER
    or U+2591 LIGHT SHADE).
    """

    def filter(self, glyph):
        if len(glyph) == 0:  # As in, no contours.
            return False

        if glyph.components:
            logger.warning(
                "Glyph '%s' contains components which will not be sorted.",
                glyph.name,
            )

        contours = sorted(
            (c for c in glyph), key=lambda contour: _control_bounding_box(contour)
        )
        glyph.clearContours()
        if hasattr(glyph, "appendContour"):  # defcon
            for contour in contours:
                glyph.appendContour(contour)
        else:  # ufoLib2
            glyph.contours.extend(contours)

        return True


def _control_bounding_box(contour):
    pen = fontTools.pens.boundsPen.ControlBoundsPen(None)
    p2s_pen = fontTools.pens.pointPen.PointToSegmentPen(pen)
    contour.drawPoints(p2s_pen)
    return pen.bounds
