import pathlib
import ufoLib2
from ufo2ft.constants import COLOR_LAYERS_KEY, COLOR_PALETTES_KEY


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

colorTable = """
    regular     C90900  FFFFFF  23849F  666666  0B5BA8  EFBB43  FFDA99  FFE10B
    inline      FF9580  E8E8E7  F6EECD  DCF676  55A5FE  EAE2B1  FF5140  FF0035
"""

colorGlyphs = {}
palettes, colorIndices = parseColorTable(colorTable)

repoDir = pathlib.Path(__file__).resolve().parent.parent
layersDir = repoDir / "build" / "Bungee_Layers"

sourceFont = ufoLib2.Font.open(layersDir / "BungeeLayers-Regular.ufo")
inlineFont = ufoLib2.Font.open(layersDir / "BungeeLayers-Inline.ufo")


for glyph in inlineFont:
    inlineGlyphName = glyph.name + inlineSuffix
    sourceFont[inlineGlyphName] = inlineFont[glyph.name].copy()
    inlineGlyph = sourceFont[inlineGlyphName]
    inlineGlyph.unicode = None

    for compo in inlineGlyph.components:
        inlineBaseGlyph = compo.baseGlyph + inlineSuffix
        compo.baseGlyph = inlineBaseGlyph

    colorGlyphs[glyph.name] = [(glyph.name, 0), (inlineGlyphName, 1)]


sourceFont.lib[COLOR_PALETTES_KEY] = palettes
sourceFont.lib[COLOR_LAYERS_KEY] = colorGlyphs
sourceFont.info.familyName = "Bungee Color"
sourceFont.info.styleName = "Regular"

outputPath = repoDir / "build" / "Bungee_Color" / "BungeeColor-Regular-COLRv0.ufo"
sourceFont.save(outputPath, overwrite=True)
