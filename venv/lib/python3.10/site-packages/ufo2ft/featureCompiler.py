import logging
import os
from collections import OrderedDict
from inspect import isclass
from io import StringIO
from tempfile import NamedTemporaryFile

from fontTools import mtiLib
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.feaLib.error import FeatureLibError, IncludedFeaNotFound
from fontTools.feaLib.parser import Parser

from ufo2ft.constants import MTI_FEATURES_PREFIX
from ufo2ft.featureWriters import (
    CursFeatureWriter,
    GdefFeatureWriter,
    KernFeatureWriter,
    MarkFeatureWriter,
    ast,
    isValidFeatureWriter,
    loadFeatureWriters,
)

logger = logging.getLogger(__name__)


def parseLayoutFeatures(font):
    """Parse OpenType layout features in the UFO and return a
    feaLib.ast.FeatureFile instance.
    """
    featxt = font.features.text or ""
    if not featxt:
        return ast.FeatureFile()
    buf = StringIO(featxt)
    ufoPath = font.path
    includeDir = None
    if ufoPath is not None:
        # The UFO v3 specification says "Any include() statements must be relative to
        # the UFO path, not to the features.fea file itself". We set the `name`
        # attribute on the buffer to the actual feature file path, which feaLib will
        # pick up and use to attribute errors to the correct file, and explicitly set
        # the include directory to the parent of the UFO.
        ufoPath = os.path.normpath(ufoPath)
        buf.name = os.path.join(ufoPath, "features.fea")
        includeDir = os.path.dirname(ufoPath)
    glyphNames = set(font.keys())
    try:
        parser = Parser(buf, glyphNames, includeDir=includeDir)
        doc = parser.parse()
    except IncludedFeaNotFound as e:
        if ufoPath and os.path.exists(os.path.join(ufoPath, e.args[0])):
            logger.warning(
                "Please change the file name in the include(...); "
                "statement to be relative to the UFO itself, "
                "instead of relative to the 'features.fea' file "
                "contained in it."
            )
        raise
    return doc


class BaseFeatureCompiler:
    """Base class for generating OpenType features and compiling OpenType
    layout tables from these.
    """

    def __init__(self, ufo, ttFont=None, glyphSet=None, **kwargs):
        """
        Args:
          ufo: an object representing a UFO (defcon.Font or equivalent)
            containing the features source data.
          ttFont: a fontTools TTFont object where the generated OpenType
            tables are added. If None, an empty TTFont is used, with
            the same glyph order as the ufo object.
          glyphSet: a (optional) dict containing pre-processed copies of
            the UFO glyphs.
        """
        self.ufo = ufo

        if ttFont is None:
            from fontTools.ttLib import TTFont

            from ufo2ft.util import makeOfficialGlyphOrder

            ttFont = TTFont()
            ttFont.setGlyphOrder(makeOfficialGlyphOrder(ufo))
        self.ttFont = ttFont

        glyphOrder = ttFont.getGlyphOrder()
        if glyphSet is not None:
            assert set(glyphOrder) == set(glyphSet.keys())
        else:
            glyphSet = ufo
        self.glyphSet = OrderedDict((gn, glyphSet[gn]) for gn in glyphOrder)

    def setupFeatures(self):
        """Make the features source.

        **This should not be called externally.** Subclasses
        must override this method.
        """
        raise NotImplementedError

    def buildTables(self):
        """Compile OpenType feature tables from the source.

        **This should not be called externally.** Subclasses
        must override this method.
        """
        raise NotImplementedError

    def setupFile_features(self):
        """DEPRECATED. Use 'setupFeatures' instead."""
        _deprecateMethod("setupFile_features", "setupFeatures")
        self.setupFeatures()

    def setupFile_featureTables(self):
        """DEPRECATED. Use 'setupFeatures' instead."""
        _deprecateMethod("setupFile_featureTables", "buildTables")
        self.buildTables()

    def compile(self):
        if "setupFile_features" in self.__class__.__dict__:
            _deprecateMethod("setupFile_features", "setupFeatures")
            self.setupFile_features()
        else:
            self.setupFeatures()

        if "setupFile_featureTables" in self.__class__.__dict__:
            _deprecateMethod("setupFile_featureTables", "buildTables")
            self.setupFile_featureTables()
        else:
            self.buildTables()

        return self.ttFont


def _deprecateMethod(arg, repl):
    import warnings

    warnings.warn(
        f"{arg!r} method is deprecated; use {repl!r} instead",
        category=UserWarning,
        stacklevel=3,
    )


