import logging

from cu2qu.pens import Cu2QuPointPen
from cu2qu.ufo import CURVE_TYPE_LIB_KEY, DEFAULT_MAX_ERR

from ufo2ft.filters import BaseFilter
from ufo2ft.fontInfoData import getAttrWithFallback

logger = logging.getLogger(__name__)


class CubicToQuadraticFilter(BaseFilter):

    _kwargs = {
        "conversionError": None,
        "reverseDirection": True,
        "rememberCurveType": False,
    }

    def set_context(self, font, glyphSet):
        ctx = super().set_context(font, glyphSet)

        relativeError = self.options.conversionError or DEFAULT_MAX_ERR
        ctx.absoluteError = relativeError * getAttrWithFallback(font.info, "unitsPerEm")

        ctx.stats = {}

        return ctx

    def __call__(self, font, glyphSet=None):
        if self.options.rememberCurveType:
            # check first in the global font lib, then in layer lib
            for lib in (font.lib, getattr(glyphSet, "lib", {})):
                curve_type = lib.get(CURVE_TYPE_LIB_KEY, "cubic")
                if curve_type == "quadratic":
                    logger.info("Curves already converted to quadratic")
                    return set()
                elif curve_type == "cubic":
                    pass  # keep converting
                else:
                    raise NotImplementedError(curve_type)

        modified = super().__call__(font, glyphSet)
        if modified:
            stats = self.context.stats
            logger.info(
                "New spline lengths: %s"
                % (", ".join("%s: %d" % (ln, stats[ln]) for ln in sorted(stats.keys())))
            )

        if self.options.rememberCurveType:
            # 'lib' here is the layer's lib, as defined in for loop variable
            curve_type = lib.get(CURVE_TYPE_LIB_KEY, "cubic")
            if curve_type != "quadratic":
                lib[CURVE_TYPE_LIB_KEY] = "quadratic"

        return modified

    def filter(self, glyph):
        if not len(glyph):
            return False

        pen = Cu2QuPointPen(
            glyph.getPointPen(),
            self.context.absoluteError,
            reverse_direction=self.options.reverseDirection,
            stats=self.context.stats,
        )
        contours = list(glyph)
        glyph.clearContours()
        for contour in contours:
            contour.drawPoints(pen)
        return True
