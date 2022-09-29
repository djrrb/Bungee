from ._pathops import (
    PathPen,
    Path,
    PathVerb,
    PathOp,
    FillType,
    LineCap,
    LineJoin,
    ArcSize,
    Direction,
    op,
    simplify,
    OpBuilder,
    PathOpsError,
    UnsupportedVerbError,
    OpenPathError,
    bits2float,
    float2bits,
    decompose_quadratic_segment,
)

from .operations import (
    union,
    difference,
    intersection,
    xor,
)

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"
