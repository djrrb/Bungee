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


import datetime
from glyphsLib.types import parse_datetime

UFO_FORMAT = "%Y/%m/%d %H:%M:%S"


def to_ufo_time(datetime_obj):
    """Format a datetime object as specified for UFOs."""
    return datetime_obj.strftime(UFO_FORMAT)


def from_ufo_time(string):
    """Parses a datetime as specified for UFOs into a datetime object."""
    return datetime.datetime.strptime(string, UFO_FORMAT)


def from_loose_ufo_time(string):
    """Parses a datetime as specified for UFOs into a datetime object,
    or as the Glyphs formet."""
    try:
        return from_ufo_time(string)
    except ValueError:
        return parse_datetime(string)


def to_ufo_color(color):
    if isinstance(color, str):
        color = [int(v) for v in color.split(",")]
    if len(color) == 2:
        # Greyscale color
        color = (color[0], color[0], color[0], color[1])
    elif len(color) == 5:
        # CMYK color
        raise NotImplementedError("CMYK colors are not supported")
    return tuple(c / 255 for c in color)
