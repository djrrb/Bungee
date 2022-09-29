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


from .constants import GLYPHS_PREFIX
from glyphsLib.types import Point

LIB_KEY = GLYPHS_PREFIX + "annotations"


def to_ufo_annotations(self, ufo_glyph, layer):
    try:
        value = layer.annotations
    except KeyError:
        return
    annotations = []
    for an in list(value.values()):
        annot = {}
        for attr in ["angle", "position", "text", "type", "width"]:
            val = getattr(an, attr, None)
            if attr == "position" and val:
                val = list(val)
            if val:
                annot[attr] = val
        annotations.append(annot)

    if annotations:
        ufo_glyph.lib[LIB_KEY] = annotations


def to_glyphs_annotations(self, ufo_glyph, layer):
    if LIB_KEY not in ufo_glyph.lib:
        return

    for annot in ufo_glyph.lib[LIB_KEY]:
        annotation = self.glyphs_module.GSAnnotation()
        for attr in ["angle", "position", "text", "type", "width"]:
            if attr in annot and annot[attr]:
                if attr == "position":
                    # annot['position'] can be either "{1, 2}" or (1, 2)
                    position = Point(annot["position"])
                    annotation.position = position
                else:
                    setattr(annotation, attr, annot[attr])
        layer.annotations.append(annotation)
