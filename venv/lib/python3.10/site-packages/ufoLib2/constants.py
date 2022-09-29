from __future__ import annotations

DEFAULT_LAYER_NAME: str = "public.default"
"""The name of the default layer."""

OBJECT_LIBS_KEY: str = "public.objectLibs"
"""The lib key for object libs.

See:

- https://unifiedfontobject.org/versions/ufo3/lib.plist/#publicobjectlibs
- https://unifiedfontobject.org/versions/ufo3/glyphs/glif/#publicobjectlibs
"""

DATA_LIB_KEY = "com.github.fonttools.ufoLib2.lib.plist.data"
"""
Lib key used for serializing binary data as JSON-encodable string.
"""
