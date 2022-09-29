from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Optional, Tuple

from attr import define, field
from fontTools.misc.transform import Identity, Transform

from .misc import _convert_transform

# For Python 3.7 compatibility.
if TYPE_CHECKING:
    ImageMapping = Mapping[str, Any]
else:
    ImageMapping = Mapping


@define
class Image(ImageMapping):
    """Represents a background image reference.

    See http://unifiedfontobject.org/versions/ufo3/images/ and
    http://unifiedfontobject.org/versions/ufo3/glyphs/glif/#image.
    """

    fileName: Optional[str] = None
    """The filename of the image."""

    transformation: Transform = field(default=Identity, converter=_convert_transform)
    """The affine transformation applied to the image."""

    color: Optional[str] = None
    """The color applied to the image."""

    def clear(self) -> None:
        """Resets the image reference to factory settings."""
        self.fileName = None
        self.transformation = Identity
        self.color = None

    def __bool__(self) -> bool:
        """Indicates whether fileName is set."""
        return self.fileName is not None

    # implementation of collections.abc.Mapping abstract methods.
    # the fontTools.ufoLib.validators.imageValidator requires that image is a
    # subclass of Mapping...

    _transformation_keys_: ClassVar[Tuple[str, str, str, str, str, str]] = (
        "xScale",
        "xyScale",
        "yxScale",
        "yScale",
        "xOffset",
        "yOffset",
    )
    _valid_keys_: ClassVar[Tuple[str, str, str, str, str, str, str, str]] = (
        "fileName",
        *_transformation_keys_,
        "color",
    )

    def __getitem__(self, key: str) -> Any:
        try:
            i = self._transformation_keys_.index(key)
        except ValueError:
            try:
                return getattr(self, key)
            except AttributeError:
                raise KeyError(key)
        else:
            return self.transformation[i]

    def __len__(self) -> int:
        return len(self._valid_keys_)

    def __iter__(self) -> Iterator[str]:
        return iter(self._valid_keys_)
