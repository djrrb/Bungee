import logging
from collections import OrderedDict, namedtuple
from types import SimpleNamespace

from ufo2ft.constants import OPENTYPE_CATEGORIES_KEY
from ufo2ft.errors import InvalidFeaturesData
from ufo2ft.featureWriters import ast

INSERT_FEATURE_MARKER = r"\s*# Automatic Code.*"


class BaseFeatureWriter:
    """Abstract features writer.

    The `tableTag` class attribute (str) states the tag of the OpenType
    Layout table which the generated features are intended for.
    For example: "GPOS", "GSUB", "BASE", etc.

    The `features` class attribute defines the set of all the features
    that this writer supports. If you want to only write some of the
    available features you can provide a smaller sequence to 'features'
    constructor argument. By the default all the features supported by
    this writer will be outputted.

    Two writing modes are defined here:
    1) "skip" (default) will not write features if already present;
    2) "append" will add additional lookups to an existing feature,
       if present, or it will add a new one at the end of all features.
    Subclasses can set a different default mode or define a different
    set of `_SUPPORTED_MODES`.

    The `options` class attribute contains a mapping of option
    names with their default values. These can be overridden on an
    instance by passing keyword arguments to the constructor.
    """

    tableTag = None
    features = frozenset()
    mode = "skip"
    insertFeatureMarker = INSERT_FEATURE_MARKER
    options = {}

    _SUPPORTED_MODES = frozenset(["skip", "append"])

    def __init__(self, features=None, mode=None, **kwargs):
        if features is not None:
            features = frozenset(features)
            assert features, "features cannot be empty"
            unsupported = features.difference(self.__class__.features)
            if unsupported:
                raise ValueError("unsupported: %s" % ", ".join(unsupported))
            self.features = features

        if mode is not None:
            self.mode = mode
        if self.mode not in self._SUPPORTED_MODES:
            raise ValueError(self.mode)

        options = dict(self.__class__.options)
        for k in kwargs:
            if k not in options:
                raise TypeError("unsupported keyword argument: %r" % k)
            options[k] = kwargs[k]
        self.options = SimpleNamespace(**options)

        logger = ".".join([self.__class__.__module__, self.__class__.__name__])
        self.log = logging.getLogger(logger)

    def setContext(self, font, feaFile, compiler=None):
        """Populate a temporary `self.context` namespace, which is reset
        after each new call to `_write` method.
        Subclasses can override this to provide contextual information
        which depends on other data, or set any temporary attributes.

        The default implementation sets:
        - the current font;
        - the current FeatureFile object;
        - the current compiler instance (only present when this writer was
          instantiated from a FeatureCompiler);
        - a set of features (tags) to be generated. If self.mode is "skip",
          these are all the features which are _not_ already present.

        Returns the context namespace instance.
        """
        todo = set(self.features)
        insertComments = None
        if self.mode == "skip":
            if self.insertFeatureMarker is not None:
                insertComments = self.collectInsertMarkers(
                    feaFile, self.insertFeatureMarker, todo
                )
            # find existing feature blocks
            existing = ast.findFeatureTags(feaFile)
            # ignore features with insert marker
            if insertComments:
                existing.difference_update(insertComments.keys())
            # remove existing feature without insert marker from todo list
            todo.difference_update(existing)

        self.context = SimpleNamespace(
            font=font,
            feaFile=feaFile,
            compiler=compiler,
            todo=todo,
            insertComments=insertComments,
        )

        return self.context

    def shouldContinue(self):
        """Decide whether to start generating features or return early.
        Returns a boolean: True to proceed, False to skip.

        Sublcasses may override this to skip generation based on the presence
        or lack of other required pieces of font data.
        """
        if not self.context.todo:
            self.log.debug("No features to be generated; skipped")
            return False
        return True

    def write(self, font, feaFile, compiler=None):
        """Write features and class definitions for this font to a feaLib
        FeatureFile object.
        Returns True if feature file was modified, False if no new features
        were generated.
        """
        self.setContext(font, feaFile, compiler=compiler)
        try:
            if self.shouldContinue():
                return self._write()
            else:
                return False
        finally:
            del self.context

    def _write(self):
        """Subclasses must override this."""
        raise NotImplementedError

    def _insert(
        self,
        feaFile,
        classDefs=None,
        anchorDefs=None,
        markClassDefs=None,
        lookups=None,
        features=None,
    ):
        """
        Insert feature, its classDefs or markClassDefs and lookups at insert
        marker comment.

        If the insert marker is at the top of a feature block, the feature is
        inserted before that block, and after if the insert marker is at the
        bottom.
        """

        statements = feaFile.statements
        inserted = {}

        # First handle those with a known location, i.e. insert markers
        insertComments = self.context.insertComments
        indices = []
        for ix, feature in enumerate(features):
            if insertComments and feature.name in insertComments:
                block, comment = insertComments[feature.name]
                markerIndex = block.statements.index(comment)

                onlyCommentsBefore = all(
                    isinstance(s, ast.Comment) for s in block.statements[:markerIndex]
                )
                onlyCommentsAfter = all(
                    isinstance(s, ast.Comment) for s in block.statements[markerIndex:]
                )

                # Remove insert marker(s) from feature block.
                del block.statements[markerIndex]

                # insertFeatureMarker is in a block with only comments.
                # Replace that block with new feature block.
                if onlyCommentsBefore and onlyCommentsAfter:
                    index = statements.index(block)
                    statements.remove(block)

                # insertFeatureMarker is at the top of a feature block
                # or only preceded by other comments.
                elif onlyCommentsBefore:
                    index = statements.index(block)

                # insertFeatureMarker is at the bottom of a feature block
                # or only followed by other comments
                elif onlyCommentsAfter:
                    index = statements.index(block) + 1

                # insertFeatureMarker is in the middle of a feature block
                # preceded and followed by statements that are not comments
                #
                # Glyphs3 can insert a feature block when rules are before
                # and after the insert marker.
                # See
                # https://github.com/googlefonts/ufo2ft/issues/351#issuecomment-765294436
                # This is currently not supported.
                else:
                    raise InvalidFeaturesData(
                        "Insert marker has rules before and after, feature "
                        f"{block.name} cannot be inserted. This is not supported."
                    )

                statements.insert(index, feature)
                indices.append(index)
                inserted[id(feature)] = True

                # Now walk feature list backwards and insert any dependent features
                for i in range(ix - 1, -1, -1):
                    if id(features[i]) in inserted:
                        break
                    # Insert this before the current one i.e. at same array index
                    statements.insert(index, features[i])
                    # All the indices recorded previously have now shifted up by one
                    indices = [index] + [j + 1 for j in indices]
                    inserted[id(features[i])] = True

        # Finally, deal with any remaining features
        for feature in features:
            if id(feature) in inserted:
                continue
            index = len(statements)
            statements.insert(index, feature)
            indices.append(index)

        # Write classDefs, anchorsDefs, markClassDefs, lookups at earliest
        # opportunity.
        others = []
        minindex = min(indices)
        for defs in [classDefs, anchorDefs, markClassDefs]:
            if defs:
                others.extend(defs)
                others.append(ast.Comment(""))
        # Insert lookups
        if lookups:
            if minindex > 0 and not others:
                others.append(ast.Comment(""))
            others.extend(lookups)
        if others:
            feaFile.statements = statements = (
                statements[:minindex] + others + statements[minindex:]
            )

    @staticmethod
    def collectInsertMarkers(feaFile, insertFeatureMarker, featureTags):
        """
        Returns a dictionary of tuples (block, comment) keyed by feature tag
        with the block that contains the comment matching the insert feature
        marker, for given feature tags.
        """
        insertComments = dict()
        for match in ast.findCommentPattern(feaFile, insertFeatureMarker):
            blocks, comment = match[:-1], match[-1]
            if len(blocks) == 1 and isinstance(blocks[0], ast.FeatureBlock):
                block = blocks[0]
                if block.name in featureTags and block.name not in insertComments:
                    insertComments[block.name] = (block, comment)
        return insertComments

    def makeUnicodeToGlyphNameMapping(self):
        """Return the Unicode to glyph name mapping for the current font."""
        # Try to get the "best" Unicode cmap subtable if this writer is running
        # in the context of a FeatureCompiler, else create a new mapping from
        # the UFO glyphs
        compiler = self.context.compiler
        cmap = None
        if compiler is not None:
            table = compiler.ttFont.get("cmap")
            if table is not None:
                cmap = table.getBestCmap()
        if cmap is None:
            from ufo2ft.util import makeUnicodeToGlyphNameMapping

            if compiler is not None:
                glyphSet = compiler.glyphSet
            else:
                glyphSet = self.context.font
            cmap = makeUnicodeToGlyphNameMapping(glyphSet)
        return cmap

    def getOrderedGlyphSet(self):
        """Return OrderedDict[glyphName, glyph] sorted by glyphOrder."""
        compiler = self.context.compiler
        if compiler is not None:
            return compiler.glyphSet

        from ufo2ft.util import _GlyphSet, makeOfficialGlyphOrder

        font = self.context.font
        # subset glyphSet by skipExportGlyphs if any
        glyphSet = _GlyphSet.from_layer(
            font,
            skipExportGlyphs=set(font.lib.get("public.skipExportGlyphs", [])),
        )
        glyphOrder = makeOfficialGlyphOrder(glyphSet, font.glyphOrder)
        return OrderedDict((gn, glyphSet[gn]) for gn in glyphOrder)

    def compileGSUB(self):
        """Compile a temporary GSUB table from the current feature file."""
        from ufo2ft.util import compileGSUB

        compiler = self.context.compiler
        if compiler is not None:
            # The result is cached in the compiler instance, so if another
            # writer requests one it is not compiled again.
            if hasattr(compiler, "_gsub"):
                return compiler._gsub

            glyphOrder = compiler.ttFont.getGlyphOrder()
        else:
            # the 'real' glyph order doesn't matter because the table is not
            # compiled to binary, only the glyph names are used
            glyphOrder = sorted(self.context.font.keys())

        gsub = compileGSUB(self.context.feaFile, glyphOrder)

        if compiler and not hasattr(compiler, "_gsub"):
            compiler._gsub = gsub
        return gsub

    def getOpenTypeCategories(self):
        """Return 'public.openTypeCategories' values as a tuple of sets of
        unassigned, bases, ligatures, marks, components."""
        font = self.context.font
        unassigned, bases, ligatures, marks, components = (
            set(),
            set(),
            set(),
            set(),
            set(),
        )
        openTypeCategories = font.lib.get(OPENTYPE_CATEGORIES_KEY, {})

        for glyphName, category in openTypeCategories.items():
            if category == "unassigned":
                unassigned.add(glyphName)
            elif category == "base":
                bases.add(glyphName)
            elif category == "ligature":
                ligatures.add(glyphName)
            elif category == "mark":
                marks.add(glyphName)
            elif category == "component":
                components.add(glyphName)
            else:
                self.log.warning(
                    f"The '{OPENTYPE_CATEGORIES_KEY}' value of {glyphName} in "
                    f"{font.info.familyName} {font.info.styleName} is '{category}' "
                    "when it should be 'unassigned', 'base', 'ligature', 'mark' "
                    "or 'component'."
                )
        return namedtuple(
            "OpenTypeCategories", "unassigned base ligature mark component"
        )(
            frozenset(unassigned),
            frozenset(bases),
            frozenset(ligatures),
            frozenset(marks),
            frozenset(components),
        )

    def getGDEFGlyphClasses(self):
        """Return a tuple of GDEF GlyphClassDef base, ligature, mark, component
        glyph names.
        Sets are `None` if no 'public.openTypeCategories' values are defined or
        if no GDEF table is defined in the feature file.
        """
        feaFile = self.context.feaFile

        if ast.findTable(feaFile, "GDEF") is not None:
            return ast.getGDEFGlyphClasses(feaFile)

        unassigned, bases, ligatures, marks, components = self.getOpenTypeCategories()

        if not any((unassigned, bases, ligatures, marks, components)):
            return ast._GDEFGlyphClasses(None, None, None, None)
        return ast._GDEFGlyphClasses(
            frozenset(bases),
            frozenset(ligatures),
            frozenset(marks),
            frozenset(components),
        )
