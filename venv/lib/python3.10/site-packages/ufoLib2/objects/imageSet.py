from __future__ import annotations

from fontTools.ufoLib import UFOReader, UFOWriter

from ufoLib2.objects.misc import DataStore


class ImageSet(DataStore):
    """Represents a mapping of POSIX filename strings to arbitrary image data.

    Note:
        Images cannot be put into subdirectories of the images folder.

    Behavior:
        ImageSet behaves like a dictionary of type ``Dict[str, bytes]``.

        >>> from ufoLib2 import Font
        >>> font = Font()
        >>> # Note: invalid PNG data for demonstration. Use the actual PNG bytes.
        >>> font.images["test.png"] = b"123"
        >>> font.images["test2.png"] = b"456"
        >>> font.images["test.png"]
        b'123'
        >>> del font.images["test.png"]
        >>> list(font.images.items())
        [('test2.png', b'456')]
    """

    @staticmethod
    def list_contents(reader: UFOReader) -> list[str]:
        """Returns a list of POSIX filename strings in the image data store."""
        return reader.getImageDirectoryListing()  # type: ignore

    @staticmethod
    def read_data(reader: UFOReader, filename: str) -> bytes:
        """Returns the image data at filename within the store."""
        return reader.readImage(filename)  # type: ignore

    @staticmethod
    def write_data(writer: UFOWriter, filename: str, data: bytes) -> None:
        """Writes the image data to filename within the store."""
        writer.writeImage(filename, data)

    @staticmethod
    def remove_data(writer: UFOWriter, filename: str) -> None:
        """Remove the image data at filename within the store."""
        writer.removeImage(filename)

    def __setitem__(self, fileName: str, data: bytes) -> None:
        if "/" in fileName:
            raise ValueError(
                "Images cannot be put into subdirectories of the images folder."
            )
        super().__setitem__(fileName, data)
