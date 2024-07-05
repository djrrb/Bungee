import pathlib
from copy import deepcopy
from fontTools.misc.arrayTools import sectRect
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.pens.pointPen import PointToSegmentPen
import ufoLib2


from assembleTools import (
    computeWinAscentDescent,
    DecomposingRecordingPointPen,
    decomposeComponents,
    fixFeatureIncludes,
    removeOverlaps,
    reverseContours,
)

repoDir = pathlib.Path(__file__).resolve().parent.parent


def breakOutLayers(familyName, source, style, outputPath):
    styleName = style["styleName"]
    sourceFont = ufoLib2.Font.open(source)
    extraTracking = style.get("tracking", 0)
    trackingOffset = style.get("trackingOffset", 0)
    decomposeAllLayers = style.get("decompose", False)
    deleteAnchors = style.get("deleteAnchors", False)

    exceptionsSourcePath = style.get("exceptionsSource")
    exceptionsFont = (
        ufoLib2.Font.open(repoDir / exceptionsSourcePath)
        if exceptionsSourcePath is not None
        else None
    )

    newFont = ufoLib2.Font()
    newFont.info = deepcopy(sourceFont.info)
    newFont.info.familyName = familyName
    newFont.info.styleName = styleName
    newFont.lib["public.glyphOrder"] = sourceFont.lib["public.glyphOrder"]
    newFont.lib["public.openTypeMeta"] = sourceFont.lib["public.openTypeMeta"]
    newFont.kerning = sourceFont.kerning
    newFont.groups = sourceFont.groups
    newFont.features.text = fixFeatureIncludes(sourceFont.features.text)

    for glyph in sourceFont:
        sourceGlyph = sourceFont[glyph.name]
        newFont[glyph.name] = sourceGlyph.copy()
        newGlyph = newFont[glyph.name]
        newGlyph.clearContours()
        newGlyph.clearComponents()
        newGlyph.clearGuidelines()

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
        shadeLayer = sourceFont.layers["shade"]
        for glyph in newFont:
            if glyph.name not in basicShadeTrackingExceptions and not any(
                n in shadeLayer
                for n in allUsedGlyphNames(sourceFont[glyph.name], sourceFont)
            ):
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
                compo.transformation = compo.transformation[:4] + (
                    x + o - baseOffset,
                    y,
                )
    # Insert exceptions
    if exceptionsFont is not None:
        for glyph in exceptionsFont:
            sourceGlyph = exceptionsFont[glyph.name]
            newFont[glyph.name] = sourceGlyph.copy()

    if deleteAnchors:
        for glyph in newFont:
            glyph.clearAnchors()

    computeWinAscentDescent(newFont)
    newFont.save(outputPath, overwrite=True)


# The following glyphs need tracking + offsetting in Bungee Basic Shade,
# despite not having a shade themselves. But they have related glyphs
# with shade. Except space.
basicShadeTrackingExceptions = {
    "space",
    "indexdownleft.outline",
    "indexdownleft.salt_outline",
    "indexdownright.outline",
    "indexdownright.salt_outline",
    "indexupleft.outline",
    "indexupleft.salt_outline",
    "indexupright.outline",
    "indexupright.salt_outline",
    "uni261C",
    "uni261C.salt",
    "uni261D",
    "uni261D.salt",
    "uni261E",
    "uni261E.salt",
    "uni261F",
    "uni261F.salt",
    "whitedownpointingtriangle",
    "whiteleftpointingtriangle",
    "whiterightpointingtriangle",
    "whiteuppointingtriangle",
}


def allUsedGlyphNames(glyph, font):
    names = {glyph.name}
    for compo in glyph.components:
        names.update(allUsedGlyphNames(font[compo.baseGlyph], font))
    return names


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
    folderName="Bungee_Basic",
    source="sources/1-drawing/Bungee-Regular.ufo",
    styles=[
        dict(
            familyName="Bungee",
            styleName="Regular",
            layers=["foreground"],
        ),
        dict(
            familyName="Bungee Hairline",
            styleName="Regular",
            layers=["inline"],
        ),
        dict(
            familyName="Bungee Inline",
            styleName="Regular",
            layers=["foreground", "inline"],
        ),
        dict(
            familyName="Bungee Outline",
            styleName="Regular",
            layers=["outline", "foreground", "inline"],
        ),
        dict(
            familyName="Bungee Shade",
            styleName="Regular",
            layers=["shade", "foreground", "inline"],
            tracking=100,
            trackingOffset=115,
            decompose=True,
            deleteAnchors=True,
            exceptionsSource="sources/1-drawing/Bungee-Shade-Exceptions.ufo",
        ),
    ],
)

layerStyles = [
    dict(
        familyName="Bungee Layers",
        styleName="Regular",
        layers=["foreground"],
    ),
    dict(
        familyName="Bungee Layers Inline",
        styleName="Regular",
        layers=["inline"],
    ),
    dict(
        familyName="Bungee Layers Outline",
        styleName="Regular",
        layers=["outline"],
    ),
    dict(
        familyName="Bungee Layers Shade",
        styleName="Regular",
        layers=["shade"],
    ),
]

bungeeLayers = dict(
    folderName="Bungee_Layers",
    source="sources/1-drawing/Bungee-Regular.ufo",
    styles=layerStyles,
)


families = [
    bungeeBasic,
    bungeeLayers,
]


def main():
    buildDir = repoDir / "build"
    buildDir.mkdir(exist_ok=True)

    for family in families:
        folderName = family["folderName"]
        outputFolder = buildDir / folderName
        outputFolder.mkdir(exist_ok=True)
        sourcePath = repoDir / family["source"]
        for style in family["styles"]:
            familyName = style["familyName"]
            baseFileName = familyName.replace(" ", "")
            styleName = style["styleName"]
            outputPath = outputFolder / f"{baseFileName}-{styleName}.ufo"
            print("assembling", outputPath.name)
            breakOutLayers(familyName, sourcePath, style, outputPath)


main()
