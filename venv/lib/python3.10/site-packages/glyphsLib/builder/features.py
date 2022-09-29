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

from __future__ import annotations

import re
from textwrap import dedent
from io import StringIO
from typing import TYPE_CHECKING

from fontTools.feaLib import ast, parser

from .constants import GLYPHLIB_PREFIX
from .tokens import TokenExpander, PassThruExpander

if TYPE_CHECKING:
    from ufoLib2 import Font

    from ..classes import GSFont, GSFontMaster
    from . import UFOBuilder


ANONYMOUS_FEATURE_PREFIX_NAME = "<anonymous>"
ORIGINAL_FEATURE_CODE_KEY = GLYPHLIB_PREFIX + "originalFeatureCode"
ORIGINAL_CATEGORY_KEY = GLYPHLIB_PREFIX + "originalOpenTypeCategory"


def autostr(automatic):
    return "# automatic\n" if automatic else ""


def to_ufo_master_features(self, ufo, master):
    # Recover the original feature code if it was stored in the user data
    original = master.userData[ORIGINAL_FEATURE_CODE_KEY]
    if original is not None:
        ufo.features.text = original
    else:
        ufo.features.text = _to_ufo_features(
            self.font, ufo, generate_GDEF=self.generate_GDEF, master=master
        )


_LANGUAGE_MAPPING = {
    "dflt": None,
    "AFK": 0x0436,
    "ARA": 0x0C01,
    "ASM": 0x044D,
    "AZE": 0x042C,
    "BEL": 0x0423,
    "BEN": 0x0845,
    "BGR": 0x0402,
    "BRE": 0x047E,
    "CAT": 0x0403,
    "CSY": 0x0405,
    "DAN": 0x0406,
    "DEU": 0x0407,
    "ELL": 0x0408,
    "ENG": 0x0409,
    "ESP": 0x0C0A,
    "ETI": 0x0425,
    "EUQ": 0x042D,
    "FIN": 0x040B,
    "FLE": 0x0813,
    "FOS": 0x0438,
    "FRA": 0x040C,
    "FRI": 0x0462,
    "GRN": 0x046F,
    "GUJ": 0x0447,
    "HAU": 0x0468,
    "HIN": 0x0439,
    "HRV": 0x041A,
    "HUN": 0x040E,
    "HVE": 0x042B,
    "IRI": 0x083C,
    "ISL": 0x040F,
    "ITA": 0x0410,
    "ITA": 0x0410,
    "IWR": 0x040D,
    "JPN": 0x0411,
    "KAN": 0x044B,
    "KAT": 0x0437,
    "KAZ": 0x043F,
    "KHM": 0x0453,
    "KOK": 0x0457,
    "LAO": 0x0454,
    "LSB": 0x082E,
    "LTH": 0x0427,
    "LVI": 0x0426,
    "MAR": 0x044E,
    "MKD": 0x042F,
    "MLR": 0x044C,
    "MLY": 0x043E,
    "MNG": 0x0352,
    "MTS": 0x043A,
    "NEP": 0x0461,
    "NLD": 0x0413,
    "NOB": 0x0414,
    "ORI": 0x0448,
    "PAN": 0x0446,
    "PAS": 0x0463,
    "PLK": 0x0415,
    "PTG": 0x0816,
    "PTG-BR": 0x0416,
    "RMS": 0x0417,
    "ROM": 0x0418,
    "RUS": 0x0419,
    "SAN": 0x044F,
    "SKY": 0x041B,
    "SLV": 0x0424,
    "SQI": 0x041C,
    "SRB": 0x081A,
    "SVE": 0x041D,
    "TAM": 0x0449,
    "TAT": 0x0444,
    "TEL": 0x044A,
    "THA": 0x041E,
    "TIB": 0x0451,
    "TRK": 0x041F,
    "UKR": 0x0422,
    "URD": 0x0420,
    "USB": 0x042E,
    "UYG": 0x0480,
    "UZB": 0x0443,
    "VIT": 0x042A,
    "WEL": 0x0452,
    "ZHH": 0x0C04,
    "ZHS": 0x0804,
    "ZHT": 0x0404,
}

