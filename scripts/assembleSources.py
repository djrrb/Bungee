import pathlib
from copy import deepcopy
from fontTools.misc.arrayTools import sectRect
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.pens.pointPen import PointToSegmentPen
import ufoLib2


from assembleTools import (
    DecomposingRecordingPointPen,
    decomposeComponents,
    fixFeatureIncludes,
    removeOverlaps,
    reverseContours,
)


def breakOutLayers(familyName, source, style, outputPath):
    styleName = style["styleName"]
    sourceFont = ufoLib2.Font.open(source)
    extraTracking = style.get("tracking", 0)
    trackingOffset = style.get("trackingOffset", 0)
    decomposeAllLayers = style.get("decompose", False)

    newFont = ufoLib2.Font()
    newFont.info = deepcopy(sourceFont.info)
    newFont.info.familyName = familyName
    newFont.info.styleName = styleName
    newFont.lib["public.glyphOrder"] = sourceFont.lib["public.glyphOrder"]
    newFont.kerning = sourceFont.kerning
    newFont.groups = sourceFont.groups
    newFont.features.text = fixFeatureIncludes(sourceFont.features.text)

    for glyph in sourceFont:
        sourceGlyph = sourceFont[glyph.name]
        newFont[glyph.name] = sourceGlyph.copy()
        newGlyph = newFont[glyph.name]
        newGlyph.clear()
        decomposeLayers = (
            (decomposeAllLayers and len(sourceGlyph.components) > 1)
            or bool(sourceGlyph.contours and sourceGlyph.components)
            or doCompomentsOverlap(sourceGlyph, sourceFont)
        )

        for i, layerName in enumerate(style["layers"]):
            if layerName not in sourceFont.layers:
                continue
            layer = sourceFont.layers[layerName]
            if glyph.name not in layer:
                if not glyph.components:
                    continue
                layerGlyph = sourceGlyph.copy()
            else:
                layerGlyph = layer[glyph.name].copy()
            if decomposeLayers:
                layerGlyph = layerGlyph.copy()
                layerGlyph.clearComponents()
                layerGlyph.components.extend(sourceGlyph.components)
                decomposeNestedComponents(layerGlyph, sourceFont)
                decomposeComponents(layerGlyph, layer)

            removeOverlaps(layerGlyph)
            if i % 2:
                reverseContours(layerGlyph)
            newGlyph.contours.extend(layerGlyph.contours)

        if not decomposeLayers:
            newGlyph.components.extend(sourceGlyph.components)

    if extraTracking:
        trackingAndOffset = {}
        for glyph in newFont:
            if glyph.name not in sourceFont.layers["shade"]:
                # No shade, no tracking
                t = o = 0
            elif ".v" in glyph.name or glyph.name.endswith("_v"):
                # No tracking, but adjust centering
                t = 0
                o = 65
            else:
                t = extraTracking
                o = trackingOffset
            trackingAndOffset[glyph.name] = (t, o)
        for glyph in newFont:
            t, o = trackingAndOffset[glyph.name]
            if o:
                moveGlyphHor(glyph, o)
            if t:
                glyph.width += t
            for compo in glyph.components:
                _, baseOffset = trackingAndOffset[compo.baseGlyph]
                x, y = compo.transformation[-2:]
                compo.transformation = compo.transformation[:4] + (x + o - baseOffset, y)

    newFont.save(outputPath, overwrite=True)


def doCompomentsOverlap(glyph, font):
    boxes = []
    for component in glyph.components:
        recPen = DecomposingRecordingPointPen(font)
        component.draw(recPen)
        bbPen = ControlBoundsPen(None)
        recPen.replay(PointToSegmentPen(bbPen))
        boxes.append(bbPen.bounds)

    if len(boxes) > 1:
        for ia in range(len(boxes) - 1):
            for ib in range(ia + 1, len(boxes)):
                boxA = boxes[ia]
                boxB = boxes[ib]
                doesIntersect, _ = sectRect(boxA, boxB)
                if doesIntersect:
                    return True

    return False


def decomposeNestedComponents(glyph, font):
    newComponents = []
    for component in glyph.components:
        compoGlyph = font[component.baseGlyph]
        parentTransform = Transform(*component.transformation)
        if compoGlyph.components:
            if compoGlyph.contours:
                return
            assert not compoGlyph.contours, (glyph.name, compoGlyph.name)
            compoGlyph = compoGlyph.copy()
            decomposeNestedComponents(compoGlyph, font)
            for nestedCompo in compoGlyph.components:
                nestedTransform = Transform(*nestedCompo.transformation)
                newComponents.append(
                    (nestedCompo.baseGlyph, parentTransform.transform(nestedTransform))
                )
        else:
            newComponents.append((component.baseGlyph, component.transformation))
    glyph.clearComponents()
    pen = glyph.getPen()
    for baseGlyph, t in newComponents:
        pen.addComponent(baseGlyph, t)


def moveGlyphHor(glyph, dx):
    for contour in glyph:
        for pt in contour.points:
            pt.x += dx


bungeeBasic = dict(
    familyName="Bungee",
    folderName="Bungee_Basic",
    source="sources/1-drawing/Bungee-Regular.ufo",
    styles=[
        dict(
            styleName="Regular",
            layers=["foreground"],
        ),
        dict(
            styleName="Hairline",
            layers=["inline"],
        ),
        dict(
            styleName="Inline",
            layers=["foreground", "inline"],
        ),
        dict(
            styleName="Outline",
            layers=["outline", "foreground", "inline"],
        ),
        dict(
            styleName="Shade",
            layers=["shade", "foreground", "inline"],
            tracking=100,
            trackingOffset=115,
            decompose=True,
        ),
    ],
)

layerStyles = [
    dict(
        styleName="Regular",
        layers=["foreground"],
    ),
    dict(
        styleName="Inline",
        layers=["inline"],
    ),
    dict(
        styleName="Outline",
        layers=["outline"],
    ),
    dict(
        styleName="Shade",
        layers=["shade"],
    ),
]

bungeeLayers = dict(
    familyName="Bungee Layers",
    source="sources/1-drawing/Bungee-Regular.ufo",
    styles=layerStyles,
)

bungeeLayersRotated = dict(
    familyName="Bungee Layers Rotated",
    source="sources/1-drawing/Bungee_Rotated-Regular.ufo",
    styles=layerStyles,
    features="vertical",
)

families = [
    bungeeBasic,
    bungeeLayers,
    # bungeeLayersRotated,
]


def main():
    repoDir = pathlib.Path(__file__).resolve().parent.parent
    buildDir = repoDir / "build"
    buildDir.mkdir(exist_ok=True)

    for family in families:
        familyName = family["familyName"]
        folderName = family.get("folderName", familyName.replace(" ", "_"))
        outputFolder = buildDir / folderName
        outputFolder.mkdir(exist_ok=True)
        sourcePath = repoDir / family["source"]
        baseFileName = familyName.replace(" ", "")
        for style in family["styles"]:
            styleName = style["styleName"]
            outputPath = outputFolder / f"{baseFileName}-{styleName}.ufo"
            print("assembling", outputPath.name)
            breakOutLayers(familyName, sourcePath, style, outputPath)


main()
