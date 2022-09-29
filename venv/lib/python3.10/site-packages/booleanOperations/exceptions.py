class BooleanOperationsError(Exception):
    """Base BooleanOperations exception"""


class UnsupportedContourError(BooleanOperationsError):
    """Raised when asked to perform an operation on an unsupported curve type."""


class InvalidContourError(BooleanOperationsError):
    """Raised when any input contour is invalid"""


class InvalidSubjectContourError(InvalidContourError):
    """Raised when a 'subject' contour is not valid"""


class InvalidClippingContourError(InvalidContourError):
    """Raised when a 'clipping' contour is not valid"""


class OpenContourError(BooleanOperationsError):
    """Raised when any input contour is open"""


class ExecutionError(BooleanOperationsError):
    """Raised when clipping execution fails"""