_REVERSE_LANGUAGE_MAPPING = {v: k for v, k in _LANGUAGE_MAPPING.items()}


def _to_name_langID(language):
    if language not in _LANGUAGE_MAPPING:
        raise ValueError(f"Unknown name language: {language}")
    return _LANGUAGE_MAPPING[language]


def _to_glyphs_language(langID):
    if langID not in _REVERSE_LANGUAGE_MAPPING:
        raise ValueError(f"Unknown name langID: {langID}")
    return _REVERSE_LANGUAGE_MAPPING[langID]


def _to_ufo_features(
    font: GSFont,
    ufo: Font | None = None,
    generate_GDEF: bool = False,
    master: GSFontMaster | None = None,
) -> str:
    """Convert GSFont features, including prefixes and classes, to UFO.

    Optionally, build a GDEF table definiton, excluding 'skip_export_glyphs'.
    """
    if not master:
        expander = PassThruExpander()
    else:
        expander = TokenExpander(font, master)

    prefixes = []
    for prefix in font.featurePrefixes:
        strings = []
        if prefix.name != ANONYMOUS_FEATURE_PREFIX_NAME:
            strings.append("# Prefix: %s\n" % prefix.name)
        strings.append(autostr(prefix.automatic))
        strings.append(expander.expand(prefix.code))
        prefixes.append("".join(strings))

    prefix_str = "\n\n".join(prefixes)

    class_defs = []
    for class_ in font.classes:
        prefix = "@" if not class_.name.startswith("@") else ""
        name = prefix + class_.name
        class_defs.append(
            "{}{} = [ {}\n];".format(
                autostr(class_.automatic), name, expander.expand(class_.code)
            )
        )
    class_str = "\n\n".join(class_defs)

    feature_defs = []
    for feature in font.features:
        code = expander.expand(feature.code)
        lines = ["feature %s {" % feature.name]
        notes = feature.notes
        feature_names = None
        if font.format_version == 2 and notes:
            m = re.search("(featureNames {.+};)", notes, flags=re.DOTALL)
            if m:
                name = m.groups()[0]
                # Remove the name from the note
                notes = notes.replace(name, "").strip()
                feature_names = name.splitlines()
            else:
                m = re.search(r"^(Name: (.+))", notes)
                if m:
                    line, name = m.groups()
                    # Remove the name from the note
                    notes = notes.replace(line, "").strip()
                    # Replace special chars backslash and doublequote for AFDKO syntax
                    name = name.replace("\\", r"\005c").replace('"', r"\0022")
                    feature_names = ["featureNames {", f'  name "{name}";', "};"]
        elif font.format_version == 3 and feature.labels:
            feature_names = []
            feature_names.append("featureNames {")
            for label in feature.labels:
                langID = _to_name_langID(label["language"])
                name = label["value"]
                name = name.replace("\\", r"\005c").replace('"', r"\0022")
                if langID is None:
                    feature_names.append(f'  name "{name}";')
                else:
                    feature_names.append(f'  name 3 1 0x{langID:X} "{name}";')
            feature_names.append("};")
        if notes:
            lines.append("# notes:")
            lines.extend("# " + line for line in notes.splitlines())
        if feature_names:
            lines.extend(feature_names)
        if feature.automatic:
            lines.append("# automatic")
        if feature.disabled:
            lines.append("# disabled")
            lines.extend("#" + line for line in code.splitlines())
        else:
            lines.append(code)
        lines.append("} %s;" % feature.name)
        feature_defs.append("\n".join(lines))
    fea_str = "\n\n".join(feature_defs)

    if generate_GDEF:
        assert ufo is not None
        regenerate_opentype_categories(font, ufo)

    full_text = "\n\n".join(filter(None, [class_str, prefix_str, fea_str])) + "\n"
    return full_text if full_text.strip() else ""


