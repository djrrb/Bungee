# Copyright 2015 Google Inc. All Rights Reserved.
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


import re

from glyphsLib.types import Point

COLOR_NAME_SUFFIX = " [%s]"
COLOR_NAME_RE = re.compile(r"^.*( \[([0-1.,eE+-]+)\])$")
IDENTIFIER_NAME_SUFFIX = " [#%s]"
IDENTIFIER_NAME_RE = re.compile(r"^.*( \[#([^\]]+)\])$")
LOCKED_NAME_SUFFIX = " [locked]"


def to_ufo_guidelines(self, ufo_obj, glyphs_obj):
    """Set guidelines."""
    guidelines = glyphs_obj.guides
    if not guidelines:
        return
    new_guidelines = []
    for guideline in guidelines:
        new_guideline = {}
        x, y = guideline.position
        angle = guideline.angle % 360
        if _is_vertical(x, y, angle):
            new_guideline["x"] = x
        elif _is_horizontal(x, y, angle):
            new_guideline["y"] = y
        else:
            new_guideline["x"] = x
            new_guideline["y"] = y
            new_guideline["angle"] = angle
        name = guideline.name
        if name is not None:
            # Identifier
            m = IDENTIFIER_NAME_RE.match(name)
            if m:
                new_guideline["identifier"] = m.group(2)
                name = name[: -len(m.group(1))]
            # Color
            m = COLOR_NAME_RE.match(name)
            if m:
                new_guideline["color"] = m.group(2)
                name = name[: -len(m.group(1))]
        if guideline.locked:
            name = (name or "") + LOCKED_NAME_SUFFIX
        if name:
            new_guideline["name"] = name
        new_guidelines.append(new_guideline)
    ufo_obj.guidelines = new_guidelines


def to_glyphs_guidelines(self, ufo_obj, glyphs_obj):
    """Set guidelines."""
    if not ufo_obj.guidelines:
        return
    for guideline in ufo_obj.guidelines:
        new_guideline = self.glyphs_module.GSGuide()
        name = guideline.name
        # Locked
        if name is not None and name.endswith(LOCKED_NAME_SUFFIX):
            name = name[: -len(LOCKED_NAME_SUFFIX)]
            new_guideline.locked = True
        if guideline.color:
            name = (name or "") + COLOR_NAME_SUFFIX % str(guideline.color)
        if guideline.identifier:
            name = (name or "") + IDENTIFIER_NAME_SUFFIX % guideline.identifier
        new_guideline.name = name
        new_guideline.position = Point(guideline.x or 0, guideline.y or 0)
        if guideline.angle is not None:
            new_guideline.angle = guideline.angle % 360
        elif _is_vertical(guideline.x, guideline.y, None):
            new_guideline.angle = 90
        glyphs_obj.guides.append(new_guideline)


def _is_vertical(x, y, angle):
    return (y is None or y == 0) and (angle is None or angle == 90 or angle == 270)


def _is_horizontal(x, y, angle):
    return (x is None or x == 0) and (angle is None or angle == 0 or angle == 180)
