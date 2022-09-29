from .booleanOperationManager import BooleanOperationManager
from .exceptions import BooleanOperationsError

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"

# export BooleanOperationManager static methods
union = BooleanOperationManager.union
difference = BooleanOperationManager.difference
intersection = BooleanOperationManager.intersection
xor = BooleanOperationManager.xor
getIntersections = BooleanOperationManager.getIntersections
