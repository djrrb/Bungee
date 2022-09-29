from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    KeysView,
    Optional,
    Sequence,
    Type,
    overload,
)

from attr import define, field
from fontTools.ufoLib.glifLib import GlyphSet

from ufoLib2.constants import DEFAULT_LAYER_NAME
from ufoLib2.objects.glyph import Glyph
from ufoLib2.objects.lib import Lib, _convert_Lib, _get_lib, _set_lib
from ufoLib2.objects.misc import (
    BoundingBox,
    _deepcopy_unlazify_attrs,
    _prune_object_libs,
    unionBounds,
)
from ufoLib2.typing import T

if TYPE_CHECKING:
    from cattr import GenConverter

_GLYPH_NOT_LOADED = Glyph(name="___UFOLIB2_LAZY_GLYPH___")


def _convert_glyphs(value: dict[str, Glyph] | Sequence[Glyph]) -> dict[str, Glyph]:
    result: dict[str, Glyph] = {}
    if isinstance(value, dict):
        glyph_ids = set()
        for name, glyph in value.items():
            if not isinstance(glyph, Glyph):
                raise TypeError(f"Expected Glyph, found {type(glyph).__name__}")
            if glyph is not _GLYPH_NOT_LOADED:
                glyph_id = id(glyph)
                if glyph_id in glyph_ids:
                    raise KeyError(f"{glyph!r} can't be added twice")
                glyph_ids.add(glyph_id)
                if glyph.name is None:
                    glyph._name = name
                elif glyph.name != name:
                    raise ValueError(
                        "glyph has incorrect name: "
                        f"expected '{name}', found '{glyph.name}'"
                    )
            result[name] = glyph
    else:
        for glyph in value:
            if not isinstance(glyph, Glyph):
                raise TypeError(f"Expected Glyph, found {type(glyph).__name__}")
            if glyph.name is None:
                raise ValueError(f"{glyph!r} has no name; can't add it to Layer")
            if glyph.name in result:
                raise KeyError(f"glyph named '{glyph.name}' already exists")
            result[glyph.name] = glyph
    return result


