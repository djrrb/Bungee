from freetype.raw import *
from enum import IntEnum


class FTHintMode(IntEnum):
    """Set FreeType hinting mode."""
    # This enum contains flag combinations which are used in the
    # FT_Load_Glyph function. We recommend using this enum instead of
    # providing the flags yourself because the combinations below are
    # known to work well together.
    # https://www.freetype.org/freetype2/docs/reference/ft2-base_interface.html#ft_load_xxx
    NORMAL = FT_LOAD_TARGET_NORMAL | FT_LOAD_RENDER
    UNHINTED = FT_LOAD_NO_HINTING | FT_LOAD_RENDER
    LIGHT = FT_LOAD_TARGET_LIGHT | FT_LOAD_RENDER
