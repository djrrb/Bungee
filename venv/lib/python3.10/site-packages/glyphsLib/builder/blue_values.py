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


def to_ufo_blue_values(self, ufo, master):
    """Set postscript blue values from Glyphs alignment zones."""

    alignment_zones = master.alignmentZones
    blue_values = []
    other_blues = []
    for zone in sorted(alignment_zones):
        pos = zone.position
        size = zone.size
        val_list = blue_values if pos == 0 or size >= 0 else other_blues
        val_list.extend(sorted((pos, pos + size)))

    if blue_values:
        ufo.info.postscriptBlueValues = blue_values
    if other_blues:
        ufo.info.postscriptOtherBlues = other_blues


def to_glyphs_blue_values(self, ufo, master):
    """Sets the GSFontMaster alignmentZones from the postscript blue values."""

    zones = []
    blue_values = _pairs(ufo.info.postscriptBlueValues or [])
    other_blues = _pairs(ufo.info.postscriptOtherBlues or [])
    for y1, y2 in blue_values:
        size = y2 - y1
        if y2 == 0:
            pos = 0
            size = -size
        else:
            pos = y1
        zones.append(self.glyphs_module.GSAlignmentZone(pos, size))
    for y1, y2 in other_blues:
        size = y1 - y2
        pos = y2
        zones.append(self.glyphs_module.GSAlignmentZone(pos, size))

    master.alignmentZones = sorted(zones, key=lambda zone: -zone.position)


def _pairs(list):
    return [list[i : i + 2] for i in range(0, len(list), 2)]
