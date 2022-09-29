import math
import pathlib
from copy import deepcopy
from fontTools.misc.transform import Transform
import ufoLib2


from assembleTools import (
    decomposeComponents,
    fixFeatureIncludes,
    transformGlyph,
)


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


def rotateTranslateGlyph(newGlyph):
    y = 360 - newGlyph.width / 2
    t = Transform()
    t = t.rotate(math.radians(90))
    t = t.translate(y, 0)
    transformGlyph(newGlyph, t)


verticalShapeExceptions = {
    # These are exceptions to the general "unverticalGlyphName" algorithm.
    #
    # - "v" glyphs that do *not* map to a non-v glyph, but to themselves:
    "uni25DD.curve_v": "uni25DD.curve_v",
    "uni2B24.salt_v": "uni2B24.salt_v",
    "uni2B1B.trapezoid_e_v": "uni2B1B.trapezoid_e_v",
    "uni2B1B.trapezoid_w_v": "uni2B1B.trapezoid_w_v",
    # - n(orth), e(ast), s(outh), w(est) mapping:
    "uni2B1B.semichevron_n": "uni2B1B.semichevron_e",
    "uni2B1B.semichevron_s": "uni2B1B.semichevron_w",
    "uni27A1.s": "uni27A1.w",
    "uni27A1.n": "uni27A1",
    # - Glyphs that also exist in unmapped form, but need to be ignored:
    "uni2B1B.semichevron_e": None,
    "uni2B1B.semichevron_w": None,
    "uni27A1.w": None,
    "uni27A1": None,
    "uni25D6.wings": None,
    "uni25D7.wings": None,
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
