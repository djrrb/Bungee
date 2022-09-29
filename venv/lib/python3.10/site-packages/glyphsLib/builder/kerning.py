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

from .glyph import BRACKET_GLYPH_RE

UFO_KERN_GROUP_PATTERN = re.compile("^public\\.kern([12])\\.(.*)$")


def to_ufo_kerning(self):
    for master in self.font.masters:
        kerning_source = master.metricsSource  # Maybe be a linked master
        if kerning_source is None:
            kerning_source = master
        if kerning_source.id in self.font.kerning:
            kerning = self.font.kerning[kerning_source.id]
            _to_ufo_kerning(self, self._sources[master.id].font, kerning)


def _to_ufo_kerning(self, ufo, kerning_data):
    """Add .glyphs kerning to an UFO."""

    warning_msg = "Non-existent glyph class %s found in kerning rules."

    for left, pairs in kerning_data.items():
        match = re.match(r"@MMK_L_(.+)", left)
        left_is_class = bool(match)
        if left_is_class:
            left = "public.kern1.%s" % match.group(1)
            if left not in ufo.groups:
                self.logger.warning(warning_msg % left)
        for right, kerning_val in pairs.items():
            match = re.match(r"@MMK_R_(.+)", right)
            right_is_class = bool(match)
            if right_is_class:
                right = "public.kern2.%s" % match.group(1)
                if right not in ufo.groups:
                    self.logger.warning(warning_msg % right)
            ufo.kerning[left, right] = kerning_val


def to_glyphs_kerning(self):
    """Add UFO kerning to GSFont."""
    for master_id, source in self._sources.items():
        for (left, right), value in source.font.kerning.items():
            if BRACKET_GLYPH_RE.match(left) or BRACKET_GLYPH_RE.match(right):
                # Skip all bracket glyph entries, as they are duplicates of their
                # parents'.
                continue
            left_match = UFO_KERN_GROUP_PATTERN.match(left)
            right_match = UFO_KERN_GROUP_PATTERN.match(right)
            if left_match:
                left = "@MMK_L_{}".format(left_match.group(2))
            if right_match:
                right = "@MMK_R_{}".format(right_match.group(2))
            self.font.setKerningForPair(master_id, left, right, value)
