import logging
import math
from enum import IntEnum

from fontTools.misc.fixedTools import otRound
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.pens.transformPen import TransformPointPen as _TransformPointPen

from ufo2ft.filters import BaseFilter
from ufo2ft.fontInfoData import getAttrWithFallback

log = logging.getLogger(__name__)


class TransformPointPen(_TransformPointPen):
    def __init__(self, outPointPen, transformation, modified=None):
        super().__init__(outPointPen, transformation)
        self.modified = modified if modified is not None else set()
        self._inverted = self._transformation.inverse()

    def addComponent(self, baseGlyph, transformation, identifier=None, **kwargs):
        if baseGlyph in self.modified:
            # multiply the component's transformation matrix with the inverse
            # of the filter's transformation matrix to compensate for the
            # transformation already applied to the base glyph
            transformation = Transform(*transformation).transform(self._inverted)

        super().addComponent(baseGlyph, transformation, identifier=identifier, **kwargs)


class TransformationsFilter(BaseFilter):
    class Origin(IntEnum):
        CAP_HEIGHT = 0
        HALF_CAP_HEIGHT = 1
        X_HEIGHT = 2
        HALF_X_HEIGHT = 3
        BASELINE = 4

    _kwargs = {
        "OffsetX": 0,
        "OffsetY": 0,
        "ScaleX": 100,
        "ScaleY": 100,
        "Slant": 0,
        "Origin": 4,  # BASELINE
    }

    def start(self):
        self.options.Origin = self.Origin(self.options.Origin)

    def get_origin_height(self, font, origin):
        if origin is self.Origin.BASELINE:
            return 0
        elif origin is self.Origin.CAP_HEIGHT:
            return getAttrWithFallback(font.info, "capHeight")
        elif origin is self.Origin.HALF_CAP_HEIGHT:
            return otRound(getAttrWithFallback(font.info, "capHeight") / 2)
        elif origin is self.Origin.X_HEIGHT:
            return getAttrWithFallback(font.info, "xHeight")
        elif origin is self.Origin.HALF_X_HEIGHT:
            return otRound(getAttrWithFallback(font.info, "xHeight") / 2)
        else:
            raise AssertionError(origin)

    def set_context(self, font, glyphSet):
        ctx = super().set_context(font, glyphSet)

        origin_height = self.get_origin_height(font, self.options.Origin)

        m = Identity
        dx, dy = self.options.OffsetX, self.options.OffsetY
        if dx != 0 or dy != 0:
            m = m.translate(dx, dy)

        sx, sy = self.options.ScaleX, self.options.ScaleY
        angle = self.options.Slant
        # TODO Add support for "Cursify" option
        # cursify = self.options.SlantCorrection
        if sx != 100 or sy != 100 or angle != 0:
            # vertically shift glyph to the specified 'Origin' before
            # scaling and/or slanting, then move it back
            if origin_height != 0:
                m = m.translate(0, origin_height)
            if sx != 100 or sy != 100:
                m = m.scale(sx / 100, sy / 100)
            if angle != 0:
                m = m.skew(math.radians(angle))
            if origin_height != 0:
                m = m.translate(0, -origin_height)

        ctx.matrix = m

        return ctx

    def filter(self, glyph):
        matrix = self.context.matrix
        if matrix == Identity or not (glyph or glyph.components or glyph.anchors):
            return False  # nothing to do

        modified = self.context.modified
        glyphSet = self.context.glyphSet
        for component in glyph.components:
            base_name = component.baseGlyph
            if base_name in modified:
                continue
            base_glyph = glyphSet[base_name]
            if self.include(base_glyph) and self.filter(base_glyph):
                # base glyph is included but was not transformed yet; we
                # call filter recursively until all the included bases are
                # transformed, or there are no more components
                modified.add(base_name)

        rec = RecordingPointPen()
        glyph.drawPoints(rec)
        glyph.clearContours()
        glyph.clearComponents()

        outpen = glyph.getPointPen()
        filterpen = TransformPointPen(outpen, matrix, modified)
        rec.replay(filterpen)

        # anchors are not drawn through the pen API,
        # must be transformed separately
        for a in glyph.anchors:
            a.x, a.y = matrix.transformPoint((a.x, a.y))

        glyph.width, glyph.height = matrix.transformVector((glyph.width, glyph.height))

        return True