class FeatureCompiler(BaseFeatureCompiler):
    """Generate automatic features and compile OpenType tables from Adobe
    Feature File stored in the UFO, using fontTools.feaLib as compiler.
    """

    defaultFeatureWriters = [
        KernFeatureWriter,
        MarkFeatureWriter,
        GdefFeatureWriter,
        CursFeatureWriter,
    ]

    def __init__(self, ufo, ttFont=None, glyphSet=None, featureWriters=None, **kwargs):
        """
        Args:
          featureWriters: a list of BaseFeatureWriter subclasses or
            pre-initialized instances. The default value (None) means that:
            - first, the UFO lib will be searched for a list of featureWriters
              under the key "com.github.googlei18n.ufo2ft.featureWriters"
              (see loadFeatureWriters).
            - if that is not found, the default list of writers will be used:
              (see FeatureCompiler.defaultFeatureWriters, and the individual
              feature writer classes for the list of features generated).
            If the featureWriters list is empty, no automatic feature is
            generated and only pre-existing features are compiled.
            The ``featureWriters`` parameter overrides both the writers from
            the UFO lib and the default writers list. To extend instead of
            replace the latter, the list can contain a special value ``...``
            (i.e. the ``ellipsis`` singleton, not the str literal '...')
            which gets replaced by either the UFO.lib writers or the default
            ones; thus one can insert additional writers either before or after
            these.
        """
        BaseFeatureCompiler.__init__(self, ufo, ttFont, glyphSet)

        self.initFeatureWriters(featureWriters)

        if kwargs.get("mtiFeatures") is not None:
            import warnings

            warnings.warn(
                "mtiFeatures argument is ignored; "
                "you should use MtiLibFeatureCompiler",
                category=UserWarning,
                stacklevel=2,
            )

    def _load_custom_feature_writers(self, featureWriters=None):
        # Args:
        #   ufo: Font
        #   featureWriters: Optional[List[Union[FeatureWriter, EllipsisType]]])
        # Returns: List[FeatureWriter]

        # by default, load the feature writers from the lib or the default ones;
        # ellipsis is used as a placeholder so one can optionally insert additional
        # featureWriters=[w1, ..., w2] either before or after these, or override
        # them by omitting the ellipsis.
        if featureWriters is None:
            featureWriters = [...]
        result = []
        seen_ellipsis = False
        for writer in featureWriters:
            if writer is ...:
                if seen_ellipsis:
                    raise ValueError("ellipsis not allowed more than once")
                writers = loadFeatureWriters(self.ufo)
                if writers is not None:
                    result.extend(writers)
                else:
                    result.extend(self.defaultFeatureWriters)
                seen_ellipsis = True
            else:
                klass = writer if isclass(writer) else type(writer)
                if not isValidFeatureWriter(klass):
                    raise TypeError(f"Invalid feature writer: {writer!r}")
                result.append(writer)
        return result

    def initFeatureWriters(self, featureWriters=None):
        """Initialize feature writer classes as specified in the UFO lib.
        If none are defined in the UFO, the default feature writers are used
        (see FeatureCompiler.defaultFeatureWriters).
        The 'featureWriters' argument can be used to override these.
        The method sets the `self.featureWriters` attribute with the list of
        writers.

        Note that the writers that generate GSUB features are placed first in
        this list, before all others. This is because the GSUB table may be
        used in the subsequent feature writers to resolve substitutions from
        glyphs with unicodes to their alternates.
        """
        featureWriters = self._load_custom_feature_writers(featureWriters)

        gsubWriters = []
        others = []
        for writer in featureWriters:
            if isclass(writer):
                writer = writer()
            if writer.tableTag == "GSUB":
                gsubWriters.append(writer)
            else:
                others.append(writer)

        self.featureWriters = gsubWriters + others

    def setupFeatures(self):
        """
        Make the features source.

        **This should not be called externally.** Subclasses
        may override this method to handle the file creation
        in a different way if desired.
        """
        if self.featureWriters:
            featureFile = parseLayoutFeatures(self.ufo)

            for writer in self.featureWriters:
                writer.write(self.ufo, featureFile, compiler=self)

            # stringify AST to get correct line numbers in error messages
            self.features = featureFile.asFea()
        else:
            # no featureWriters, simply read existing features' text
            self.features = self.ufo.features.text or ""

    def writeFeatures(self, outfile):
        if hasattr(self, "features"):
            outfile.write(self.features)

    def buildTables(self):
        """
        Compile OpenType feature tables from the source.
        Raises a FeaLibError if the feature compilation was unsuccessful.

        **This should not be called externally.** Subclasses
        may override this method to handle the table compilation
        in a different way if desired.
        """

        if not self.features:
            return

        # the path is used by the lexer to follow 'include' statements;
        # if we generated some automatic features, includes have already been
        # resolved, and we work from a string which does't exist on disk
        path = self.ufo.path if not self.featureWriters else None
        try:
            addOpenTypeFeaturesFromString(self.ttFont, self.features, filename=path)
        except FeatureLibError:
            if path is None:
                # if compilation fails, create temporary file for inspection
                data = self.features.encode("utf-8")
                with NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(data)
                logger.error("Compilation failed! Inspect temporary file: %r", tmp.name)
            raise


class MtiFeatureCompiler(BaseFeatureCompiler):
    """Compile OpenType layout tables from MTI feature files using
    fontTools.mtiLib.
    """

    def setupFeatures(self):
        ufo = self.ufo
        features = {}
        # includes the length of the "/" separator
        prefixLength = len(MTI_FEATURES_PREFIX) + 1
        for fn in ufo.data.fileNames:
            if fn.startswith(MTI_FEATURES_PREFIX) and fn.endswith(".mti"):
                content = ufo.data[fn].decode("utf-8")
                features[fn[prefixLength:-4]] = content
        self.mtiFeatures = features

    def buildTables(self):
        for tag, features in self.mtiFeatures.items():
            table = mtiLib.build(features.splitlines(), self.ttFont)
            assert table.tableTag == tag
            self.ttFont[tag] = table
