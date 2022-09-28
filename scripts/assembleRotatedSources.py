import math
import pathlib
from copy import deepcopy
from fontTools.misc.transform import Transform
from pathops.operations import union
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPointPen
import ufoLib2


def fixFeatureIncludes(features):
    lines = features.splitlines()
    lines = [
        line.replace("include(features/", "include(../../sources/1-drawing/features/")
        for line in lines
    ]
    return "\n".join(lines) + "\n"


def componentDepth(glyphName, font):
    glyph = font[glyphName]
    if not glyph.components:
        return 0
    return 1 + max(componentDepth(compo.baseGlyph, font) for compo in glyph.components)


def getLowerCaseGlyphNames(font):
    cmap = {g.unicode: g.name for g in font if g.unicode}
    lcGlyphNames = set()
    for uni, glyphName in sorted(cmap.items()):
        char = chr(uni)
        charUC = char.upper()
        if char != charUC:
            if len(charUC) == 1:
                uniUC = ord(charUC)
                if uniUC in cmap:
                    lcGlyphNames.add(glyphName)
            else:
                # That one exception tho
                assert charUC == "SS", charUC
                assert glyphName == "germandbls"
                assert ord("\N{LATIN CAPITAL LETTER SHARP S}") in cmap
                lcGlyphNames.add(glyphName)
    return lcGlyphNames


class DecomposingRecordingPointPen(RecordingPointPen):
    def __init__(self, glyphSet):
        super(DecomposingRecordingPointPen, self).__init__()
        self.glyphSet = glyphSet

    def addComponent(self, glyphName, transformation, identifier=None, **kwargs):
        glyph = self.glyphSet[glyphName]
        tPen = TransformPointPen(self, transformation)
        glyph.drawPoints(tPen)


def decomposeComponents(glyph, font):
    recPen = DecomposingRecordingPointPen(font)
    glyph.drawPoints(recPen)
    glyph.clear()
    recPen.replay(glyph.getPointPen())


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


def rotateTranslateGlyph(newGlyph):
    y = 360 - newGlyph.width / 2
    t = Transform()
    t = t.rotate(math.radians(90))
    t = t.translate(y, 0)
    transformGlyph(newGlyph, t)


def transformGlyph(glyph, transformation):
    recPen = RecordingPointPen()
    tPen = TransformPointPen(recPen, transformation)
    glyph.drawPoints(tPen)
    glyph.clear()
    recPen.replay(glyph.getPointPen())


verticalShapeExceptions = {
    "uni25DD.curve_v": "uni25DD.curve_v",  # maps to itself
    "uni2B24.salt_v": "uni2B24.salt_v",  # maps to itself
    "uni2B1B.trapezoid_e": "uni2B1B.trapezoid_e",
    "uni2B1B.trapezoid_e_v": "uni2B1B.trapezoid_e_v",
    "uni2B1B.trapezoid_w": "uni2B1B.trapezoid_w",
    "uni2B1B.trapezoid_w_v": "uni2B1B.trapezoid_w_v",
    "uni2B1B.semichevron_e": "uni2B1B.semichevron_e",
    "uni2B1B.semichevron_w": "uni2B1B.semichevron_w",
    "uni2B1B.semichevron_n": "uni2B1B.semichevron_n",
    "uni2B1B.semichevron_s": "uni2B1B.semichevron_s",
    "uni2B1B.chevron_w": "uni2B1B.chevron_w",
    "uni2B1B.chevron_e": "uni2B1B.chevron_e",
    "uni2B1B.chevron_n": "uni2B1B.chevron_n",
    "uni2B1B.chevron_s": "uni2B1B.chevron_s",
    "uni27A1.w": "uni27A1.w",
    "uni27A1": "uni27A1",  # ????
    "uni27A1.s": "uni27A1.s",
    "uni27A1.n": "uni27A1.n",
}


def unverticalGlyphName(glyphName):
    if glyphName in verticalShapeExceptions:
        newName = verticalShapeExceptions[glyphName]
    elif ".v_" in glyphName:
        newName = glyphName.replace(".v_", ".")
    elif "_v" in glyphName:
        newName = glyphName.replace("_v", "")
    elif glyphName.endswith(".v"):
        newName = glyphName.replace(".v", "")
    else:
        newName = glyphName
    return newName


def computeOffsetsAndWidths(
    rotatedGlyphNames, glyphNameMapping, rotatedSourceFont, regularSourceFont
):
    offsetsAndWidths = {}
    for destGlyphName in rotatedGlyphNames:
        sourceGlyphName = glyphNameMapping[destGlyphName]

        rotatedGlyph = rotatedSourceFont[destGlyphName]
        regularGlyph = regularSourceFont[sourceGlyphName]

        rotatedBounds = rotatedGlyph.getControlBounds(rotatedSourceFont) or (0, 0, 0, 0)
        regularBounds = regularGlyph.getControlBounds(regularSourceFont) or (0, 0, 0, 0)
        xMinRot, _, xMaxRot, _ = rotatedBounds
        _, yMinReg, _, yMaxReg = regularBounds
        leftMargin = xMinRot
        rightMargin = rotatedGlyph.width - xMaxRot

        xOffset = yMaxReg + leftMargin
        yOffset = 360 - regularGlyph.width / 2
        widthRot = leftMargin + (yMaxReg - yMinReg) + rightMargin
        offsetsAndWidths[destGlyphName] = xOffset, yOffset, widthRot
    return offsetsAndWidths


