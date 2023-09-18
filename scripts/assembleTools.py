from pathops.operations import union
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPointPen


class DecomposingRecordingPointPen(RecordingPointPen):
    def __init__(self, glyphSet):
        super(DecomposingRecordingPointPen, self).__init__()
        self.glyphSet = glyphSet

    def addComponent(self, glyphName, transformation, identifier=None, **kwargs):
        glyph = self.glyphSet[glyphName]
        tPen = TransformPointPen(self, transformation)
        glyph.drawPoints(tPen)


def decomposeAndRemoveOverlaps(font):
    for glyph in font:
        decomposeComponents(glyph, font)
        removeOverlaps(glyph)


def decomposeComponents(glyph, font):
    recPen = DecomposingRecordingPointPen(font)
    glyph.drawPoints(recPen)
    glyph.clear()
    recPen.replay(glyph.getPointPen())


def fixFeatureIncludes(features):
    lines = features.splitlines()
    lines = [
        line.replace("include(features/", "include(../../sources/1-drawing/features/")
        for line in lines
    ]
    return "\n".join(lines) + "\n"


def removeOverlaps(glyph):
    recPen = RecordingPen()
    union(glyph.contours, recPen)
    glyph.clearContours()
    recPen.replay(glyph.getPen())


def reverseContours(glyph):
    recPen = RecordingPen()
    glyph.draw(ReverseContourPen(recPen))
    glyph.clear()
    recPen.replay(glyph.getPen())


def transformGlyph(glyph, transformation):
    recPen = RecordingPointPen()
    tPen = TransformPointPen(recPen, transformation)
    glyph.drawPoints(tPen)
    glyph.clear()
    recPen.replay(glyph.getPointPen())
