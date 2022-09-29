from fontTools.misc.transform import Transform

import ufo2ft.util
from ufo2ft.filters import BaseFilter


class DecomposeComponentsFilter(BaseFilter):
    def filter(self, glyph):
        if not glyph.components:
            return False
        ufo2ft.util.deepCopyContours(self.context.glyphSet, glyph, glyph, Transform())
        glyph.clearComponents()
        return True
