from __future__ import annotations

import os
import shutil
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    KeysView,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    cast,
)

import fs.base
import fs.tempfs
from attr import define, field
from fontTools.ufoLib import UFOFileStructure, UFOReader, UFOWriter

from ufoLib2.constants import DEFAULT_LAYER_NAME
from ufoLib2.objects.dataSet import DataSet
from ufoLib2.objects.features import Features
from ufoLib2.objects.glyph import Glyph
from ufoLib2.objects.guideline import Guideline
from ufoLib2.objects.imageSet import ImageSet
from ufoLib2.objects.info import Info
from ufoLib2.objects.kerning import Kerning, KerningPair
from ufoLib2.objects.layer import Layer
from ufoLib2.objects.layerSet import LayerSet
from ufoLib2.objects.lib import Lib, _convert_Lib, _get_lib, _set_lib
from ufoLib2.objects.misc import (
    BoundingBox,
    _deepcopy_unlazify_attrs,
    _object_lib,
    _prune_object_libs,
)
from ufoLib2.typing import HasIdentifier, PathLike, T


def _convert_LayerSet(value: LayerSet | Iterable[Layer]) -> LayerSet:
    return value if isinstance(value, LayerSet) else LayerSet.from_iterable(value)


def _convert_Info(value: Info | Mapping[str, Any]) -> Info:
    return value if isinstance(value, Info) else Info(**value)


def _convert_DataSet(value: DataSet | MutableMapping[str, bytes]) -> DataSet:
    return value if isinstance(value, DataSet) else DataSet(value)  # type: ignore


def _convert_ImageSet(value: ImageSet | MutableMapping[str, bytes]) -> ImageSet:
    return value if isinstance(value, ImageSet) else ImageSet(value)  # type: ignore


def _convert_Features(value: Features | str) -> Features:
    return value if isinstance(value, Features) else Features(value)


def _convert_Kerning(value: Mapping[KerningPair, float]) -> Kerning:
    return value if isinstance(value, Kerning) else Kerning(value)


def _get_kerning(self: Font) -> Kerning:
    return self._kerning


def _set_kerning(self: Font, value: Mapping[KerningPair, float]) -> None:
    self._kerning = _convert_Kerning(value)


