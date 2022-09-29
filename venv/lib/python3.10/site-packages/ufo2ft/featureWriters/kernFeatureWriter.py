from types import SimpleNamespace

from fontTools import unicodedata

from ufo2ft.constants import INDIC_SCRIPTS, USE_SCRIPTS
from ufo2ft.featureWriters import BaseFeatureWriter, ast
from ufo2ft.util import classifyGlyphs, quantize, unicodeScriptDirection

SIDE1_PREFIX = "public.kern1."
SIDE2_PREFIX = "public.kern2."

# In HarfBuzz the 'dist' feature is automatically enabled for these shapers:
#   src/hb-ot-shape-complex-myanmar.cc
#   src/hb-ot-shape-complex-use.cc
#   src/hb-ot-shape-complex-indic.cc
#   src/hb-ot-shape-complex-khmer.cc
# We derived the list of scripts associated to each dist-enabled shaper from
# `hb_ot_shape_complex_categorize` in src/hb-ot-shape-complex-private.hh
DIST_ENABLED_SCRIPTS = set(INDIC_SCRIPTS) | set(["Khmr", "Mymr"]) | set(USE_SCRIPTS)

RTL_BIDI_TYPES = {"R", "AL"}
LTR_BIDI_TYPES = {"L", "AN", "EN"}


def unicodeBidiType(uv):
    """Return "R" for characters with RTL direction, or "L" for LTR (whether
    'strong' or 'weak'), or None for neutral direction.
    """
    char = chr(uv)
    bidiType = unicodedata.bidirectional(char)
    if bidiType in RTL_BIDI_TYPES:
        return "R"
    elif bidiType in LTR_BIDI_TYPES:
        return "L"
    else:
        return None


class KerningPair:

    __slots__ = ("side1", "side2", "value", "directions", "bidiTypes")

    def __init__(self, side1, side2, value, directions=None, bidiTypes=None):
        if isinstance(side1, str):
            self.side1 = ast.GlyphName(side1)
        elif isinstance(side1, ast.GlyphClassDefinition):
            self.side1 = ast.GlyphClassName(side1)
        else:
            raise AssertionError(side1)

        if isinstance(side2, str):
            self.side2 = ast.GlyphName(side2)
        elif isinstance(side2, ast.GlyphClassDefinition):
            self.side2 = ast.GlyphClassName(side2)
        else:
            raise AssertionError(side2)

        self.value = value
        self.directions = directions or set()
        self.bidiTypes = bidiTypes or set()

    @property
    def firstIsClass(self):
        return isinstance(self.side1, ast.GlyphClassName)

    @property
    def secondIsClass(self):
        return isinstance(self.side2, ast.GlyphClassName)

    @property
    def glyphs(self):
        if self.firstIsClass:
            classDef1 = self.side1.glyphclass
            glyphs1 = {g.asFea() for g in classDef1.glyphSet()}
        else:
            glyphs1 = {self.side1.asFea()}
        if self.secondIsClass:
            classDef2 = self.side2.glyphclass
            glyphs2 = {g.asFea() for g in classDef2.glyphSet()}
        else:
            glyphs2 = {self.side2.asFea()}
        return glyphs1 | glyphs2

    def __repr__(self):
        return "<{} {} {} {}{}{}>".format(
            self.__class__.__name__,
            self.side1,
            self.side2,
            self.value,
            " %r" % self.directions if self.directions else "",
            " %r" % self.bidiTypes if self.bidiTypes else "",
        )


