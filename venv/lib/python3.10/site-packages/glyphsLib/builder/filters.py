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


import logging
import re

from glyphsLib.util import cast_to_number_or_bool, reverse_cast_to_number_or_bool

logger = logging.getLogger(__name__)


def parse_glyphs_filter(filter_str, is_pre=False):
    """Parses glyphs custom filter string into a dict object that
    ufo2ft can consume.

     Reference:
         ufo2ft: https://github.com/googlefonts/ufo2ft
         Glyphs 2.3 Handbook July 2016, p184

     Args:
         filter_str - a string of glyphs app filter

     Return:
         A dictionary contains the structured filter.
         Return None if parse failed.
    """
    elements = filter_str.split(";")

    if elements[0] == "":
        logger.error(
            "Failed to parse glyphs filter, expecting a filter name: \
             %s",
            filter_str,
        )
        return None

    result = {"name": elements[0]}
    for idx, elem in enumerate(elements[1:]):
        if not elem:
            # skip empty arguments
            continue
        if ":" in elem:
            # Key value pair
            key, value = elem.split(":", 1)
            if key.lower() in ["include", "exclude"]:
                if idx != len(elements[1:]) - 1:
                    logger.error(
                        "{} can only present as the last argument in the filter. "
                        "{} is ignored.".format(key, elem)
                    )
                    continue
                result[key.lower()] = re.split("[ ,]+", value)
            else:
                if "kwargs" not in result:
                    result["kwargs"] = {}
                result["kwargs"][key] = cast_to_number_or_bool(value)
        else:
            if "args" not in result:
                result["args"] = []
            result["args"].append(cast_to_number_or_bool(elem))
    if is_pre:
        result["pre"] = True
    return result


def write_glyphs_filter(result):
    elements = [result["name"]]
    if "args" in result:
        for arg in result["args"]:
            elements.append(reverse_cast_to_number_or_bool(arg))
    if "kwargs" in result:
        for key, arg in result["kwargs"].items():
            if key.lower() not in ("include", "exclude"):
                elements.append(key + ":" + reverse_cast_to_number_or_bool(arg))
        for key, arg in result["kwargs"].items():
            if key.lower() in ("include", "exclude"):
                elements.append(key + ":" + reverse_cast_to_number_or_bool(arg))
    for key, arg in result.items():
        if key.lower() in ("include", "exclude"):
            elements.append(key + ":" + ",".join(arg))
    return ";".join(elements)
