from ufo2ft.constants import COLOR_LAYER_MAPPING_KEY, COLOR_LAYERS_KEY
from ufo2ft.filters import BaseFilter
from ufo2ft.util import _GlyphSet


class ExplodeColorLayerGlyphsFilter(BaseFilter):

    """This filter doesn't really filter glyphs, but copies glyphs
    from UFO layers to alternate glyphs in the default layer, for use
    in the COLR table.
    """

    def set_context(self, font, glyphSet):
        context = super().set_context(font, glyphSet)
        context.globalColorLayerMapping = font.lib.get(COLOR_LAYER_MAPPING_KEY)
        context.layerGlyphSets = {}
        context.colorLayerGlyphNames = set()  # glyph names that we added
        if COLOR_LAYERS_KEY not in font.lib:
            font.lib[COLOR_LAYERS_KEY] = {}
        else:
            # if the font already contains an explicit COLOR_LAYERS_KEY, we
            # assume the color layers have already been 'exploded' once.
            context.skipCurrentFont = True
        return context

    def _getLayer(self, font, layerName):
        layer = self.context.layerGlyphSets.get(layerName)
        if layer is None:
            layer = _GlyphSet.from_layer(font, layerName)
            self.context.layerGlyphSets[layerName] = layer
        return layer

    def _copyGlyph(self, layerGlyphSet, glyphSet, glyphName, layerName):
        layerGlyph = layerGlyphSet[glyphName]
        layerGlyphName = f"{glyphName}.{layerName}"
        if layerGlyphName in glyphSet:
            if layerGlyphName in self.context.colorLayerGlyphNames:
                # We've added this glyph already, so we're done
                return layerGlyphName
            from ufo2ft.errors import InvalidFontData

            raise InvalidFontData(
                f"a glyph named {layerGlyphName} already exists, "
                "conflicting with a requested color layer glyph."
            )
        for component in layerGlyph.components:
            baseLayerGlyphName = self._copyGlyph(
                layerGlyphSet, glyphSet, component.baseGlyph, layerName
            )
            component.baseGlyph = baseLayerGlyphName
        glyphSet[layerGlyphName] = layerGlyph
        self.context.colorLayerGlyphNames.add(layerGlyphName)
        return layerGlyphName

    def filter(self, glyph):
        if getattr(self.context, "skipCurrentFont", False):
            return False

        font = self.context.font
        glyphSet = self.context.glyphSet
        colorLayers = font.lib[COLOR_LAYERS_KEY]
        colorLayerMapping = glyph.lib.get(COLOR_LAYER_MAPPING_KEY)
        if colorLayerMapping is None:
            colorLayerMapping = self.context.globalColorLayerMapping
        if colorLayerMapping is None:
            # No color layer info for this glyph
            return False
        layers = []
        for layerName, colorID in colorLayerMapping:
            layerGlyphSet = self._getLayer(font, layerName)
            if glyph.name in layerGlyphSet:
                if glyph == layerGlyphSet[glyph.name]:
                    layerGlyphName = glyph.name
                else:
                    layerGlyphName = self._copyGlyph(
                        layerGlyphSet, glyphSet, glyph.name, layerName
                    )
                layers.append((layerGlyphName, colorID))
        if layers:
            colorLayers[glyph.name] = layers
            return True
        else:
            return False