@define(kw_only=True)
class Font:
    """A data class representing a single Unified Font Object (UFO).

    Font uses :class:`fontTools.ufoLib.UFOReader` and
    :class:`fontTools.ufoLib.UFOWriter` to read and write UFO data from and to disk.
    It will default to reading lazily, loading glyphs, data and images as they are
    accessed. Copying a font implicitly loads everything eagerly before.

    The data model is formally specified at
    http://unifiedfontobject.org/versions/ufo3/index.html.

    Parameters:
        layers (LayerSet): A mapping of layer names to Layer objects.
        info (Info): The font Info object.
        features (Features): The font Features object.
        groups (Dict[str, List[str]]): A mapping of group names to a list of glyph
            names.
        kerning (Dict[Tuple[str, str], float]): A mapping of a tuple of first and
            second kerning pair to a kerning value.
        lib (Dict[str, Any]): A mapping of keys to arbitrary values.
        data (DataSet): A mapping of data file paths to arbitrary data.
        images (ImageSet): A mapping of image file paths to arbitrary image data.

    Behavior:
        The Font object has some dict-like behavior for quick access to glyphs on the
        the default layer. For example, to get a glyph by name from the default layer::

            glyph = font["aGlyphName"]

        To iterate over all glyphs in the default layer::

            for glyph in font:
                pass

        To get the number of glyphs in the default layer::

            glyphCount = len(font)

        To find out if a font contains a particular glyph in the default layer by name::

            exists = "aGlyphName" in font

        To remove a glyph from the default layer by name::

            del font["aGlyphName"]

        To replace a glyph in the default layer with another :class:`.Glyph` object::

            font["aGlyphName"] = otherGlyph

        To copy a font::

            import copy
            fontCopy = copy.deepcopy(font)

        Layers behave the same, for when you're working on something other than the
        default layer.
    """

    layers: LayerSet = field(
        factory=LayerSet.default,
        converter=_convert_LayerSet,
        metadata={"omit_if_default": False},
    )
    """LayerSet: A mapping of layer names to Layer objects."""

    info: Info = field(factory=Info, converter=_convert_Info)
    """Info: The font Info object."""

    features: Features = field(factory=Features, converter=_convert_Features)
    """Features: The font Features object."""

    groups: Dict[str, List[str]] = field(factory=dict)
    """Dict[str, List[str]]: A mapping of group names to a list of glyph names."""

    _kerning: Kerning = field(factory=Kerning, converter=_convert_Kerning)
    """Dict[Tuple[str, str], float]: A mapping of a tuple of first and second kerning
    pair to a kerning value."""

    _lib: Lib = field(factory=Lib, converter=_convert_Lib)
    """Dict[str, PlistEncodable]: A mapping of keys to arbitrary plist values."""

    data: DataSet = field(factory=DataSet, converter=_convert_DataSet)
    """DataSet: A mapping of data file paths to arbitrary data."""

    images: ImageSet = field(factory=ImageSet, converter=_convert_ImageSet)
    """ImageSet: A mapping of image file paths to arbitrary image data."""

    # init=False args, set by alternate open/read classmethod constructors
    _path: Optional[PathLike] = field(
        default=None, metadata=dict(copyable=False), eq=False, init=False
    )
    _lazy: Optional[bool] = field(default=None, init=False, eq=False)
    _reader: Optional[UFOReader] = field(default=None, init=False, eq=False)
    _fileStructure: Optional[UFOFileStructure] = field(
        default=None, init=False, eq=False
    )

    @classmethod
    def open(cls, path: PathLike, lazy: bool = True, validate: bool = True) -> Font:
        """Instantiates a new Font object from a path to a UFO.

        Args:
            path: The path to the UFO to load.
            lazy: If True, load glyphs, data files and images as they are accessed. If
                False, load everything up front.
            validate: If True, enable UFO data model validation during loading. If
                False, load whatever is deserializable.
        """
        reader = UFOReader(path, validate=validate)
        self = cls.read(reader, lazy=lazy)
        self._path = path
        if not lazy:
            reader.close()
        return self

    @classmethod
    def read(cls, reader: UFOReader, lazy: bool = True) -> Font:
        """Instantiates a Font object from a :class:`fontTools.ufoLib.UFOReader`.

        Args:
            path: The path to the UFO to load.
            lazy: If True, load glyphs, data files and images as they are accessed. If
                False, load everything up front.
        """
        self = cls(
            layers=LayerSet.read(reader, lazy=lazy),
            data=DataSet.read(reader, lazy=lazy),
            images=ImageSet.read(reader, lazy=lazy),
            info=Info.read(reader),
            features=Features(reader.readFeatures()),
            groups=reader.readGroups(),
            kerning=Kerning(reader.readKerning()),
            lib=Lib(reader.readLib()),
        )
        self._lazy = lazy
        self._fileStructure = reader.fileStructure
        if lazy:
            # keep the reader around so we can close it when done
            self._reader = reader
        return self

    def __contains__(self, name: object) -> bool:
        return name in self.layers._defaultLayer

    def __delitem__(self, name: str) -> None:
        del self.layers._defaultLayer[name]

    def __getitem__(self, name: str) -> Glyph:
        return self.layers._defaultLayer[name]

    def __setitem__(self, name: str, glyph: Glyph) -> None:
        self.layers._defaultLayer[name] = glyph

    def __iter__(self) -> Iterator[Glyph]:
        return iter(self.layers._defaultLayer)

    def __len__(self) -> int:
        return len(self.layers._defaultLayer)

    def get(self, name: str, default: T | None = None) -> T | Glyph | None:
        """Return the :class:`.Glyph` object for name if it is present in the
        default layer, otherwise return ``default``."""
        return self.layers._defaultLayer.get(name, default)

    def keys(self) -> KeysView[str]:
        """Return a list of glyph names in the default layer."""
        return self.layers._defaultLayer.keys()

    def close(self) -> None:
        """Closes the UFOReader if it still exists to finalize any outstanding
        file operations."""
        if self._reader is not None:
            self._reader.close()

    def __enter__(self) -> Font:
        # TODO: Document an example for this.
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        names = list(filter(None, [self.info.familyName, self.info.styleName]))
        fontName = " '{}'".format(" ".join(names)) if names else ""
        return "<{}.{}{} at {}>".format(
            self.__class__.__module__, self.__class__.__name__, fontName, hex(id(self))
        )

    def __eq__(self, other: object) -> bool:
        # same as attrs-defined __eq__ method, only that it un-lazifies fonts if needed
        # NOTE: Avoid isinstance check that mypy recognizes because we don't want to
        # test possible Font subclasses for equality.
        if other.__class__ is not self.__class__:
            return NotImplemented
        other = cast(Font, other)

        for font in (self, other):
            if font._lazy:
                font.unlazify()

        return (
            self.layers,
            self.info,
            self.features,
            self.groups,
            self.kerning,
            self.lib,
            self.data,
            self.images,
        ) == (
            other.layers,
            other.info,
            other.features,
            other.groups,
            other.kerning,
            other.lib,
            other.data,
            other.images,
        )

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    @property
    def reader(self) -> UFOReader | None:
        """Returns the underlying :class:`fontTools.ufoLib.UFOReader`."""
        return self._reader

    def unlazify(self) -> None:
        """Load all glyphs, data files and images if the Font object loaded
        them lazily previously."""
        if self._lazy:
            assert self._reader is not None
            self.layers.unlazify()
            self.data.unlazify()
            self.images.unlazify()
        self._lazy = False

    __deepcopy__ = _deepcopy_unlazify_attrs

    @property
    def glyphOrder(self) -> list[str]:
        """The font's glyph order.

        See http://unifiedfontobject.org/versions/ufo3/lib.plist/#publicglyphorder for
        semantics.

        Getter:
            Return the font's glyph order, if it is set in lib, or an empty list.

        Note:
            The getter always returns a new list, modifications to it do not change
            the lib content.

        Setter:
            Sets the font's glyph order. If ``value`` is None or an empty list, the
            glyph order key will be deleted from the lib if it exists.
        """
        return list(cast(Sequence[str], self.lib.get("public.glyphOrder", [])))

    @glyphOrder.setter
    def glyphOrder(self, value: list[str] | None) -> None:
        if value is None or len(value) == 0:
            if "public.glyphOrder" in self.lib:
                del self.lib["public.glyphOrder"]
        else:
            self.lib["public.glyphOrder"] = value

    @property
    def guidelines(self) -> list[Guideline]:
        """The font's global guidelines.

        Getter:
            Returns the font's global guidelines or an empty list.

        Setter:
            Appends the list of Guidelines to the global Guidelines.
                XXX Should it replace them?
        """
        if self.info.guidelines is None:
            return []
        return self.info.guidelines

    @guidelines.setter
    def guidelines(self, value: Iterable[Guideline | Mapping[str, Any]]) -> None:
        self.info.guidelines = []
        for guideline in value:
            self.appendGuideline(guideline)

    kerning = property(_get_kerning, _set_kerning)

    lib = property(_get_lib, _set_lib)

    def objectLib(self, object: HasIdentifier) -> dict[str, Any]:
        """Return the lib for an object with an identifier, as stored in a font's lib.

        If the object does not yet have an identifier, a new one is assigned to it. If
        the font lib does not yet contain the object's lib, a new one is inserted and
        returned.

        .. doctest::

            >>> from ufoLib2.objects import Font, Guideline
            >>> font = Font()
            >>> font.guidelines = [Guideline(x=100)]
            >>> guideline_lib = font.objectLib(font.guidelines[0])
            >>> guideline_lib["com.test.foo"] = 1234
            >>> guideline_id = font.guidelines[0].identifier
            >>> assert guideline_id is not None
            >>> assert font.lib["public.objectLibs"][guideline_id] is guideline_lib
        """

        return _object_lib(self.lib, object)

    @property
    def path(self) -> PathLike | None:
        """Return the path of the UFO, if it was set, or None."""
        return self._path

    @property
    def bounds(self) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the default
        layer, taking the actual contours into account.

        |defcon_compat|
        """
        return self.layers._defaultLayer.bounds

    @property
    def controlPointBounds(self) -> BoundingBox | None:
        """Returns the (xMin, yMin, xMax, yMax) bounding box of the layer,
        taking only the control points into account.

        |defcon_compat|
        """
        return self.layers._defaultLayer.controlPointBounds

    def addGlyph(self, glyph: Glyph) -> None:
        """Appends glyph object to the default layer unless its name is already
        taken.

        Note:
            Call the method on the layer directly if you want to overwrite entries
            with the same name or append copies of the glyph.
        """
        self.layers._defaultLayer.addGlyph(glyph)

    def newGlyph(self, name: str) -> Glyph:
        """Creates and returns new :class:`.Glyph` object in default layer with
        name."""
        return self.layers._defaultLayer.newGlyph(name)

    def newLayer(self, name: str, **kwargs: Any) -> Layer:
        """Creates and returns a new :class:`.Layer`.

        Args:
            name: The name of the new layer.
            kwargs: The arguments passed to the Layer object constructor.
        """
        return self.layers.newLayer(name, **kwargs)

    def renameGlyph(self, name: str, newName: str, overwrite: bool = False) -> None:
        """Renames a :class:`.Glyph` object in the default layer.

        Args:
            name: The old name.
            newName: The new name.
            overwrite: If False, raises exception if newName is already taken.
                If True, overwrites (read: deletes) the old :class:`.Glyph` object.
        """
        self.layers._defaultLayer.renameGlyph(name, newName, overwrite)

    def renameLayer(self, name: str, newName: str, overwrite: bool = False) -> None:
        """Renames a :class:`.Layer`.

        Args:
            name: The old name.
            newName: The new name.
            overwrite: If False, raises exception if newName is already taken.
                If True, overwrites (read: deletes) the old :class:`.Layer` object.
        """
        self.layers.renameLayer(name, newName, overwrite)

    def appendGuideline(self, guideline: Guideline | Mapping[str, Any]) -> None:
        """Appends a guideline to the list of the font's global guidelines.

        Creates the global guideline list unless it already exists.

        Args:
            guideline: A :class:`.Guideline` object or a mapping for the Guideline
                constructor.
        """
        if not isinstance(guideline, Guideline):
            if not isinstance(guideline, Mapping):
                raise TypeError(
                    "Expected Guideline object or a Mapping for the ",
                    f"Guideline constructor, found {type(guideline).__name__}",
                )
            guideline = Guideline(**guideline)
        if self.info.guidelines is None:
            self.info.guidelines = []
        self.info.guidelines.append(guideline)

    def write(self, writer: UFOWriter, saveAs: bool | None = None) -> None:
        """Writes this Font to a :class:`fontTools.ufoLib.UFOWriter`.

        Args:
            writer: The :class:`fontTools.ufoLib.UFOWriter` to write to.
            saveAs: If True, tells the writer to save out-of-place. If False, tells the
                writer to save in-place. This affects how resources are cleaned before
                writing.
        """
        if saveAs is None:
            saveAs = self._reader is not writer
        # TODO move this check to fontTools UFOWriter
        if self.layers._defaultLayer.name != DEFAULT_LAYER_NAME:
            assert DEFAULT_LAYER_NAME not in self.layers.layerOrder
        # save font attrs
        writer.writeFeatures(self.features.text)
        writer.writeGroups(self.groups)
        writer.writeInfo(self.info)
        writer.writeKerning(self.kerning)
        _prune_object_libs(
            self.lib,
            {g.identifier for g in self.guidelines if g.identifier is not None},
        )
        writer.writeLib(self.lib)
        # save the layers
        self.layers.write(writer, saveAs=saveAs)
        # save bin parts
        self.data.write(writer, saveAs=saveAs)
        self.images.write(writer, saveAs=saveAs)

    def save(
        self,
        path: PathLike | fs.base.FS | None = None,
        formatVersion: int = 3,
        structure: UFOFileStructure | None = None,
        overwrite: bool = False,
        validate: bool = True,
    ) -> None:
        """Saves the font to ``path``.

        Args:
            path: The target path. If it is None, the path from the last save (except
                when that was a ``fs.base.FS``) or when the font was first opened will
                be used.
            formatVersion: The version to save the UFO as. Only version 3 is supported
                currently.
            structure (fontTools.ufoLib.UFOFileStructure): How to store the UFO.
                Can be either None, "zip" or "package". If None, it tries to use the
                same structure as the original UFO at the output path. If "zip", the
                UFO will be saved as compressed archive. If "package", it is saved as
                a regular folder or "package".
            overwrite: If False, raises OSError when the target path exists. If True,
                overwrites the target path.
            validate: If True, will validate the data in Font before writing it out. If
                False, will write out whatever is serializable.
        """
        if formatVersion != 3:
            raise NotImplementedError(f"unsupported format version: {formatVersion}")

        # validate 'structure' argument
        if structure is not None:
            structure = UFOFileStructure(structure)
        elif self._fileStructure is not None:
            # if structure is None, fall back to the same as when first loaded
            structure = self._fileStructure

        # Normalize path unless we're given a fs.base.FS, which we pass to UFOWriter.
        if path is not None and not isinstance(path, fs.base.FS):
            path = os.path.normpath(os.fspath(path))

        overwritePath = tmp = None

        saveAs = path is not None
        if saveAs:
            if isinstance(path, str) and os.path.exists(path):
                if overwrite:
                    overwritePath = path
                    tmp = fs.tempfs.TempFS()
                    path = tmp.getsyspath(os.path.basename(path))
                else:
                    import errno

                    raise OSError(errno.EEXIST, "path %r already exists" % path)
        elif self.path is None:
            raise TypeError("'path' is required when saving a new Font")
        else:
            path = self.path

        try:
            with UFOWriter(path, structure=structure, validate=validate) as writer:
                self.write(writer, saveAs=saveAs)
            writer.setModificationTime()
        except Exception:
            raise
        else:
            if overwritePath is not None:
                assert isinstance(path, str)

                # remove existing then move file to destination
                if os.path.isdir(overwritePath):
                    shutil.rmtree(overwritePath)
                elif os.path.isfile(overwritePath):
                    os.remove(overwritePath)
                shutil.move(path, overwritePath)
                path = overwritePath
        finally:
            # clean up the temporary directory
            if tmp is not None:
                tmp.close()

        # Only remember path if it isn't a fs.base.FS because not all FS objects are
        # OsFS with a corresponding filesystem path. E.g. think about MemoryFS.
        # If you want, you can call getsyspath("") method of OsFS object and set that to
        # self._path. But you then have to catch the fs.errors.NoSysPath and skip if
        # the FS object does not implement a filesystem path.
        if not isinstance(path, fs.base.FS):
            self._path = path
