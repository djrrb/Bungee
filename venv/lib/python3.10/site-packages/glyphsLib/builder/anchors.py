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


from fontTools.misc.transform import Transform
from .constants import COMPONENT_INFO_KEY
import fontTools.pens.boundsPen

from glyphsLib.types import Point

__all__ = [
    "to_ufo_propagate_font_anchors",
    "to_ufo_glyph_anchors",
    "to_glyphs_glyph_anchors",
]


def to_ufo_propagate_font_anchors(self, ufo):
    """Copy anchors from parent glyphs' components to the parent."""

    processed = set()
    for glyph in ufo:
        _propagate_glyph_anchors(self, ufo, glyph, processed)


def _propagate_glyph_anchors(self, ufo, parent, processed):
    """Propagate anchors for a single parent glyph."""

    if parent.name in processed:
        return
    processed.add(parent.name)

    base_components = []
    mark_components = []
    anchor_names = set()
    to_add = {}
    for component in parent.components:
        try:
            glyph = ufo[component.baseGlyph]
        except KeyError:
            self.logger.warning(
                "Anchors not propagated for inexistent component {} in glyph {}".format(
                    component.baseGlyph, parent.name
                )
            )
        else:
            _propagate_glyph_anchors(self, ufo, glyph, processed)
            if any(a.name.startswith("_") for a in glyph.anchors):
                mark_components.append(component)
            else:
                base_components.append(component)
                anchor_names |= {a.name for a in glyph.anchors}

    if mark_components and not base_components and _is_ligature_mark(parent):
        # The composite is a mark that is composed of other marks (E.g.
        # "circumflexcomb_tildecomb"). Promote the mark that is positioned closest
        # to the origin to a base.
        try:
            component = _component_closest_to_origin(mark_components, ufo)
        except Exception as e:
            raise Exception(
                "Error while determining which component of composite "
                "'{}' is the lowest: {}".format(parent.name, str(e))
            ) from e
        mark_components.remove(component)
        base_components.append(component)
        glyph = ufo[component.baseGlyph]
        anchor_names |= {a.name for a in glyph.anchors}

    for anchor_name in anchor_names:
        # don't add if parent already contains this anchor OR any associated
        # ligature anchors (e.g. "top_1, top_2" for "top")
        if not any(a.name.startswith(anchor_name) for a in parent.anchors):
            _get_anchor_data(to_add, ufo, base_components, anchor_name)

    for component in mark_components:
        _adjust_anchors(to_add, ufo, parent, component)

    # we sort propagated anchors to append in a deterministic order
    for name, (x, y) in sorted(to_add.items()):
        anchor_dict = {"name": name, "x": x, "y": y}
        parent.appendAnchor(anchor_dict)


def _get_anchor_data(anchor_data, ufo, components, anchor_name):
    """Get data for an anchor from a list of components."""

    anchors = []
    for component in components:
        for anchor in ufo[component.baseGlyph].anchors:
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


def _componentAnchorFromLib(_glyph, _targetComponent):
    """Pull component’s named anchor from Glyph.lib"""
    if COMPONENT_INFO_KEY in _glyph.lib:
        for _anchorLib in _glyph.lib[COMPONENT_INFO_KEY]:
            if (
                "anchor" in _anchorLib
                and "name" in _anchorLib
                and _anchorLib["name"] == _targetComponent.baseGlyph
                and _anchorLib["index"] == _glyph.components.index(_targetComponent)
            ):
                return _anchorLib["anchor"]


def _adjust_anchors(anchor_data, ufo, parent, component):
    """Adjust anchors to which a mark component may have been attached."""
    glyph = ufo[component.baseGlyph]
    t = Transform(*component.transformation)
    _componentAnchor = _componentAnchorFromLib(parent, component)
    for anchor in glyph.anchors:
        # adjust either if component is attached to a specific named anchor
        # (e.g. top_2 for a ligature glyph)
        # rather than to the standard anchors (top/bottom)
        if _componentAnchor and _componentAnchor in anchor_data:
            anchor_data[_componentAnchor] = t.transformPoint((anchor.x, anchor.y))
        # ... or this anchor has data and the component also contains
        # the associated mark anchor (e.g. "_top" for "top") ...
        elif anchor.name in anchor_data and any(
            a.name == "_" + anchor.name for a in glyph.anchors
        ):
            anchor_data[anchor.name] = t.transformPoint((anchor.x, anchor.y))


def to_ufo_glyph_anchors(self, glyph, anchors):
    """Add .glyphs anchors to a glyph."""

    for anchor in anchors:
        x, y = anchor.position
        anchor_dict = {"name": anchor.name, "x": x, "y": y}
        glyph.appendAnchor(anchor_dict)


def to_glyphs_glyph_anchors(self, ufo_glyph, layer):
    """Add UFO glif anchors to a GSLayer."""
    for ufo_anchor in ufo_glyph.anchors:
        anchor = self.glyphs_module.GSAnchor()
        anchor.name = ufo_anchor.name
        anchor.position = Point(ufo_anchor.x, ufo_anchor.y)
        layer.anchors.append(anchor)


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
            "Don't know to to compute the bounds of component '{}' ".format(component)
        )