def _build_public_opentype_categories(ufo: Font) -> dict[str, str]:
    """Returns a dictionary mapping glyph names to GDEF categories.

    Does not handle ligature carets. A GDEF table with both categories and
    ligature carets is generated by ufo2ft's GdefFeatureWriter at compile time,
    using the categories dict and glyph data.

    Determining the categories requires anchor propagation or user care to work
    as expected, as Glyphs.app also looks at anchors for classification:

    * Base: any glyph that has an attaching anchor (such as "top"; "_top" does
      not count) and is neither classified as Ligature nor Mark using the
      definitions below;
    * Ligature: if subCategory is "Ligature" and the glyph has at least one
      attaching anchor;
    * Mark: if category is "Mark" and subCategory is either "Nonspacing" or
      "Spacing Combining";
    * Compound: never assigned by Glyphs.app.

    See:

    * https://github.com/googlefonts/glyphsLib/issues/85
    * https://github.com/googlefonts/glyphsLib/pull/100#issuecomment-275430289
    """
    from glyphsLib import glyphdata

    categories: dict[str, str] = {}
    category_key = GLYPHLIB_PREFIX + "category"
    subCategory_key = GLYPHLIB_PREFIX + "subCategory"

    # NOTE: We can generate the category even for glyphs that are not exported,
    # because entries don't have to exist in the final fonts.
    for glyph in ufo:
        glyph_name = glyph.name
        assert glyph_name is not None

        has_attaching_anchor = False
        for anchor in glyph.anchors:
            name = anchor.name
            if name and not name.startswith("_"):
                has_attaching_anchor = True

        # First check glyph.lib for category/subCategory overrides. Otherwise,
        # use global values from GlyphData.
        glyphinfo = glyphdata.get_glyph(
            glyph_name, unicodes=[f"{c:04X}" for c in glyph.unicodes]
        )
        category = glyph.lib.get(category_key) or glyphinfo.category
        subCategory = glyph.lib.get(subCategory_key) or glyphinfo.subCategory

        if subCategory == "Ligature" and has_attaching_anchor:
            categories[glyph_name] = "ligature"
        elif category == "Mark" and (
            subCategory == "Nonspacing" or subCategory == "Spacing Combining"
        ):
            categories[glyph_name] = "mark"
        elif has_attaching_anchor:
            categories[glyph_name] = "base"

    return categories


def regenerate_gdef(self: UFOBuilder) -> None:
    for source in self._sources.values():
        regenerate_opentype_categories(self.font, source.font)


def regenerate_opentype_categories(font: GSFont, ufo: Font) -> None:
    categories = _build_public_opentype_categories(ufo)

    # Prefer already stored categories for round-tripping. This will provide
    # newly guessed categories only for new glyphs. The data is stored
    # GSFont-wide to capture bracket glyphs that we create for UFOs and fold
    # when going back.
    roundtripping_categories = font.userData[ORIGINAL_CATEGORY_KEY]
    if roundtripping_categories is not None:
        categories.update(roundtripping_categories)

    if categories:
        ufo.lib["public.openTypeCategories"] = categories


def _replace_block(kind, tag, repl, features):
    if not repl.endswith("\n"):
        repl += "\n"
    return re.sub(
        rf"(?<=^{kind} {tag} {{\n)(.*?)(?=^}} {tag};$)",
        repl,
        features,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )


def replace_feature(tag, repl, features):
    return _replace_block("feature", tag, repl, features)


def replace_table(tag, repl, features):
    return _replace_block("table", tag, repl, features)


def replace_prefixes(repl_map, features_text, glyph_names=None):
    """Replace all '# Prefix: NAME' sections in features.

    Args:
        repl_map: Dict[str, str]: dictionary keyed by prefix name containing
            feature code snippets to be replaced.
        features_text: str: feature text to be parsed.
        glyph_names: Optional[Sequence[str]]: list of valid glyph names, used
            by feaLib Parser to distinguish glyph name tokens containing '-' from
            glyph ranges such as 'a-z'.

    Returns:
        str: new feature text with replaced prefix paragraphs.
    """
    from glyphsLib.classes import GSFont

    temp_font = GSFont()
    _to_glyphs_features(temp_font, features_text, glyph_names=glyph_names)

    for prefix in temp_font.featurePrefixes:
        if prefix.name in repl_map:
            prefix.code = repl_map[prefix.name]

    return _to_ufo_features(temp_font)


