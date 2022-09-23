import os
import pathlib
from copy import deepcopy
from pathops.operations import union
from fontTools.misc.arrayTools import sectRect
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPointPen
import ufoLib2


def breakOutLayers(familyName, source, style, outputFolder):
    styleName = style["styleName"]
    sourceFont = ufoLib2.Font.open(source)
    folderName = familyName.replace(" ", "_")
    extraTracking = style.get("tracking", 0)
    offset = style.get("offset", 0)
    decomposeAllLayers = style.get("decompose", False)
    newFont = ufoLib2.Font()
    newFont.info = deepcopy(sourceFont.info)
    newFont.lib["public.glyphOrder"] = sourceFont.lib["public.glyphOrder"]

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
        for glyph in newFont:
            moveGlyphHor(glyph, extraTracking + offset)
            glyph.width += extraTracking

    if os.path.exists(outputFolder):
        None
    else:
        os.makedirs(outputFolder)

    fileName = f"{outputFolder}/{folderName}-{styleName}.ufo"
    newFont.save(fileName, overwrite=True)


class DecomposingRecordingPointPen(RecordingPointPen):
    def __init__(self, glyphSet):
        super(DecomposingRecordingPointPen, self).__init__()
        self.glyphSet = glyphSet

    def addComponent(self, glyphName, transformation, identifier=None, **kwargs):
        glyph = self.glyphSet[glyphName]
        tPen = TransformPointPen(self, transformation)
        glyph.drawPoints(tPen)


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


def decomposeComponents(glyph, font):
    recPen = DecomposingRecordingPointPen(font)
    glyph.drawPoints(recPen)
    glyph.clear()
    recPen.replay(glyph.getPointPen())


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


def removeOverlaps(glyph):
    recPen = RecordingPen()
    union(glyph.contours, recPen)
    glyph.clearContours()
    recPen.replay(glyph.getPen())


def decomposeAndRemoveOverlaps(font):
    for glyph in font:
        decomposeComponents(glyph, font)
        removeOverlaps(glyph)


def reverseContours(glyph):
    recPen = RecordingPen()
    glyph.draw(ReverseContourPen(recPen))
    glyph.clear()
    recPen.replay(glyph.getPen())


bungeeBasic = dict(
    familyName="Bungee",
    folderName="Bungee_Basic",
    source="sources/1-drawing/Bungee-Regular.ufo",
    styles=[
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
            offset=15,
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
        tracking=100,
        offset=15,
        decompose=True,
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
        source = family["source"]
        for style in family["styles"]:
            breakOutLayers(familyName, source, style, outputFolder)


main()
