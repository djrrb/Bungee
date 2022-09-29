# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

import fontTools.pens.boundsPen
from fontTools.misc.transform import Transform

from ufo2ft.filters import BaseFilter

logger = logging.getLogger(__name__)


class PropagateAnchorsFilter(BaseFilter):
    def set_context(self, font, glyphSet):
        ctx = super().set_context(font, glyphSet)
        ctx.processed = set()
        return ctx

    def __call__(self, font, glyphSet=None):
        if super().__call__(font, glyphSet):
            modified = self.context.modified
            if modified:
                logger.info("Glyphs with propagated anchors: %i" % len(modified))
            return modified

    def filter(self, glyph):
        if not glyph.components:
            return False
        before = len(glyph.anchors)
        _propagate_glyph_anchors(
            self.context.glyphSet,
            glyph,
            self.context.processed,
            self.context.modified,
        )
        return len(glyph.anchors) > before


def _propagate_glyph_anchors(glyphSet, composite, processed, modified):
    """
    Propagate anchors from base glyphs to a given composite
    glyph, and to all composite glyphs used in between.
    """

    if composite.name in processed:
        return
    processed.add(composite.name)

    if not composite.components:
        return

    base_components = []
    mark_components = []
    anchor_names = set()
    to_add = {}
    for component in composite.components:
        try:
            glyph = glyphSet[component.baseGlyph]
        except KeyError:
            logger.warning(
                "Anchors not propagated for inexistent component {} "
                "in glyph {}".format(component.baseGlyph, composite.name)
            )
        else:
            _propagate_glyph_anchors(glyphSet, glyph, processed, modified)
            if any(a.name.startswith("_") for a in glyph.anchors):
                mark_components.append(component)
            else:
                base_components.append(component)
                anchor_names |= {a.name for a in glyph.anchors}

    if mark_components and not base_components and _is_ligature_mark(composite):
        # The composite is a mark that is composed of other marks (E.g.
        # "circumflexcomb_tildecomb"). Promote the mark that is positioned closest
        # to the origin to a base.
        try:
            component = _component_closest_to_origin(mark_components, glyphSet)
        except Exception as e:
            raise Exception(
                "Error while determining which component of composite "
                "'{}' is the lowest: {}".format(composite.name, str(e))
            ) from e
        mark_components.remove(component)
        base_components.append(component)
        glyph = glyphSet[component.baseGlyph]
        anchor_names |= {a.name for a in glyph.anchors}

    for anchor_name in anchor_names:
        # don't add if composite glyph already contains this anchor OR any
        # associated ligature anchors (e.g. "top_1, top_2" for "top")
        if not any(a.name.startswith(anchor_name) for a in composite.anchors):
            _get_anchor_data(to_add, glyphSet, base_components, anchor_name)

    for component in mark_components:
        _adjust_anchors(to_add, glyphSet, component)

    # we sort propagated anchors to append in a deterministic order
    for name, (x, y) in sorted(to_add.items()):
        anchor_dict = {"name": name, "x": x, "y": y}
        try:
            composite.appendAnchor(anchor_dict)
        except TypeError:  # pragma: no cover
            # fontParts API
            composite.appendAnchor(name, (x, y))

    if to_add:
        modified.add(composite.name)


def _get_anchor_data(anchor_data, glyphSet, components, anchor_name):
    """Get data for an anchor from a list of components."""

    anchors = []
    for component in components:
        for anchor in glyphSet[component.baseGlyph].anchors:
            if anchor.name == anchor_name:
                anchors.append((anchor, component))
                break
    if len(anchors) > 1:
        for i, (anchor, component) in enumerate(anchors):
            t = Transform(*component.transformation)
            name = "%s_%d" % (anchor.name, i + 1)
            anchor_data[name] = t.transformPoint((anchor.x, anchor.y))
    elif anchors:
        anchor, component = anchors[0]
        t = Transform(*component.transformation)
        anchor_data[anchor.name] = t.transformPoint((anchor.x, anchor.y))


def _adjust_anchors(anchor_data, glyphSet, component):
    """
    Adjust base anchors to which a mark component may have been attached, by
    moving the base anchor attached to a mark anchor to the position of
    the mark component's base anchor.
    """

    glyph = glyphSet[component.baseGlyph]
    t = Transform(*component.transformation)
    for anchor in glyph.anchors:
        # only adjust if this anchor has data and the component also contains
        # the associated mark anchor (e.g. "_top" for "top")
        if anchor.name in anchor_data and any(
            a.name == "_" + anchor.name for a in glyph.anchors
        ):
            anchor_data[anchor.name] = t.transformPoint((anchor.x, anchor.y))


def _component_closest_to_origin(components, glyph_set):
    """Return the component whose (xmin, ymin) bounds are closest to origin.

    This ensures that a component that is moved below another is
    actually recognized as such. Looking only at the transformation
    offset can be misleading.
    """
    return min(components, key=lambda comp: _distance((0, 0), _bounds(comp, glyph_set)))


def _distance(pos1, pos2):
    x1, y1 = pos1
    x2, y2 = pos2
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


def _is_ligature_mark(glyph):
    return not glyph.name.startswith("_") and "_" in glyph.name


def _bounds(component, glyph_set):
    """Return the (xmin, ymin) of the bounds of `component`."""
    if hasattr(component, "bounds"):  # e.g. defcon
        return component.bounds[:2]
    elif hasattr(component, "draw"):  # e.g. ufoLib2
        pen = fontTools.pens.boundsPen.BoundsPen(glyphSet=glyph_set)
        component.draw(pen)
        return pen.bounds[:2]
    else:
        raise ValueError(
            f"Don't know to to compute the bounds of component '{component}' "
        )