def to_glyphs_features(self):
    if not self.designspace.sources:
        # Needs at least one UFO
        return

    # Handle differing feature files between input UFOs
    # For now: switch to very simple strategy if there is any difference
    # TODO: (jany) later, use a merge-as-we-go strategy where all discovered
    #   features go into the GSFont's features, and custom parameters are used
    #   to disable features on masters that didn't have them originally.
    if _features_are_different_across_ufos(self):
        if self.minimize_ufo_diffs:
            self.logger.warning(
                "Feature files are different across UFOs. The produced Glyphs "
                "file will have no editable features."
            )
            # Do all UFOs, not only the first one
            _to_glyphs_features_basic(self)
            return
        self.logger.warning(
            "Feature files are different across UFOs. The produced Glyphs "
            "file will reflect only the features of the first UFO."
        )

    # Split the feature file of the first UFO into GSFeatures
    ufo = self.designspace.sources[0].font
    if ufo.features.text is None:
        return
    _to_glyphs_features(
        self.font,
        ufo.features.text,
        glyph_names=ufo.keys(),
        glyphs_module=self.glyphs_module,
    )

    # Store GDEF category data GSFont-wide to capture bracket glyphs that we
    # create for UFOs and fold when going back.
    opentype_categories = ufo.lib.get("public.openTypeCategories")
    if opentype_categories is not None:
        self.font.userData[ORIGINAL_CATEGORY_KEY] = opentype_categories


def _to_glyphs_features(font, features_text, glyph_names=None, glyphs_module=None):
    """Import features text in GSFont, split into prefixes, features and classes.

    Args:
        font: GSFont
        feature_text: str
        glyph_names: Optional[Sequence[str]]
        glyphs_module: Optional[Any]
    """
    document = FeaDocument(features_text, glyph_names)
    processor = FeatureFileProcessor(document, glyphs_module)
    processor.to_glyphs(font)


def _features_are_different_across_ufos(self):
    # FIXME: requires that features are in the same order in all feature files;
    #   the only allowed differences are whitespace
    # Construct iterator over full UFOs, layer sources do not have a font object set.
    full_sources = (s for s in self.designspace.sources if not s.layerName)
    reference = next(full_sources).font.features.text or ""
    reference = _normalize_whitespace(reference)
    for source in full_sources:
        other = _normalize_whitespace(source.font.features.text or "")
        if reference != other:
            return True
    return False


def _normalize_whitespace(text):
    # FIXME: does not take into account "significant" whitespace like
    # whitespace in a UI string
    return re.sub(r"\s+", " ", text)


def _to_glyphs_features_basic(self):
    prefix = self.glyphs_module.GSFeaturePrefix()
    prefix.name = "WARNING"
    prefix.code = dedent(
        """\
        # Do not use Glyphs to edit features.
        #
        # This Glyphs file was made from several UFOs that had different
        # features. As a result, the features are not editable in Glyphs and
        # the original features will be restored when you go back to UFOs.
    """
    )
    self.font.featurePrefixes.append(prefix)
    for master_id, source in self._sources.items():
        master = self.font.masters[master_id]
        master.userData[ORIGINAL_FEATURE_CODE_KEY] = source.font.features.text


