import pathlib
from fontTools.ttLib.tables import otTables as ot
import ufoLib2
from ufo2ft.constants import COLOR_LAYERS_KEY, COLOR_PALETTES_KEY

from assembleTools import computeWinAscentDescent


def parseColorTable(colorTable):
    colorNames = []
    colors = []
    for line in colorTable.splitlines():
        line = line.strip()
        if not line:
            continue
        colorName, *hexColors = line.split()
        colorNames.append(colorName)
        colors.append([colorFromHex(hexColor) for hexColor in hexColors])

    palettes = [list(palette) for palette in zip(*colors)]
    colorIndices = {colorName: i for i, colorName in enumerate(colorNames)}
    return palettes, colorIndices


def colorFromHex(hexString):
    assert len(hexString) in [6, 8]
    channels = []
    for i in range(0, len(hexString), 2):
        channels.append(int(hexString[i : i + 2], 16) / 255)
    if len(channels) == 3:
        channels.append(1)
    return channels


inlineSuffix = ".inline"

colorTableRegular = """
    regular     C90900  FFFFFF  23849F  666666  0B5BA8  EFBB43  FFDA99  FFE10B
    inline      FF9580  E8E8E7  F6EECD  DCF676  55A5FE  EAE2B1  FF5140  FF0035
"""

colorTableSpice = """
    color1     C90900  132A66  038F60
    color2     FFD700  60A0EF  ABFE37
"""


palettesRegular, colorIndexRegular = parseColorTable(colorTableRegular)
palettesSpice, colorIndexSpice = parseColorTable(colorTableSpice)

gradient_color1 = colorIndexSpice["color1"]
gradient_color2 = colorIndexSpice["color2"]


gradient_color1_color2 = {
    "Format": ot.PaintFormat.PaintLinearGradient,
    "ColorLine": {
        "ColorStop": [(0.0, gradient_color1), (1.0, gradient_color2)],
        "Extend": "reflect",
    },
    "x0": 0,
    "y0": 0,
    "x1": 0,
    "y1": 900,
    "x2": 100,
    "y2": 0,
}

gradient_color2_color1 = {
    "Format": ot.PaintFormat.PaintLinearGradient,
    "ColorLine": {
        "ColorStop": [(0.0, gradient_color2), (1.0, gradient_color1)],
        "Extend": "reflect",
    },
    "x0": 0,
    "y0": 0,
    "x1": 0,
    "y1": 900,
    "x2": 100,
    "y2": 0,
}

repoDir = pathlib.Path(__file__).resolve().parent.parent
layersDir = repoDir / "build" / "Bungee_Layers"
outputDir = repoDir / "build" / "Bungee_Color"
outputDir.mkdir(exist_ok=True)

sourceFont = ufoLib2.Font.open(layersDir / "BungeeLayers-Regular.ufo")
inlineFont = ufoLib2.Font.open(layersDir / "BungeeLayersInline-Regular.ufo")

colorGlyphsRegular = {}
colorGlyphsSpice = {}

for glyph in inlineFont:
    inlineGlyphName = glyph.name + inlineSuffix
    sourceFont[inlineGlyphName] = inlineFont[glyph.name].copy()
    inlineGlyph = sourceFont[inlineGlyphName]
    inlineGlyph.unicode = None

    for compo in inlineGlyph.components:
        inlineBaseGlyph = compo.baseGlyph + inlineSuffix
        compo.baseGlyph = inlineBaseGlyph

    colorGlyphsRegular[glyph.name] = [
        (glyph.name, colorIndexRegular["regular"]),
        (inlineGlyphName, colorIndexRegular["inline"]),
    ]

    gradientLayers = [
        {
            "Format": ot.PaintFormat.PaintGlyph,
            "Paint": gradient_color2_color1 if suffix else gradient_color1_color2,
            "Glyph": glyph.name + suffix,
        }
        for suffix in ["", inlineSuffix]
    ]
    colorGlyphsSpice[glyph.name] = (ot.PaintFormat.PaintColrLayers, gradientLayers)


sourceFont.lib[COLOR_PALETTES_KEY] = palettesRegular
sourceFont.lib[COLOR_LAYERS_KEY] = colorGlyphsRegular
sourceFont.info.familyName = "Bungee Color"
sourceFont.info.styleName = "Regular"

sourceFont.save(outputDir / "BungeeColor-Regular.ufo", overwrite=True)

sourceFont.lib[COLOR_PALETTES_KEY] = palettesSpice
sourceFont.lib[COLOR_LAYERS_KEY] = colorGlyphsSpice
sourceFont.info.familyName = "Bungee Spice"
sourceFont.info.styleName = "Regular"

computeWinAscentDescent(sourceFont)
sourceFont.save(outputDir / "BungeeSpice-Regular.ufo", overwrite=True)
