from fontTools.misc.fixedTools import otRound

from ufo2ft.featureWriters import BaseFeatureWriter, ast
from ufo2ft.util import classifyGlyphs, unicodeScriptDirection


class CursFeatureWriter(BaseFeatureWriter):
    """Generate a curs feature base on glyph anchors.

    The default mode is 'skip': i.e. if the 'curs' feature is already present in
    the feature file, it is not generated again.

    The optional 'append' mode will add extra lookups to an already existing
    features, if any.

    By default, anchors names 'entry' and 'exit' will be used to connect the
    'entry' anchor of a glyph with the 'exit' anchor of the preceding glyph.
    """

    tableTag = "GPOS"
    features = frozenset(["curs"])

    def _makeCursiveFeature(self):
        cmap = self.makeUnicodeToGlyphNameMapping()
        if any(unicodeScriptDirection(uv) == "LTR" for uv in cmap):
            gsub = self.compileGSUB()
            dirGlyphs = classifyGlyphs(unicodeScriptDirection, cmap, gsub)
            shouldSplit = "LTR" in dirGlyphs
        else:
            shouldSplit = False

        lookups = []
        ordereredGlyphSet = self.getOrderedGlyphSet().items()
        if shouldSplit:
            # Make LTR lookup
            LTRlookup = self._makeCursiveLookup(
                (
                    glyph
                    for (glyphName, glyph) in ordereredGlyphSet
                    if glyphName in dirGlyphs["LTR"]
                ),
                direction="LTR",
            )
            if LTRlookup:
                lookups.append(LTRlookup)

            # Make RTL lookup with other glyphs
            RTLlookup = self._makeCursiveLookup(
                (
                    glyph
                    for (glyphName, glyph) in ordereredGlyphSet
                    if glyphName not in dirGlyphs["LTR"]
                ),
                direction="RTL",
            )
            if RTLlookup:
                lookups.append(RTLlookup)
        else:
            lookup = self._makeCursiveLookup(
                (glyph for (glyphName, glyph) in ordereredGlyphSet)
            )
            if lookup:
                lookups.append(lookup)

        if lookups:
            feature = ast.FeatureBlock("curs")
            feature.statements.extend(lookups)
            return feature

    def _makeCursiveLookup(self, glyphs, direction=None):
        statements = self._makeCursiveStatements(glyphs)

        if not statements:
            return

        suffix = ""
        if direction == "LTR":
            suffix = "_ltr"
        elif direction == "RTL":
            suffix = "_rtl"
        lookup = ast.LookupBlock(name=f"curs{suffix}")

        if direction != "LTR":
            lookup.statements.append(ast.makeLookupFlag(("IgnoreMarks", "RightToLeft")))
        else:
            lookup.statements.append(ast.makeLookupFlag("IgnoreMarks"))

        lookup.statements.extend(statements)

        return lookup

    def _makeCursiveStatements(self, glyphs):
        cursiveAnchors = dict()
        statements = []
        for glyph in glyphs:
            entryAnchor = exitAnchor = None
            for anchor in glyph.anchors:
                if entryAnchor and exitAnchor:
                    break
                if anchor.name == "entry":
                    entryAnchor = ast.Anchor(x=otRound(anchor.x), y=otRound(anchor.y))
                elif anchor.name == "exit":
                    exitAnchor = ast.Anchor(x=otRound(anchor.x), y=otRound(anchor.y))

            # A glyph can have only one of the cursive anchors (e.g. if it
            # attaches on one side only)
            if entryAnchor or exitAnchor:
                cursiveAnchors[ast.GlyphName(glyph.name)] = (entryAnchor, exitAnchor)

        if cursiveAnchors:
            for glyphName, anchors in cursiveAnchors.items():
                statement = ast.CursivePosStatement(glyphName, *anchors)
                statements.append(statement)

        return statements

    def _write(self):
        feaFile = self.context.feaFile
        feature = self._makeCursiveFeature()

        if not feature:
            return False

        self._insert(feaFile=feaFile, features=[feature])
        return True