class FeaDocument:
    """Parse the string of a fea code into statements."""

    def __init__(self, text, glyph_set=None):
        feature_file = StringIO(text)
        glyph_names = glyph_set if glyph_set is not None else ()
        parser_ = parser.Parser(
            feature_file, glyphNames=glyph_names, followIncludes=False
        )
        self._doc = parser_.parse()
        self.statements = self._doc.statements
        self._lines = text.splitlines(True)  # keepends=True
        self._build_end_locations()

    def text(self, statements):
        """Recover the original fea code of the given statements from the
        given block.
        """
        return "".join(self._statement_text(st) for st in statements)

    def _statement_text(self, statement):
        _, begin_line, begin_char = statement.location
        _, end_line, end_char = statement.end_location
        lines = self._lines[begin_line - 1 : end_line]
        if lines:
            # In case it's the same line, we need to trim the end first
            lines[-1] = lines[-1][:end_char]
            lines[0] = lines[0][begin_char - 1 :]
        return "".join(lines)

    def _build_end_locations(self):
        # The statements in the ast only have their start location, but we also
        # need the end location to find the text in between.
        # FIXME: (jany) maybe feaLib could provide that?
        # Add a fake statement at the end, it's the only one that won't get
        # a proper end_location, but its presence will help compute the
        # end_location of the real last statement(s).
        self._lines.append("#")  # Line corresponding to the fake statement
        fake_location = (None, len(self._lines), 1)
        self._doc.statements.append(
            ast.Comment(text="Sentinel", location=fake_location)
        )
        self._build_end_locations_rec(self._doc)
        # Remove the fake last statement
        self._lines.pop()
        self._doc.statements.pop()

    def _build_end_locations_rec(self, block):
        # To get the end location, we do a depth-first exploration of the ast:
        # When a new statement starts, it means that the previous one ended.
        # When a new statement starts outside of the current block, we must
        # remove the "end-of-block" string from the previous inner statement.
        previous = None
        previous_in_block = None
        for st in block.statements:
            if hasattr(st, "statements"):
                self._build_end_locations_rec(st)
            if previous is not None:
                _, line, char = st.location
                line, char = self._previous_char(line, char)
                previous.end_location = (None, line, char)
            if previous_in_block is not None:
                previous_in_block.end_location = self._in_block_end_location(previous)
                previous_in_block = None
            previous = st
            if hasattr(st, "statements"):
                previous_in_block = st.statements[-1] if st.statements else None

    WHITESPACE_RE = re.compile("\\s")
    WHITESPACE_OR_NAME_RE = re.compile("\\w|\\s")

    def _previous_char(self, line, char):
        char -= 1
        while char == 0:
            line -= 1
            char = len(self._lines[line - 1])
        return line, char

    def _in_block_end_location(self, block):
        _, line, char = block.end_location

        def current_char(line, char):
            return self._lines[line - 1][char - 1]

        # Find the semicolon
        while current_char(line, char) != ";":
            assert self.WHITESPACE_RE.match(current_char(line, char))
            line, char = self._previous_char(line, char)
        # Skip it
        line, char = self._previous_char(line, char)
        # Skip the whitespace and table/feature name
        while self.WHITESPACE_OR_NAME_RE.match(current_char(line, char)):
            line, char = self._previous_char(line, char)
        # It should be the closing bracket
        assert current_char(line, char) == "}"
        # Skip it and we're done
        line, char = self._previous_char(line, char)

        return None, line, char


class PeekableIterator:
    """Helper class to iterate and peek over a list."""

    def __init__(self, list):
        self.index = 0
        self.list = list

    def has_next(self, n=0):
        return (self.index + n) < len(self.list)

    def __iter__(self):
        return self

    def __next__(self):
        res = self.list[self.index]
        self.index += 1
        return res

    next = __next__

    def peek(self, n=0):
        return self.list[self.index + n]


