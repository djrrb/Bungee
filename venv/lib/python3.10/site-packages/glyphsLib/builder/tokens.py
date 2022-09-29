import re
from collections import OrderedDict


def _like(got, expected):
    expected = expected.replace("?", ".")
    expected = expected.replace("*", ".*")
    # Technically we should be a bit stricter than this
    return re.match(expected, str(got))


class TokenExpander:

    number_token_re = r"\$\{([^}]+)\}"
    glyph_predicate_re = r"\$\[([^\]]+)\]"
    bare_number_value_re = r"\$(\w+)\b"

    def __init__(self, font, master):
        self.font = font
        self.master = master

    def expand(self, featurecode):
        self.featurecode = featurecode
        self.output = ""
        self.position = 0
        while len(self.featurecode) > 0:
            if self.featurecode[0] == "$":
                self.parse_token()
            m = re.match(r"^[^$]+", self.featurecode)
            if m:
                self.output += m[0]
                self._consume_match(m)
        return self.output

    def _consume_match(self, m):
        self.position += len(m[0])
        self.featurecode = self.featurecode[len(m[0]) :]

    def parse_token(self):
        for (regexp, parser) in [
            (self.number_token_re, self.parse_number_token),
            (self.glyph_predicate_re, self.parse_glyph_predicate),
            (self.bare_number_value_re, self.parse_bare_number_value),
        ]:
            m = re.match(regexp, self.featurecode)
            if m:
                self.output += parser(m[1])
                self._consume_match(m)
                return

        raise ValueError(
            "Unknown token type: '%s' at position %i"
            % (self.featurecode[:10], self.position)
        )

    def parse_bare_number_value(self, number):
        # Find index of number
        try:
            index = [metric.name for metric in self.font.numbers].index(number)
        except ValueError as e:
            raise ValueError(
                "Unknown number token '$%s' at position %i" % (number, self.position)
            ) from e

        value = self.master.numbers[index]
        # We don't add this to the output, because we use the same routine in
        # number tokens
        return str(value)

    def parse_number_token(self, token):
        # These things can contain: number tokens, literal numbers, +-*/, space
        # We will also allow ()
        expression = ""
        originaltoken = token
        while len(token) > 0:
            if token[0] in "0123456789+-*/() ":
                expression += token[0]
                token = token[1:]
                continue
            # Assume it's a number token
            m = re.match(r"^(\w+)", token)
            if not m:
                raise ValueError(
                    "Unknown character %s in number token '%s' at position %i"
                    % (token[0], originaltoken, self.position)
                )
            expression += self.parse_bare_number_value(m[1])
            token = token[len(m[0]) :]
        # This expression is now just numbers and operators - safe to eval,
        # but needs to be an integer
        return "%i" % eval(expression)

    def parse_glyph_predicate(self, token):
        self.originaltoken = token
        self.glyph_predicate = token  # Use a little subparser thing here
        return " ".join(self._parse_glyph_predicate_to_array())

    # All following methods are part of the glyph predicate subparser

    gsglyph_predicate_objects = [
        "hasAlignedWidth",
        "hasAnnotations",
        "hasComponents",
        "hasCorners",
        "hasCustomGlyphInfo",
        "hasHints",
        "hasPostScriptHints",
        "hasSpecialLayers",
        "hasTrueTypeHints",
        "isAligned",
        "isAppleColorGlyph",
        "isColorGlyph",
        "isCornerGlyph",
        "isHangulKeyGlyph",
        "isSVGColorGlyph",
        "isSmartGlyph",
        "justLocked",
        "locked",
        "mastersCompatible",
        "outlineHasChanges",
        "case",
        "changeCount",
        "colorIndex",
        "countOfLayers",
        "countOfPartsSettings",
        "countOfTags",
        "countOfUnicodes",
        "direction",
        "baseString",
        "bottomKerningGroup",
        "bottomMetricsKey",
        "category",
        "charName",
        "charString",
        "description",
        "glyphDataEntryString",
        "lastChange",
        "leftKerningGroup",
        "leftKerningKey",
        "leftMetricsKey",
        "name",
        "note",
        "production",
        "productionName",
        "rightKerningGroup",
        "rightKerningKey",
        "rightMetricsKey",
        "script",
        "sortName",
        "sortNameKeep",
        "string",
        "subCategory",
        "topKerningGroup",
        "topMetricsKey",
        "unicode",
        "unicodeChar",
        "unicodeString",
        "vertWidthMetricsKey",
        "widthMetricsKey",
    ]
    gsglyph_predicate_object_re = (
        r"^\s*(" + "|".join(gsglyph_predicate_objects) + r"\b)"
    )
    comparators_re = (
        r"(?i)\s*(beginswith|contains|endswith|like|matches|==?|>=|"
        r"=>|<=|=<|!=|<>|>|<|between|in)\s*"
    )

    def _parse_glyph_predicate_to_array(self):
        invert = self._parse_optional_not()
        obj = self._parse_object()
        comparator = self._parse_comparator()
        if comparator == "in" or comparator == "between":
            expected = self._parse_aggregation()
        else:
            expected = self._parse_value()

        glyphs = OrderedDict({})
        for g in self.font.glyphs:
            v = self._get_value_for_glyph(g, obj)
            truth = self._compare(v, comparator, expected)
            if invert:
                truth = not truth
            if truth:
                glyphs[g.name] = None

        compound = self._parse_compound()
        if compound:
            if compound == "OR":
                for g2 in self._parse_glyph_predicate_to_array():
                    glyphs[g2] = None
            else:  # AND
                otherset = set(self._parse_glyph_predicate_to_array())
                return [g for g in glyphs.keys() if g in otherset]

        return list(glyphs.keys())

    def _parse_optional_not(self):
        m = re.match(r"^\s*not\s+", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return True
        return False

    def _parse_error_in_predicate(self, thing):
        found = re.match(r"^\s*(\S+)", self.glyph_predicate)
        raise ValueError(
            "Expected a %s, found '%s' in predicate '%s'"
            % (thing, found[0], self.originaltoken)
        )

    def _parse_object(self):
        m = re.match(
            self.gsglyph_predicate_object_re, self.glyph_predicate
        ) or self._parse_error_in_predicate("known glyph predicate object")
        self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
        return m[1]

    def _parse_comparator(self):
        m = re.match(
            self.comparators_re, self.glyph_predicate
        ) or self._parse_error_in_predicate("comparator")
        normalize_comparators = {"=": "==", "=>": ">=", "=<": "<=", "<>": "!="}
        self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
        return normalize_comparators.get(m[1], m[1]).lower()

    def _parse_value(self):
        m = re.match(r'\s*"([^"]+)"', self.glyph_predicate) or re.match(
            r"\s*'([^']+)'", self.glyph_predicate
        )  # Doesn't handle string escapes
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return m[1]
        m = re.match(r"(?i)\s*(yes|true)", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return True
        m = re.match(r"(?i)\s*(no|false)", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return False
        # The tutorial says number values can be floats, but I don't think they can
        m = re.match(r"\s*(\d+)", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return int(m[1])

        # Keyword constants
        m = re.match(r"\s*(\w+)", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return m[1]
        self._parse_error_in_predicate("value")

    def _get_value_for_glyph(self, g, value):
        try:
            return getattr(g, value)
        except AttributeError as exc:
            raise ValueError(
                "Glyphs attribute %s used in predicate '%s'"
                " but glyphsLib does not support it" % (value, self.originaltoken)
            ) from exc

    apply_comparators = {
        "beginswith": lambda got, exp: str(got).startswith(exp),
        "contains": lambda got, exp: exp in str(got),
        "endswith": lambda got, exp: str(got).endswith(exp),
        "like": _like,
        "matches": lambda got, exp: re.search(exp, str(got)),
        "==": lambda got, exp: got == exp,
        "!=": lambda got, exp: got != exp,
        ">=": lambda got, exp: got >= exp,
        "<=": lambda got, exp: got <= exp,
        "between": lambda got, exp: got >= exp[0] and got <= exp[1],
        "in": lambda got, exp: got in exp,
    }

    def _compare(self, got, comparator, expected):
        return self.apply_comparators[comparator](got, expected)

    def _parse_compound(self):
        m = re.match(r"(?i)\s*(and|&&)", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return "AND"

        m = re.match(r"(?i)\s*(or|\|\|)", self.glyph_predicate)
        if m:
            self.glyph_predicate = self.glyph_predicate[len(m[0]) :]
            return "OR"

        return False


class PassThruExpander:
    def expand(self, token):
        return token
