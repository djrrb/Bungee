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


from .constants import GLYPHS_PREFIX
from glyphsLib.types import Transform, Rect, Point, Size

BACKGROUND_IMAGE_PREFIX = GLYPHS_PREFIX + "backgroundImage."
CROP_KEY = BACKGROUND_IMAGE_PREFIX + "crop"
LOCKED_KEY = BACKGROUND_IMAGE_PREFIX + "locked"
ALPHA_KEY = BACKGROUND_IMAGE_PREFIX + "alpha"


def to_ufo_background_image(self, ufo_glyph, layer):
    """Copy the backgound image from the GSLayer to the UFO Glyph."""
    image = layer.backgroundImage
    if image is None:
        return
    ufo_image = ufo_glyph.image
    ufo_image.fileName = image.path
    ufo_image.transformation = image.transform
    ufo_glyph.lib[CROP_KEY] = list(image.crop)
    ufo_glyph.lib[LOCKED_KEY] = image.locked
    ufo_glyph.lib[ALPHA_KEY] = image.alpha


def to_glyphs_background_image(self, ufo_glyph, layer):
    """Copy the background image from the UFO Glyph to the GSLayer."""
    ufo_image = ufo_glyph.image
    if ufo_image.fileName is None:
        return
    image = self.glyphs_module.GSBackgroundImage()
    image.path = ufo_image.fileName
    image.transform = Transform(*ufo_image.transformation)
    if CROP_KEY in ufo_glyph.lib:
        x, y, w, h = ufo_glyph.lib[CROP_KEY]
        image.crop = Rect(Point(x, y), Size(w, h))
    if LOCKED_KEY in ufo_glyph.lib:
        image.locked = ufo_glyph.lib[LOCKED_KEY]
    if ALPHA_KEY in ufo_glyph.lib:
        image.alpha = ufo_glyph.lib[ALPHA_KEY]
    layer.backgroundImage = image
