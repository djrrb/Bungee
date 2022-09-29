class Error(Exception):
    """Base exception class for all ufo2ft errors."""

    pass


class InvalidFontData(Error):
    """Raised when input font contains invalid data."""

    pass


class InvalidFeaturesData(Error):
    """Raised when input font contains invalid features data."""

    pass


class InvalidDesignSpaceData(Error):
    """Raised when input DesignSpace document contains invalid data."""

    pass
