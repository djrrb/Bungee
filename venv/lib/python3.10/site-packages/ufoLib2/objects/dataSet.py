from __future__ import annotations

from fontTools.ufoLib import UFOReader, UFOWriter

from ufoLib2.objects.misc import DataStore


class DataSet(DataStore):
    """Represents a mapping of POSIX filename strings to arbitrary data bytes.

    Always use forward slahes (/) as directory separators, even on Windows.

    Behavior:
        DataSet behaves like a dictionary of type ``Dict[str, bytes]``.

        >>> from ufoLib2 import Font
        >>> font = Font()
        >>> font.data["test.txt"] = b"123"
        >>> font.data["directory/my_binary_blob.bin"] = b"456"
        >>> font.data["test.txt"]
        b'123'
        >>> del font.data["test.txt"]
        >>> list(font.data.items())
        [('directory/my_binary_blob.bin', b'456')]
    """

    @staticmethod
    def list_contents(reader: UFOReader) -> list[str]:
        """Returns a list of POSIX filename strings in the data store."""
        return reader.getDataDirectoryListing()  # type: ignore

    @staticmethod
    def read_data(reader: UFOReader, filename: str) -> bytes:
        """Returns the data at filename within the store."""
        return reader.readData(filename)  # type: ignore

    @staticmethod
    def write_data(writer: UFOWriter, filename: str, data: bytes) -> None:
        """Writes the data to filename within the store."""
        writer.writeData(filename, data)

    @staticmethod
    def remove_data(writer: UFOWriter, filename: str) -> None:
        """Remove the data at filename within the store."""
        writer.removeData(filename)