class KernFeatureWriter(BaseFeatureWriter):
    """Generates a kerning feature based on groups and rules contained
    in an UFO's kerning data.

    There are currently two possible writing modes:
    2) "skip" (default) will not write anything if the features are already present;
    1) "append" will add additional lookups to an existing feature, if present,
       or it will add a new one at the end of all features.

    If the `quantization` argument is given in the filter options, the resulting
    anchors are rounded to the nearest multiple of the quantization value.
    """

    tableTag = "GPOS"
    features = frozenset(["kern", "dist"])
    options = dict(ignoreMarks=True, quantization=1)

    def setContext(self, font, feaFile, compiler=None):
        ctx = super().setContext(font, feaFile, compiler=compiler)
        ctx.gdefClasses = self.getGDEFGlyphClasses()
        ctx.kerning = self.getKerningData(font, feaFile, self.getOrderedGlyphSet())

        feaScripts = ast.getScriptLanguageSystems(feaFile)
        ctx.scriptGroups = self._groupScriptsByTagAndDirection(feaScripts)

        return ctx

    def shouldContinue(self):
        if not self.context.kerning.pairs:
            self.log.debug("No kerning data; skipped")
            return False

        if "dist" in self.context.todo and "dist" not in self.context.scriptGroups:
            self.log.debug(
                "No dist-enabled scripts defined in languagesystem "
                "statements; dist feature will not be generated"
            )
            self.context.todo.remove("dist")

        return super().shouldContinue()

    def _write(self):
        lookups = self._makeKerningLookups()
        if not lookups:
            self.log.debug("kerning lookups empty; skipped")
            return False

        features = self._makeFeatureBlocks(lookups)
        if not features:
            self.log.debug("kerning features empty; skipped")
            return False

        # extend feature file with the new generated statements
        feaFile = self.context.feaFile

        # first add the glyph class definitions
        side1Classes = self.context.kerning.side1Classes
        side2Classes = self.context.kerning.side2Classes
        newClassDefs = []
        for classes in (side1Classes, side2Classes):
            newClassDefs.extend([c for _, c in sorted(classes.items())])

        lookupGroups = []
        for _, lookupGroup in sorted(lookups.items()):
            lookupGroups.extend(lookupGroup)

        self._insert(
            feaFile=feaFile,
            classDefs=newClassDefs,
            lookups=lookupGroups,
            features=[features[tag] for tag in ["kern", "dist"] if tag in features],
        )
        return True

    @classmethod
    def getKerningData(cls, font, feaFile=None, glyphSet=None):
        side1Classes, side2Classes = cls.getKerningClasses(font, feaFile, glyphSet)
        pairs = cls.getKerningPairs(font, side1Classes, side2Classes, glyphSet)
        return SimpleNamespace(
            side1Classes=side1Classes, side2Classes=side2Classes, pairs=pairs
        )

    @staticmethod
    def getKerningGroups(font, glyphSet=None):
        if glyphSet:
            allGlyphs = set(glyphSet.keys())
        else:
            allGlyphs = set(font.keys())
        side1Groups = {}
        side2Groups = {}
        for name, members in font.groups.items():
            # prune non-existent or skipped glyphs
            members = [g for g in members if g in allGlyphs]
            if not members:
                # skip empty groups
                continue
            # skip groups without UFO3 public.kern{1,2} prefix
            if name.startswith(SIDE1_PREFIX):
                side1Groups[name] = members
            elif name.startswith(SIDE2_PREFIX):
                side2Groups[name] = members
        return side1Groups, side2Groups

    @classmethod
    def getKerningClasses(cls, font, feaFile=None, glyphSet=None):
        side1Groups, side2Groups = cls.getKerningGroups(font, glyphSet)
        side1Classes = ast.makeGlyphClassDefinitions(
            side1Groups, feaFile, stripPrefix="public."
        )
        side2Classes = ast.makeGlyphClassDefinitions(
            side2Groups, feaFile, stripPrefix="public."
        )
        return side1Classes, side2Classes

    @staticmethod
    def getKerningPairs(font, side1Classes, side2Classes, glyphSet=None):
        if glyphSet:
            allGlyphs = set(glyphSet.keys())
        else:
            allGlyphs = set(font.keys())
        kerning = font.kerning

        pairsByFlags = {}
        for (side1, side2) in kerning:
            # filter out pairs that reference missing groups or glyphs
            if side1 not in side1Classes and side1 not in allGlyphs:
                continue
            if side2 not in side2Classes and side2 not in allGlyphs:
                continue
            flags = (side1 in side1Classes, side2 in side2Classes)
            pairsByFlags.setdefault(flags, set()).add((side1, side2))

        result = []
        for flags, pairs in sorted(pairsByFlags.items()):
            for side1, side2 in sorted(pairs):
                value = kerning[side1, side2]
                if all(flags) and value == 0:
                    # ignore zero-valued class kern pairs
                    continue
                firstIsClass, secondIsClass = flags
                if firstIsClass:
                    side1 = side1Classes[side1]
                if secondIsClass:
                    side2 = side2Classes[side2]
                result.append(KerningPair(side1, side2, value))
        return result

    def _intersectPairs(self, attribute, glyphSets):
        allKeys = set()
        for pair in self.context.kerning.pairs:
            for key, glyphs in glyphSets.items():
                if not pair.glyphs.isdisjoint(glyphs):
                    getattr(pair, attribute).add(key)
                    allKeys.add(key)
        return allKeys

    @staticmethod
    def _groupScriptsByTagAndDirection(feaScripts):
        # Read scripts/languages defined in feaFile's 'languagesystem'
        # statements and group them by the feature tag (kern or dist)
        # they are associated with, and the global script's horizontal
        # direction (DFLT is excluded)
        scriptGroups = {}
        for scriptCode, scriptLangSys in feaScripts.items():
            if scriptCode:
                direction = unicodedata.script_horizontal_direction(scriptCode)
            else:
                direction = "LTR"
            if scriptCode in DIST_ENABLED_SCRIPTS:
                tag = "dist"
            else:
                tag = "kern"
            scriptGroups.setdefault(tag, {}).setdefault(direction, []).extend(
                scriptLangSys
            )
        return scriptGroups

    @staticmethod
    def _makePairPosRule(pair, rtl=False, quantization=1):
        enumerated = pair.firstIsClass ^ pair.secondIsClass
        value = quantize(pair.value, quantization)
        if rtl and "L" in pair.bidiTypes:
            # numbers are always shaped LTR even in RTL scripts
            rtl = False
        valuerecord = ast.ValueRecord(
            xPlacement=value if rtl else None,
            yPlacement=0 if rtl else None,
            xAdvance=value,
            yAdvance=0 if rtl else None,
        )
        return ast.PairPosStatement(
            glyphs1=pair.side1,
            valuerecord1=valuerecord,
            glyphs2=pair.side2,
            valuerecord2=None,
            enumerated=enumerated,
        )

    def _makeKerningLookup(
        self, name, pairs, exclude=None, rtl=False, ignoreMarks=True
    ):
        assert pairs
        rules = []
        for pair in pairs:
            if exclude is not None and exclude(pair):
                self.log.debug("pair excluded from '%s' lookup: %r", name, pair)
                continue
            rules.append(
                self._makePairPosRule(
                    pair, rtl=rtl, quantization=self.options.quantization
                )
            )

        if rules:
            lookup = ast.LookupBlock(name)
            if ignoreMarks and self.options.ignoreMarks:
                lookup.statements.append(ast.makeLookupFlag("IgnoreMarks"))
            lookup.statements.extend(rules)
            return lookup

    def _makeKerningLookups(self):
        cmap = self.makeUnicodeToGlyphNameMapping()
        if any(unicodeScriptDirection(uv) == "RTL" for uv in cmap):
            # If there are any characters from globally RTL scripts in the
            # cmap, we compile a temporary GSUB table to resolve substitutions
            # and group glyphs by script horizontal direction and bidirectional
            # type. We then mark each kerning pair with these properties when
            # any of the glyphs involved in a pair intersects these groups.
            gsub = self.compileGSUB()
            dirGlyphs = classifyGlyphs(unicodeScriptDirection, cmap, gsub)
            directions = self._intersectPairs("directions", dirGlyphs)
            shouldSplit = "RTL" in directions
            if shouldSplit:
                bidiGlyphs = classifyGlyphs(unicodeBidiType, cmap, gsub)
                self._intersectPairs("bidiTypes", bidiGlyphs)
        else:
            shouldSplit = False

        marks = self.context.gdefClasses.mark
        lookups = {}
        if shouldSplit:
            # make one DFLT lookup with script-agnostic characters, and two
            # LTR/RTL lookups excluding pairs from the opposite group.
            # We drop kerning pairs with ambiguous direction: i.e. those containing
            # glyphs from scripts with different overall horizontal direction, or
            # glyphs with incompatible bidirectional type (e.g. arabic letters vs
            # arabic numerals).
            pairs = []
            for pair in self.context.kerning.pairs:
                if ("RTL" in pair.directions and "LTR" in pair.directions) or (
                    "R" in pair.bidiTypes and "L" in pair.bidiTypes
                ):
                    self.log.warning(
                        "skipped kern pair with ambiguous direction: %r", pair
                    )
                    continue
                pairs.append(pair)
            if not pairs:
                return lookups

            if self.options.ignoreMarks:
                # If there are pairs with a mix of mark/base then the IgnoreMarks
                # flag is unnecessary and should not be set
                basePairs, markPairs = self._splitBaseAndMarkPairs(pairs, marks)
                if basePairs:
                    self._makeSplitDirectionKernLookups(lookups, basePairs)
                if markPairs:
                    self._makeSplitDirectionKernLookups(
                        lookups, markPairs, ignoreMarks=False, suffix="_marks"
                    )
            else:
                self._makeSplitDirectionKernLookups(lookups, pairs)
        else:
            # only make a single (implicitly LTR) lookup including all base/base pairs
            # and a single lookup including all base/mark pairs (if any)
            pairs = self.context.kerning.pairs
            if self.options.ignoreMarks:
                basePairs, markPairs = self._splitBaseAndMarkPairs(pairs, marks)
                lookups["LTR"] = []
                if basePairs:
                    lookups["LTR"].append(
                        self._makeKerningLookup("kern_ltr", basePairs)
                    )
                if markPairs:
                    lookups["LTR"].append(
                        self._makeKerningLookup(
                            "kern_ltr_marks", markPairs, ignoreMarks=False
                        )
                    )
            else:
                lookups["LTR"] = [self._makeKerningLookup("kern_ltr", pairs)]
        return lookups

    def _splitBaseAndMarkPairs(self, pairs, marks):
        basePairs, markPairs = [], []
        if marks:
            for pair in pairs:
                if any(glyph in marks for glyph in pair.glyphs):
                    markPairs.append(pair)
                else:
                    basePairs.append(pair)
        else:
            basePairs[:] = pairs
        return basePairs, markPairs

    def _makeSplitDirectionKernLookups(
        self, lookups, pairs, ignoreMarks=True, suffix=""
    ):
        dfltKern = self._makeKerningLookup(
            "kern_dflt" + suffix,
            pairs,
            exclude=(lambda pair: {"LTR", "RTL"}.intersection(pair.directions)),
            rtl=False,
            ignoreMarks=ignoreMarks,
        )
        if dfltKern:
            lookups.setdefault("DFLT", []).append(dfltKern)

        ltrKern = self._makeKerningLookup(
            "kern_ltr" + suffix,
            pairs,
            exclude=(lambda pair: not pair.directions or "RTL" in pair.directions),
            rtl=False,
            ignoreMarks=ignoreMarks,
        )
        if ltrKern:
            lookups.setdefault("LTR", []).append(ltrKern)

        rtlKern = self._makeKerningLookup(
            "kern_rtl" + suffix,
            pairs,
            exclude=(lambda pair: not pair.directions or "LTR" in pair.directions),
            rtl=True,
            ignoreMarks=ignoreMarks,
        )
        if rtlKern:
            lookups.setdefault("RTL", []).append(rtlKern)

    def _makeFeatureBlocks(self, lookups):
        features = {}
        if "kern" in self.context.todo:
            kern = ast.FeatureBlock("kern")
            self._registerKernLookups(kern, lookups)
            if kern.statements:
                features["kern"] = kern
        if "dist" in self.context.todo:
            dist = ast.FeatureBlock("dist")
            self._registerDistLookups(dist, lookups)
            if dist.statements:
                features["dist"] = dist
        return features

    def _registerKernLookups(self, feature, lookups):
        if "DFLT" in lookups:
            ast.addLookupReferences(feature, lookups["DFLT"])

        scriptGroups = self.context.scriptGroups
        if "dist" in self.context.todo:
            distScripts = scriptGroups["dist"]
        else:
            distScripts = {}
        kernScripts = scriptGroups.get("kern", {})
        ltrScripts = kernScripts.get("LTR", [])
        rtlScripts = kernScripts.get("RTL", [])

        ltrLookups = lookups.get("LTR")
        rtlLookups = lookups.get("RTL")
        if ltrLookups and rtlLookups:
            if ltrScripts and rtlScripts:
                for script, langs in ltrScripts:
                    ast.addLookupReferences(feature, ltrLookups, script, langs)
                for script, langs in rtlScripts:
                    ast.addLookupReferences(feature, rtlLookups, script, langs)
            elif ltrScripts:
                ast.addLookupReferences(feature, rtlLookups, script="DFLT")
                for script, langs in ltrScripts:
                    ast.addLookupReferences(feature, ltrLookups, script, langs)
            elif rtlScripts:
                ast.addLookupReferences(feature, ltrLookups, script="DFLT")
                for script, langs in rtlScripts:
                    ast.addLookupReferences(feature, rtlLookups, script, langs)
            else:
                if not (distScripts.get("LTR") and distScripts.get("RTL")):
                    raise ValueError(
                        "cannot use DFLT script for both LTR and RTL kern "
                        "lookups; add 'languagesystems' to features for at "
                        "least one LTR or RTL script using the kern feature"
                    )
        elif ltrLookups:
            if not (rtlScripts or distScripts):
                ast.addLookupReferences(feature, ltrLookups)
            else:
                ast.addLookupReferences(feature, ltrLookups, script="DFLT")
                for script, langs in ltrScripts:
                    ast.addLookupReferences(feature, ltrLookups, script, langs)
        elif rtlLookups:
            if not (ltrScripts or distScripts):
                ast.addLookupReferences(feature, rtlLookups)
            else:
                ast.addLookupReferences(feature, rtlLookups, script="DFLT")
                for script, langs in rtlScripts:
                    ast.addLookupReferences(feature, rtlLookups, script, langs)

    def _registerDistLookups(self, feature, lookups):
        scripts = self.context.scriptGroups["dist"]
        ltrLookups = lookups.get("LTR")
        if ltrLookups:
            for script, langs in scripts.get("LTR", []):
                ast.addLookupReferences(feature, ltrLookups, script, langs)
        rtlLookups = lookups.get("RTL")
        if rtlLookups:
            for script, langs in scripts.get("RTL", []):
                ast.addLookupReferences(feature, rtlLookups, script, langs)
