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


from collections import OrderedDict
import glyphsLib
import logging
import openstep_plist
import sys


logger = logging.getLogger(__name__)


class Parser:
    """Parses Python dictionaries from Glyphs files."""

    def __init__(self, current_type=OrderedDict, format_version=2):
        self.current_type = current_type
        self.format_version = format_version

    def parse(self, d):
        try:
            if isinstance(d, str):
                d = self._fl7_format_clean(d)
                d = openstep_plist.loads(d, use_numbers=True)
            elif isinstance(d, bytes):
                d = self._fl7_format_clean(d)
                d = openstep_plist.loads(d.decode(), use_numbers=True)
            result = self._parse(d)
        except openstep_plist.parser.ParseError as e:
            raise ValueError("Failed to parse file") from e
        return result

    def _fl7_format_clean(self, d):
        """FontLab 7 glyphs source format exports include a final closing semicolon.
        This method removes the semicolon before passing the string to the parser."""
        # see https://github.com/googlefonts/fontmake/issues/806
        if isinstance(d, str):
            d = d.rstrip(";\n")
        elif isinstance(d, bytes):
            d = d.rstrip(b";\n")
        return d

    def _parse(self, d, new_type=None):
        self.current_type = new_type or self.current_type
        if isinstance(d, list):
            return self._parse_list(d, new_type)
        if isinstance(d, (dict, OrderedDict)):
            return self._parse_dict(d, new_type)
        return d

    def _parse_list(self, d, new_type=None):
        self.current_type = new_type or self.current_type
        return [self._parse(x, new_type) for x in d]

    def parse_into_object(self, res, value):
        return self._parse_dict_into_object(res, value)

    def _parse_dict(self, text, new_type=None):
        """Parse a dictionary from source text starting at i."""
        old_current_type = self.current_type
        new_type = new_type or self.current_type
        if new_type is None:
            # customparameter.value needs to be set from the found value
            new_type = dict
        elif type(new_type) == list:
            new_type = new_type[0]
        res = new_type()
        self._parse_dict_into_object(res, text)
        self.current_type = old_current_type
        return res

    def _parse_dict_into_object(self, res, d):
        for name in d.keys():
            sane_name = name.replace(".", "__")
            if hasattr(res, f"_parse_{sane_name}_dict"):
                getattr(res, f"_parse_{sane_name}_dict")(self, d[name])
            elif isinstance(res, (dict, OrderedDict)):
                result = self._parse(d[name])
                try:
                    res[name] = result
                except (TypeError, KeyError):  # hmmm...
                    res = {}  # ugly, this fixes nested dicts in customparameters
                    res[name] = result
            else:
                res[name] = d[name]


def load(fp):
    """Read a .glyphs file. 'fp' should be (readable) file object.
    Return a GSFont object.
    """
    p = Parser(current_type=glyphsLib.classes.GSFont)
    logger.info("Parsing .glyphs file")
    res = glyphsLib.classes.GSFont()
    p.parse_into_object(res, openstep_plist.load(fp, use_numbers=True))
    return res


def loads(s):
    """Read a .glyphs file from a (unicode) str object, or from
    a UTF-8 encoded bytes object.
    Return a GSFont object.
    """
    p = Parser(current_type=glyphsLib.classes.GSFont)
    logger.info("Parsing .glyphs file")
    res = glyphsLib.classes.GSFont()
    p.parse_into_object(res, openstep_plist.loads(s, use_numbers=True))
    return res


def main(args=None):
    """Roundtrip the .glyphs file given as an argument."""
    for arg in args:
        fp = open(arg, "r", encoding="utf-8")
        glyphsLib.dump(load(fp), sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1:])