class FeatureFileProcessor:
    """Put fea statements into the correct fields of a GSFont."""

    def __init__(self, doc, glyphs_module=None):
        self.doc = doc
        if glyphs_module is None:
            from glyphsLib import classes as glyphs_module
        self.glyphs_module = glyphs_module
        self.statements = PeekableIterator(doc.statements)
        self._font = None

    def to_glyphs(self, font):
        self._font = font
        self._process_file()

    PREFIX_RE = re.compile("^# Prefix: (.*)$")
    AUTOMATIC_RE = re.compile("^# automatic$")
    DISABLED_RE = re.compile("^# disabled$")
    NOTES_RE = re.compile("^# notes:$")

    def _process_file(self):
        unhandled_root_elements = []
        while self.statements.has_next():
            if (
                self._process_prefix()
                or self._process_glyph_class_definition()
                or self._process_feature_block()
                or self._process_gdef_table_block()
            ):
                # Flush any unhandled root elements into an anonymous prefix
                if unhandled_root_elements:
                    prefix = self.glyphs_module.GSFeaturePrefix()
                    prefix.name = ANONYMOUS_FEATURE_PREFIX_NAME
                    prefix.code = self._rstrip_newlines(
                        self.doc.text(unhandled_root_elements)
                    )
                    self._font.featurePrefixes.append(prefix)
                    del unhandled_root_elements[:]  # list.clear() in Python 3.
            else:
                # FIXME: (jany) Maybe print warning about unhandled fea block?
                unhandled_root_elements.append(next(self.statements))
        # Flush any unhandled root elements into an anonymous prefix
        if unhandled_root_elements:
            prefix = self.glyphs_module.GSFeaturePrefix()
            prefix.name = ANONYMOUS_FEATURE_PREFIX_NAME
            prefix.code = self._rstrip_newlines(self.doc.text(unhandled_root_elements))
            self._font.featurePrefixes.append(prefix)

    def _process_prefix(self):
        st = self.statements.peek()
        if not isinstance(st, ast.Comment):
            return False
        match = self.PREFIX_RE.match(st.text)
        if not match:
            return False
        next(self.statements)

        # Consume statements that are part of the feature prefix
        prefix_statements = []
        while self.statements.has_next():
            st = self.statements.peek()
            # Don't consume statements that are treated specially
            if isinstance(
                st, (ast.GlyphClassDefinition, ast.FeatureBlock, ast.TableBlock)
            ):
                break
            # Don't comsume a comment if it is the start of another prefix...
            if isinstance(st, ast.Comment):
                if self.PREFIX_RE.match(st.text):
                    break
                # ...or if it is the "automatic" comment just before a class
                if self.statements.has_next(1):
                    next_st = self.statements.peek(1)
                    if self.AUTOMATIC_RE.match(st.text) and isinstance(
                        next_st, ast.GlyphClassDefinition
                    ):
                        break
            prefix_statements.append(next(self.statements))

        prefix = self.glyphs_module.GSFeaturePrefix()
        prefix.name = match.group(1)
        automatic, prefix_statements = self._pop_comment(
            prefix_statements, self.AUTOMATIC_RE
        )
        prefix.automatic = bool(automatic)
        prefix.code = self._rstrip_newlines(self.doc.text(prefix_statements), 2)
        self._font.featurePrefixes.append(prefix)
        return True

    def _process_glyph_class_definition(self):
        automatic = False
        st = self.statements.peek()
        if isinstance(st, ast.Comment):
            if self.AUTOMATIC_RE.match(st.text):
                automatic = True
                st = self.statements.peek(1)
            else:
                return False
        if not isinstance(st, ast.GlyphClassDefinition):
            return False
        if automatic:
            next(self.statements)
        next(self.statements)
        glyph_class = self.glyphs_module.GSClass()
        glyph_class.name = st.name
        # Call st.glyphs.asFea() because it updates the 'original' field
        # However, we don't use the result of `asFea` because it expands
        # classes in a strange way
        # FIXME: (jany) maybe open an issue if feaLib?
        st.glyphs.asFea()
        elements = []
        try:
            if st.glyphs.original:
                for glyph in st.glyphs.original:
                    try:
                        # Class name (MarkClassName object)
                        elements.append("@" + glyph.markClass.name)
                    except AttributeError:
                        try:
                            # Class name (GlyphClassName object)
                            elements.append("@" + glyph.glyphclass.name)
                        except AttributeError:
                            try:
                                # Class name (GlyphClassDefinition object)
                                # FIXME: (jany) why not always the same type?
                                elements.append("@" + glyph.name)
                            except AttributeError:
                                # Glyph name
                                elements.append(glyph)
            else:
                elements = st.glyphSet()
        except AttributeError:
            # Single class
            try:
                # Class name (MarkClassName object)
                elements.append("@" + st.glyphs.markClass.name)
            except AttributeError:
                # Class name (GlyphClassName object)
                elements.append("@" + st.glyphs.glyphclass.name)
        glyph_class.code = " ".join(elements)
        glyph_class.automatic = bool(automatic)
        self._font.classes.append(glyph_class)
        return True

    def _process_feature_block(self):
        st = self.statements.peek()
        if not isinstance(st, ast.FeatureBlock):
            return False
        next(self.statements)
        contents = st.statements
        automatic, contents = self._pop_comment(contents, self.AUTOMATIC_RE)
        disabled, disabled_text, contents = self._pop_comment_block(
            contents, self.DISABLED_RE
        )
        notes, notes_text, contents = self._pop_comment_block(contents, self.NOTES_RE)
        feature = self.glyphs_module.GSFeature()
        feature.name = st.name
        feature.automatic = bool(automatic)
        if feature.automatic:
            # See if there is a feature names block in the code that should be
            # written to the notes.
            for i, statement in enumerate(contents):
                if (
                    isinstance(statement, ast.NestedBlock)
                    and statement.block_name == "featureNames"
                ):
                    feature_names = contents[i]
                    if feature_names.statements:
                        # If there is only one name has default platformID,
                        # platEncID and langID, write it using the simple
                        # syntax. Otherwise write out the full featureNames
                        # statement.
                        if self._font.format_version == 2:
                            name = feature_names.statements[0]
                            if (
                                len(feature_names.statements) == 1
                                and name.platformID == 3
                                and name.platEncID == 1
                                and name.langID == 0x409
                            ):
                                name_text = f"Name: {name.string}"
                            else:
                                name_text = str(feature_names)
                            notes_text = name_text + "\n" + notes_text
                            notes = True
                            contents.pop(i)
                        elif self._font.format_version == 3:
                            labels = []
                            for name in feature_names.statements:
                                if name.platformID == 3 and name.platEncID == 1:
                                    language = _to_glyphs_language(name.langID)
                                    labels.append(
                                        dict(language=language, value=name.string)
                                    )
                            if len(labels) == len(feature_names.statements):
                                feature.labels = labels
                                contents.pop(i)
                    break
        if notes:
            feature.notes = notes_text
        if disabled:
            feature.code = disabled_text
            feature.disabled = True
            # FIXME: (jany) check that the user has not added more new code
            #    after the disabled comment. Maybe start by checking whether
            #    the block is only made of comments
        else:
            feature.code = self._rstrip_newlines(self.doc.text(contents))
        self._font.features.append(feature)
        return True

    def _process_gdef_table_block(self):
        st = self.statements.peek()
        if not isinstance(st, ast.TableBlock) or st.name != "GDEF":
            return False
        # TODO: read an existing GDEF table and do something with it?
        # For now, this function returns False to say that it has not handled
        # the GDEF table, so it will be stored in Glyphs as a prefix with other
        # "unhandled root elements".
        return False

    def _pop_comment(self, statements, comment_re):
        """Look for the comment that matches the given regex.
        If it matches, return the regex match object and list of statements
        without the special one.
        """
        res = []
        match = None
        for st in statements:
            if match or not isinstance(st, ast.Comment):
                res.append(st)
                continue
            match = comment_re.match(st.text)
            if not match:
                res.append(st)
        return match, res

    def _pop_comment_block(self, statements, header_re):
        """Look for a series of comments that start with one that matches the
        regex. If the first comment is found, all subsequent comments are
        popped from statements, concatenated and dedented and returned.
        """
        res = []
        comments = []
        match = None
        st_iter = iter(statements)
        # Look for the header
        for st in st_iter:
            if isinstance(st, ast.Comment):
                match = header_re.match(st.text)
                if match:
                    # Drop this comment an move on to consuming the block
                    break
                else:
                    res.append(st)
            else:
                res.append(st)
        # Consume consecutive comments
        for st in st_iter:
            if isinstance(st, ast.Comment):
                comments.append(st)
            else:
                # The block is over, keep the rest of the statements
                res.append(st)
                break
        # Keep the rest of the statements
        res.extend(list(st_iter))
        # Inside the comment block, drop the pound sign and any common indent
        return match, dedent("".join(c.text[1:] + "\n" for c in comments)), res

    # Strip up to the given number of newlines from the right end of the string
    def _rstrip_newlines(self, string, number=1):
        for _ in range(number):
            if string and string[-1] == "\n":
                string = string[:-1]
        return string
