from __future__ import annotations

import re
from typing import TYPE_CHECKING, Type

from attr import define

if TYPE_CHECKING:
    from cattr import GenConverter


RE_NEWLINES = re.compile(r"\r\n|\r")


@define
class Features:
    """A data class representing UFO features.

    See http://unifiedfontobject.org/versions/ufo3/features.fea/.
    """

    text: str = ""
    """Holds the content of the features.fea file."""

    def __bool__(self) -> bool:
        return bool(self.text)

    def __str__(self) -> str:
        return self.text

    def normalize_newlines(self) -> Features:
        """Normalize CRLF and CR newlines to just LF."""
        self.text = RE_NEWLINES.sub("\n", self.text)
        return self

    def _unstructure(self, converter: GenConverter) -> str:
        del converter  # unused
        return self.text

    @staticmethod
    def _structure(data: str, cls: Type[Features], converter: GenConverter) -> Features:
        del converter  # unused
        return cls(data)