def main():
    repoDir = pathlib.Path(__file__).resolve().parent.parent
    layerDir = repoDir / "build" / "Bungee_Layers"
    outputDir = repoDir / "build" / "Bungee_Rotated"
    outputDir.mkdir(exist_ok=True)

    rotatedSourcePath = repoDir / "sources" / "1-drawing" / "Bungee_Rotated-Regular.ufo"
    regularSourcePath = layerDir / "BungeeLayers-Regular.ufo"

    rotatedSourceFont = ufoLib2.Font.open(rotatedSourcePath)
    regularSourceFont = ufoLib2.Font.open(regularSourcePath)

    rotatedGlyphNames = {glyph.name for glyph in rotatedSourceFont}

    lcGlyphNames = getLowerCaseGlyphNames(rotatedSourceFont)

    glyphNameMapping = {}
    for glyph in regularSourceFont:
        sourceGlyphName = glyph.name
        destGlyphName = unverticalGlyphName(sourceGlyphName)
        if destGlyphName in rotatedGlyphNames:
            glyphNameMapping[destGlyphName] = sourceGlyphName

    glyphOrder = [
        glyphName
        for glyphName in rotatedSourceFont.lib["public.glyphOrder"]
        if glyphName in rotatedGlyphNames
    ]
    assert len(glyphOrder) == len(rotatedGlyphNames)

    rotatedGlyphNames = sorted(rotatedGlyphNames)

    offsetsAndWidths = computeOffsetsAndWidths(
        rotatedGlyphNames, glyphNameMapping, rotatedSourceFont, regularSourceFont
    )

    for styleName in ["Regular", "Inline", "Outline", "Shade"]:
        outputPath = outputDir / f"BungeeRotated-{styleName}.ufo"
        print("assembling", outputPath.name)
        outputFont = ufoLib2.Font()
        if styleName == "Regular":
            layerSourceFont = regularSourceFont
        else:
            layerFontPath = layerDir / f"BungeeLayers-{styleName}.ufo"
            layerSourceFont = ufoLib2.Font.open(layerFontPath)

        outputFont.info = deepcopy(rotatedSourceFont.info)
        outputFont.info.styleName = styleName
        outputFont.lib["public.glyphOrder"] = glyphOrder
        outputFont.groups = rotatedSourceFont.groups
        outputFont.kerning = rotatedSourceFont.kerning
        outputFont.features.text = fixFeatureIncludes(rotatedSourceFont.features.text)

        for destGlyphName in rotatedGlyphNames:
            sourceGlyphName = glyphNameMapping[destGlyphName]
            sourceGlyph = deepcopy(layerSourceFont[sourceGlyphName])

            for compo in sourceGlyph.components:
                if compo.baseGlyph == destGlyphName:
                    # Component would reference itself, decompose
                    decomposeComponents(sourceGlyph, layerSourceFont)
                    break

            outputFont[destGlyphName] = sourceGlyph
            newGlyph = outputFont[destGlyphName]
            newGlyph.unicodes = rotatedSourceFont[destGlyphName].unicodes

            for compo in newGlyph.components:
                compo.baseGlyph = unverticalGlyphName(compo.baseGlyph)

            if destGlyphName in lcGlyphNames:
                # Fix lowercase width
                assert len(newGlyph.components) == 1
                compo = newGlyph.components[0]
                assert compo.transformation == (1, 0, 0, 1, 0, 0)
                _, _, widthRot = offsetsAndWidths[compo.baseGlyph]
                newGlyph.width = widthRot
            else:
                xOffset, yOffset, widthRot = offsetsAndWidths[destGlyphName]
                t = Transform()
                t = t.rotate(math.radians(90))
                t = t.translate(yOffset, -xOffset)

                if newGlyph.contours:
                    assert not newGlyph.components, "can't mix outlines and components"
                    transformGlyph(newGlyph, t)
                else:
                    # Compensate component origins based on how the base glyphs moved
                    for compo in newGlyph.components:
                        assert compo.transformation[:4] == (1, 0, 0, 1)
                        xOffset, yOffset, _ = offsetsAndWidths[compo.baseGlyph]
                        x, y = t.transformPoint(compo.transformation[4:])
                        compo.transformation = (1, 0, 0, 1, x - xOffset, y - yOffset)

                newGlyph.width = widthRot

        outputFont.save(outputPath, overwrite=True)


main()
