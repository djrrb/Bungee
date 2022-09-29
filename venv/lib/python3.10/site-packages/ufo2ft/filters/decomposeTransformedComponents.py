from fontTools.misc.transform import Identity, Transform

import ufo2ft.util
from ufo2ft.filters import BaseFilter


class DecomposeTransformedComponentsFilter(BaseFilter):
    def filter(self, glyph):
        if not glyph.components:
            return False
        needs_decomposition = False
        for component in glyph.components:
            if component.transformation[:4] != Identity[:4]:
                needs_decomposition = True
                break
        if not needs_decomposition:
            return False
        ufo2ft.util.deepCopyContours(self.context.glyphSet, glyph, glyph, Transform())
        glyph.clearComponents()
        return True
