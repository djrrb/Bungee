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

# TODO: (jany) merge with builder/common.py

import logging
import itertools
import os
import shutil
from fontTools.misc.textTools import num2binary

logger = logging.getLogger(__name__)


def build_ufo_path(out_dir, family_name, style_name):
    """Build string to use as a UFO path."""

    return os.path.join(
        out_dir,
        "%s-%s.ufo"
        % ((family_name or "").replace(" ", ""), (style_name or "").replace(" ", "")),
    )


def open_ufo(path, font_class, **kwargs):
    try:
        return font_class.open(path, lazy=False, **kwargs)  # ufoLib2
    except AttributeError:
        return font_class(path, **kwargs)  # defcon, fontParts, etc.


def write_ufo(ufo, out_dir):
    """Write a UFO."""

    out_path = build_ufo_path(out_dir, ufo.info.familyName, ufo.info.styleName)

    logger.info("Writing %s" % out_path)
    clean_ufo(out_path)
    ufo.save(out_path)


def clean_ufo(path):
    """Make sure old UFO data is removed, as it may contain deleted glyphs."""

    if path.endswith(".ufo") and os.path.exists(path):
        shutil.rmtree(path)


def ufo_create_background_layer_for_all_glyphs(ufo_font):
    """Create a background layer for all glyphs in ufo_font if not present to
    reduce roundtrip differences."""

    if "public.background" in ufo_font.layers:
        background = ufo_font.layers["public.background"]
    else:
        background = ufo_font.newLayer("public.background")

    for glyph in ufo_font:
        if glyph.name not in background:
            background.newGlyph(glyph.name)


def cast_to_number_or_bool(inputstr):
    """Cast a string to int, float or bool. Return original string if it can't be
    converted.

    Scientific expression is converted into float.
    """
    if inputstr.strip().lower() == "true":
        return True
    elif inputstr.strip().lower() == "false":
        return False
    try:
        return int(inputstr)
    except ValueError:
        try:
            return float(inputstr)
        except ValueError:
            return inputstr


def reverse_cast_to_number_or_bool(input):
    if input is True:
        return "true"  # FIXME: (jany) dubious, glyphs handbook says should be 1
    if input is False:
        return "false"  # FIXME: (jany) dubious, glyphs handbook says should be 0
    return str(input)


def bin_to_int_list(value):
    string = num2binary(value)
    string = string.replace(" ", "")  # num2binary add a space every 8 digits
    return [i for i, v in enumerate(reversed(string)) if v == "1"]


def int_list_to_bin(value):
    result = 0
    for i in value:
        result += 1 << i
    return result


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def tostr(s, encoding="ascii", errors="strict"):
    if not isinstance(s, str):
        return s.decode(encoding, errors)
    else:
        return s