@define
class Layer:
    """Represents a Layer that holds Glyph objects.

    See http://unifiedfontobject.org/versions/ufo3/glyphs/layerinfo.plist/.

    Note:
        Various methods that work on Glyph objects take a ``layer`` attribute, because
        the UFO data model prescribes that Components within a Glyph object refer to
        glyphs *within the same layer*.

    Behavior:
        Layer behaves **partly** like a dictionary of type ``Dict[str, Glyph]``.
        Unless the font is loaded eagerly (with ``lazy=False``), the Glyph objects
        by default are only loaded into memory when accessed.

        To get the number of glyphs in the layer::

            glyphCount = len(layer)

        To iterate over all glyphs::

            for glyph in layer:
                ...

        To check if a specific glyph exists::

            exists = "myGlyphName" in layer

        To get a specific glyph::

            layer["myGlyphName"]

        To delete a specific glyph::

            del layer["myGlyphName"]
    """

    _name: str = field(default=DEFAULT_LAYER_NAME, metadata={"omit_if_default": False})
    _glyphs: Dict[str, Glyph] = field(factory=dict, converter=_convert_glyphs)
    color: Optional[str] = None
    """The color assigned to the layer."""

    _lib: Lib = field(factory=Lib, converter=_convert_Lib)
    """The layer's lib for mapping string keys to arbitrary data."""

    _default: bool = False
    """Can set to True to mark a layer as default. If layer name is 'public.default'
    the default attribute is automatically True. Exactly one layer must be marked as
    default in a font."""

    _glyphSet: Any = field(default=None, init=False, eq=False)

    def __attrs_post_init__(self) -> None:
        if self._name == DEFAULT_LAYER_NAME and not self._default:
            # layer named 'public.default' is default by definition
            self._default = True

    @classmethod
    def read(
        cls, name: str, glyphSet: GlyphSet, lazy: bool = True, default: bool = False
    ) -> Layer:
        """Instantiates a Layer object from a
        :class:`fontTools.ufoLib.glifLib.GlyphSet`.

        Args:
            name: The name of the layer.
            glyphSet: The GlyphSet object to read from.
            lazy: If True, load glyphs as they are accessed. If False, load everything
                up front.
        """
        glyphNames = glyphSet.keys()
        glyphs: dict[str, Glyph]
        if lazy:
            glyphs = {gn: _GLYPH_NOT_LOADED for gn in glyphNames}
        else:
            glyphs = {}
            for glyphName in glyphNames:
                glyph = Glyph(glyphName)
                glyphSet.readGlyph(glyphName, glyph, glyph.getPointPen())
                glyphs[glyphName] = glyph
        self = cls(name, glyphs, default=default)
        if lazy:
            self._glyphSet = glyphSet
        glyphSet.readLayerInfo(self)
        return self

    def unlazify(self) -> None:
        """Load all glyphs into memory."""
        for _ in self:
            pass

    __deepcopy__ = _deepcopy_unlazify_attrs

    def __contains__(self, name: object) -> bool:
        return name in self._glyphs

    def __delitem__(self, name: str) -> None:
        del self._glyphs[name]

    def __getitem__(self, name: str) -> Glyph:
        glyph_object = self._glyphs[name]
        if glyph_object is _GLYPH_NOT_LOADED:
            return self.loadGlyph(name)
        return glyph_object

    def __setitem__(self, name: str, glyph: Glyph) -> None:
        if not isinstance(glyph, Glyph):
            raise TypeError(f"Expected Glyph, found {type(glyph).__name__}")
        glyph._name = name
        self._glyphs[name] = glyph

    def __iter__(self) -> Iterator[Glyph]:
        for name in self._glyphs:
            yield self[name]

    def __len__(self) -> int:
        return len(self._glyphs)

    def __repr__(self) -> str:
        n = len(self._glyphs)
        return "<{}.{} '{}' ({}{}) at {}>".format(
            self.__class__.__module__,
            self.__class__.__name__,
            self._name,
            "default, " if self._default else "",
            "empty" if n == 0 else "{} glyph{}".format(n, "s" if n > 1 else ""),
            hex(id(self)),
        )

    def get(self, name: str, default: T | None = None) -> T | Glyph | None:
        """Return the Glyph object for name if it is present in this layer,
        otherwise return ``default``."""
        try:
            return self[name]
        except KeyError:
            return default

    def keys(self) -> KeysView[str]:
        """Returns a list of glyph names."""
        return self._glyphs.keys()

    @overload
    def pop(self, key: str) -> Glyph:
        ...

    @overload
    def pop(self, key: str, default: Glyph | T = ...) -> Glyph | T:
        ...

    def pop(self, key: str, default: Glyph | T = KeyError) -> Glyph | T:  # type: ignore
        """Remove and return glyph from layer.

        Args:
            key: The name of the glyph.
            default: What to return if there is no glyph with the given name.
        """
        # NOTE: We can't defer to self._glyphs.pop because we must load glyphs
        try:
            glyph = self[key]
        except KeyError:
            if default is KeyError:
                raise
            glyph = default  # type: ignore
        else:
            del self[key]
        return glyph

    @property
    def name(self) -> str:
        """The name of the layer."""
        return self._name

    lib = property(_get_lib, _set_lib)

    @property
    def default(self) -> bool:
        """Read-only property. To change the font's default layer use the
        LayerSet.defaultLayer property setter."""
        return self._default

    @property
    def bounds(self) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the layer,
        taking the actual contours into account.

        |defcon_compat|
        """
        bounds = None
        for glyph in self:
            bounds = unionBounds(bounds, glyph.getBounds(self))
        return bounds

    @property
    def controlPointBounds(self) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the layer,
        taking only the control points into account.

        |defcon_compat|
        """
        bounds = None
        for glyph in self:
            bounds = unionBounds(bounds, glyph.getControlBounds(self))
        return bounds

    def addGlyph(self, glyph: Glyph) -> None:
        """Appends glyph object to the this layer unless its name is already
        taken."""
        self.insertGlyph(glyph, overwrite=False, copy=False)

    def insertGlyph(
        self,
        glyph: Glyph,
        name: str | None = None,
        overwrite: bool = True,
        copy: bool = True,
    ) -> None:
        """Inserts Glyph object into this layer.

        Args:
            glyph: The Glyph object.
            name: The name of the glyph.
            overwrite: If True, overwrites (read: deletes) glyph with the same name if
                it exists. If False, raises KeyError.
            copy: If True, copies the Glyph object before insertion. If False, inserts
                as is.
        """
        if copy:
            glyph = glyph.copy()
        if name is not None:
            glyph._name = name
        if glyph.name is None:
            raise ValueError(f"{glyph!r} has no name; can't add it to Layer")
        if not overwrite and glyph.name in self._glyphs:
            raise KeyError(f"glyph named '{glyph.name}' already exists")
        self._glyphs[glyph.name] = glyph

    def loadGlyph(self, name: str) -> Glyph:
        """Load and return Glyph object."""
        # XXX: Remove and let __getitem__ do it?
        glyph = Glyph(name)
        self._glyphSet.readGlyph(name, glyph, glyph.getPointPen())
        self._glyphs[name] = glyph
        return glyph

    def newGlyph(self, name: str) -> Glyph:
        """Creates and returns new Glyph object in this layer with name."""
        if name in self._glyphs:
            raise KeyError(f"glyph named '{name}' already exists")
        self._glyphs[name] = glyph = Glyph(name)
        return glyph

    def renameGlyph(self, name: str, newName: str, overwrite: bool = False) -> None:
        """Renames a Glyph object in this layer.

        Args:
            name: The old name.
            newName: The new name.
            overwrite: If False, raises exception if newName is already taken.
                If True, overwrites (read: deletes) the old Glyph object.
        """
        if name == newName:
            return
        if not overwrite and newName in self._glyphs:
            raise KeyError(f"target glyph named '{newName}' already exists")
        # pop and set name
        glyph = self.pop(name)
        glyph._name = newName
        # add it back
        self._glyphs[newName] = glyph

    def instantiateGlyphObject(self) -> Glyph:
        """Returns a new Glyph instance.

        |defcon_compat|
        """
        return Glyph()

    def write(self, glyphSet: GlyphSet, saveAs: bool = True) -> None:
        """Write Layer to a :class:`fontTools.ufoLib.glifLib.GlyphSet`.

        Args:
            glyphSet: The GlyphSet object to write to.
            saveAs: If True, tells the writer to save out-of-place. If False, tells the
                writer to save in-place. This affects how resources are cleaned before
                writing.
        """
        glyphs = self._glyphs
        if not saveAs:
            for name in set(glyphSet.contents).difference(glyphs):
                glyphSet.deleteGlyph(name)
        for name, glyph in glyphs.items():
            if glyph is _GLYPH_NOT_LOADED:
                if saveAs:
                    glyph = self.loadGlyph(name)
                else:
                    continue
            _prune_object_libs(glyph.lib, _fetch_glyph_identifiers(glyph))
            glyphSet.writeGlyph(
                name, glyphObject=glyph, drawPointsFunc=glyph.drawPoints
            )
        glyphSet.writeContents()
        glyphSet.writeLayerInfo(self)
        if saveAs:
            # all glyphs are loaded by now, no need to keep ref to glyphSet
            self._glyphSet = None

    def _unstructure(self, converter: GenConverter) -> dict[str, Any]:
        # omit glyph name attribute, already used as key
        glyphs: dict[str, dict[str, Any]] = {}
        for glyph_name in self._glyphs:
            g = converter.unstructure(self[glyph_name])
            assert glyph_name == g.pop("name")
            glyphs[glyph_name] = g
        d: dict[str, Any] = {
            # never omit name even if == 'public.default' as that acts as
            # the layer's "key" in the layerSet.
            "name": self._name,
        }
        default: Any
        for key, value, default in [
            ("default", self._default, self._name == DEFAULT_LAYER_NAME),
            ("glyphs", glyphs, {}),
            ("lib", self._lib, {}),
        ]:
            if not converter.omit_if_default or value != default:
                d[key] = value
        if self.color is not None:
            d["color"] = self.color
        return d

    @staticmethod
    def _structure(
        data: dict[str, Any], cls: Type[Layer], converter: GenConverter
    ) -> Layer:
        return cls(
            name=data.get("name", DEFAULT_LAYER_NAME),
            glyphs={
                k: converter.structure(v, Glyph)
                for k, v in data.get("glyphs", {}).items()
            },
            color=data.get("color"),
            lib=converter.structure(data.get("lib", {}), Lib),
            default=data.get("default", False),
        )


def _fetch_glyph_identifiers(glyph: Glyph) -> set[str]:
    """Returns all identifiers in use in a glyph."""

    identifiers = set()
    for anchor in glyph.anchors:
        if anchor.identifier is not None:
            identifiers.add(anchor.identifier)
    for guideline in glyph.guidelines:
        if guideline.identifier is not None:
            identifiers.add(guideline.identifier)
    for contour in glyph.contours:
        if contour.identifier is not None:
            identifiers.add(contour.identifier)
        for point in contour:
            if point.identifier is not None:
                identifiers.add(point.identifier)
    for component in glyph.components:
        if component.identifier is not None:
            identifiers.add(component.identifier)
    return identifiers
