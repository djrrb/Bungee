from functools import partial
from . import Path, PathOp, op


__all__ = [
    "difference",
    "intersection",
    "reverse_difference",
    "union",
    "xor",
]


def _draw(contours):
    path = Path()
    pen = path.getPen()
    for contour in contours:
        contour.draw(pen)
    return path


def union(
    contours,
    outpen,
    fix_winding=True,
    keep_starting_points=True,
    clockwise=False,
):
    if not contours:
        return
    path = _draw(contours)
    path.simplify(
        fix_winding=fix_winding,
        keep_starting_points=keep_starting_points,
        clockwise=clockwise,
    )
    path.draw(outpen)


def _do(
    operator,
    subject_contours,
    clip_contours,
    outpen,
    fix_winding=True,
    keep_starting_points=True,
    clockwise=False,
):
    one = _draw(subject_contours)
    two = _draw(clip_contours)
    result = op(
        one,
        two,
        operator,
        fix_winding=fix_winding,
        keep_starting_points=keep_starting_points,
        clockwise=clockwise,
    )
    result.draw(outpen)


# generate self-similar operations
for operation in PathOp:
    if operation == PathOp.UNION:
        continue
    globals()[operation.name.lower()] = partial(_do, operation)
