import logging
import os
from enum import IntEnum

from fontTools import varLib
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.designspaceLib.split import splitInterpolable, splitVariableFonts
from fontTools.otlLib.optimize.gpos import GPOS_COMPACT_MODE_ENV_KEY

from ufo2ft.constants import SPARSE_OTF_MASTER_TABLES, SPARSE_TTF_MASTER_TABLES
from ufo2ft.errors import InvalidDesignSpaceData
from ufo2ft.featureCompiler import (
    MTI_FEATURES_PREFIX,
    FeatureCompiler,
    MtiFeatureCompiler,
)
from ufo2ft.outlineCompiler import OutlineOTFCompiler, OutlineTTFCompiler
from ufo2ft.postProcessor import PostProcessor
from ufo2ft.preProcessor import (
    OTFPreProcessor,
    TTFInterpolatablePreProcessor,
    TTFPreProcessor,
)
from ufo2ft.util import (
    _getDefaultNotdefGlyph,
    ensure_all_sources_have_names,
    init_kwargs,
    prune_unknown_kwargs,
)

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"


logger = logging.getLogger(__name__)


class CFFOptimization(IntEnum):
    NONE = 0
    SPECIALIZE = 1
    SUBROUTINIZE = 2


def call_preprocessor(ufo_or_ufos, *, preProcessorClass, **kwargs):
    logger.info("Pre-processing glyphs")
    if kwargs["skipExportGlyphs"] is None:
        if isinstance(ufo_or_ufos, (list, tuple)):
            kwargs["skipExportGlyphs"] = set()
            for ufo in ufo_or_ufos:
                kwargs["skipExportGlyphs"].update(
                    ufo.lib.get("public.skipExportGlyphs", [])
                )
        else:
            kwargs["skipExportGlyphs"] = ufo_or_ufos.lib.get(
                "public.skipExportGlyphs", []
            )

    # Preprocessors expect this parameter under a different name.
    if "cubicConversionError" in kwargs:
        kwargs["conversionError"] = kwargs.pop("cubicConversionError")

    callables = [preProcessorClass]
    if hasattr(preProcessorClass, "initDefaultFilters"):
        callables.append(preProcessorClass.initDefaultFilters)
    preProcessor = preProcessorClass(
        ufo_or_ufos, **prune_unknown_kwargs(kwargs, *callables)
    )
    return preProcessor.process()


def call_outline_compiler(ufo, glyphSet, *, outlineCompilerClass, **kwargs):
    kwargs = prune_unknown_kwargs(kwargs, outlineCompilerClass)
    outlineCompiler = outlineCompilerClass(ufo, glyphSet=glyphSet, **kwargs)
    return outlineCompiler.compile()


def call_postprocessor(otf, ufo, glyphSet, *, postProcessorClass, **kwargs):
    if postProcessorClass is not None:
        postProcessor = postProcessorClass(otf, ufo, glyphSet=glyphSet)
        kwargs = prune_unknown_kwargs(kwargs, postProcessor.process)
        otf = postProcessor.process(**kwargs)
    return otf


base_args = dict(
    postProcessorClass=PostProcessor,
    featureCompilerClass=None,
    featureWriters=None,
    filters=None,
    glyphOrder=None,
    useProductionNames=None,
    removeOverlaps=False,
    overlapsBackend=None,
    inplace=False,
    layerName=None,
    skipExportGlyphs=None,
    debugFeatureFile=None,
    notdefGlyph=None,
    colrLayerReuse=True,
)

compileOTF_args = {
    **base_args,
    **dict(
        preProcessorClass=OTFPreProcessor,
        outlineCompilerClass=OutlineOTFCompiler,
        optimizeCFF=CFFOptimization.SUBROUTINIZE,
        roundTolerance=None,
        cffVersion=1,
        subroutinizer=None,
        _tables=None,
    ),
}


def compileOTF(ufo, **kwargs):
    """Create FontTools CFF font from a UFO.

    *removeOverlaps* performs a union operation on all the glyphs' contours.

    *optimizeCFF* (int) defines whether the CFF charstrings should be
      specialized and subroutinized. By default both optimization are enabled.
      A value of 0 disables both; 1 only enables the specialization; 2 (default)
      does both specialization and subroutinization.

    *roundTolerance* (float) controls the rounding of point coordinates.
      It is defined as the maximum absolute difference between the original
      float and the rounded integer value.
      By default, all floats are rounded to integer (tolerance 0.5); a value
      of 0 completely disables rounding; values in between only round floats
      which are close to their integral part within the tolerated range.

    *featureWriters* argument is a list of BaseFeatureWriter subclasses or
      pre-initialized instances. Features will be written by each feature
      writer in the given order. If featureWriters is None, the default
      feature writers [KernFeatureWriter, MarkFeatureWriter] are used.

    *filters* argument is a list of BaseFilters subclasses or pre-initialized
      instances. Filters with 'pre' attribute set to True will be pre-filters
      called before the default filters, otherwise they will be post-filters,
      called after the default filters.
      Filters will modify glyphs or the glyph set. The default filters cannot
      be disabled.

    *useProductionNames* renames glyphs in TrueType 'post' or OpenType 'CFF '
      tables based on the 'public.postscriptNames' mapping in the UFO lib,
      if present. Otherwise, uniXXXX names are generated from the glyphs'
      unicode values. The default value (None) will first check if the UFO lib
      has the 'com.github.googlei18n.ufo2ft.useProductionNames' key. If this
      is missing or True (default), the glyphs are renamed. Set to False
      to keep the original names.

    **inplace** (bool) specifies whether the filters should modify the input
      UFO's glyphs, a copy should be made first.

    *layerName* specifies which layer should be compiled. When compiling something
    other than the default layer, feature compilation is skipped.

    *skipExportGlyphs* is a list or set of glyph names to not be exported to the
    final font. If these glyphs are used as components in any other glyph, those
    components get decomposed. If the parameter is not passed in, the UFO's
    "public.skipExportGlyphs" lib key will be consulted. If it doesn't exist,
    all glyphs are exported. UFO groups and kerning will be pruned of skipped
    glyphs.

    *cffVersion* (int) is the CFF format, choose between 1 (default) and 2.

    *subroutinizer* (Optional[str]) is the name of the library to use for
      compressing CFF charstrings, if subroutinization is enabled by optimizeCFF
      parameter. Choose between "cffsubr" or "compreffor".
      By default "cffsubr" is used for both CFF 1 and CFF 2.
      NOTE: cffsubr is required for subroutinizing CFF2 tables, as compreffor
      currently doesn't support it.
    """
    kwargs = init_kwargs(kwargs, compileOTF_args)
    glyphSet = call_preprocessor(ufo, **kwargs)

    logger.info("Building OpenType tables")
    optimizeCFF = CFFOptimization(kwargs.pop("optimizeCFF"))
    tables = kwargs.pop("_tables")
    otf = call_outline_compiler(
        ufo,
        glyphSet,
        **kwargs,
        optimizeCFF=optimizeCFF >= CFFOptimization.SPECIALIZE,
        tables=tables,
    )

    # Only the default layer is likely to have all glyphs used in feature code.
    if kwargs["layerName"] is None:
        compileFeatures(ufo, otf, glyphSet=glyphSet, **kwargs)

    return call_postprocessor(
        otf,
        ufo,
        glyphSet,
        **kwargs,
        optimizeCFF=optimizeCFF >= CFFOptimization.SUBROUTINIZE,
    )


compileTTF_args = {
    **base_args,
    **dict(
        preProcessorClass=TTFPreProcessor,
        outlineCompilerClass=OutlineTTFCompiler,
        convertCubics=True,
        cubicConversionError=None,
        reverseDirection=True,
        rememberCurveType=True,
        flattenComponents=False,
    ),
}


def compileTTF(ufo, **kwargs):
    """Create FontTools TrueType font from a UFO.

    *removeOverlaps* performs a union operation on all the glyphs' contours.

    *flattenComponents* un-nests glyphs so that they have at most one level of
    components.

    *convertCubics* and *cubicConversionError* specify how the conversion from cubic
    to quadratic curves should be handled.

    *layerName* specifies which layer should be compiled. When compiling something
    other than the default layer, feature compilation is skipped.

    *skipExportGlyphs* is a list or set of glyph names to not be exported to the
    final font. If these glyphs are used as components in any other glyph, those
    components get decomposed. If the parameter is not passed in, the UFO's
    "public.skipExportGlyphs" lib key will be consulted. If it doesn't exist,
    all glyphs are exported. UFO groups and kerning will be pruned of skipped
    glyphs.
    """
    kwargs = init_kwargs(kwargs, compileTTF_args)

    glyphSet = call_preprocessor(ufo, **kwargs)

    logger.info("Building OpenType tables")
    otf = call_outline_compiler(ufo, glyphSet, **kwargs)

    # Only the default layer is likely to have all glyphs used in feature code.
    if kwargs["layerName"] is None:
        compileFeatures(ufo, otf, glyphSet=glyphSet, **kwargs)

    return call_postprocessor(otf, ufo, glyphSet, **kwargs)


compileInterpolatableTTFs_args = {
    **base_args,
    **dict(
        preProcessorClass=TTFInterpolatablePreProcessor,
        outlineCompilerClass=OutlineTTFCompiler,
        cubicConversionError=None,
        reverseDirection=True,
        flattenComponents=False,
        layerNames=None,
        colrLayerReuse=False,
    ),
}


def compileInterpolatableTTFs(ufos, **kwargs):
    """Create FontTools TrueType fonts from a list of UFOs with interpolatable
    outlines. Cubic curves are converted compatibly to quadratic curves using
    the Cu2Qu conversion algorithm.

    Return an iterator object that yields a TTFont instance for each UFO.

    *layerNames* refers to the layer names to use glyphs from in the order of
    the UFOs in *ufos*. By default, this is a list of `[None]` times the number
    of UFOs, i.e. using the default layer from all the UFOs.

    When the layerName is not None for a given UFO, the corresponding TTFont object
    will contain only a minimum set of tables ("head", "hmtx", "glyf", "loca", "maxp",
    "post" and "vmtx"), and no OpenType layout tables.

    *skipExportGlyphs* is a list or set of glyph names to not be exported to the
    final font. If these glyphs are used as components in any other glyph, those
    components get decomposed. If the parameter is not passed in, the union of
    all UFO's "public.skipExportGlyphs" lib keys will be used. If they don't
    exist, all glyphs are exported. UFO groups and kerning will be pruned of
    skipped glyphs.
    """
    from ufo2ft.util import _LazyFontName

    kwargs = init_kwargs(kwargs, compileInterpolatableTTFs_args)

    if kwargs["layerNames"] is None:
        kwargs["layerNames"] = [None] * len(ufos)
    assert len(ufos) == len(kwargs["layerNames"])

    glyphSets = call_preprocessor(ufos, **kwargs)

    for ufo, glyphSet, layerName in zip(ufos, glyphSets, kwargs["layerNames"]):
        fontName = _LazyFontName(ufo)
        if layerName is not None:
            logger.info("Building OpenType tables for %s-%s", fontName, layerName)
        else:
            logger.info("Building OpenType tables for %s", fontName)

        ttf = call_outline_compiler(
            ufo,
            glyphSet,
            **kwargs,
            tables=SPARSE_TTF_MASTER_TABLES if layerName else None,
        )

        # Only the default layer is likely to have all glyphs used in feature
        # code.
        if layerName is None:
            if kwargs["debugFeatureFile"]:
                kwargs["debugFeatureFile"].write("\n### %s ###\n" % fontName)
            compileFeatures(ufo, ttf, glyphSet=glyphSet, **kwargs)

        ttf = call_postprocessor(ttf, ufo, glyphSet, **kwargs)

        if layerName is not None:
            # for sparse masters (i.e. containing only a subset of the glyphs), we
            # need to include the post table in order to store glyph names, so that
            # fontTools.varLib can interpolate glyphs with same name across masters.
            # However we want to prevent the underlinePosition/underlineThickness
            # fields in such sparse masters to be included when computing the deltas
            # for the MVAR table. Thus, we set them to this unlikely, limit value
            # (-36768) which is a signal varLib should ignore them when building MVAR.
            ttf["post"].underlinePosition = -0x8000
            ttf["post"].underlineThickness = -0x8000

        yield ttf


def compileInterpolatableTTFsFromDS(designSpaceDoc, **kwargs):
    """Create FontTools TrueType fonts from the DesignSpaceDocument UFO sources
    with interpolatable outlines. Cubic curves are converted compatibly to
    quadratic curves using the Cu2Qu conversion algorithm.

    If the Designspace contains a "public.skipExportGlyphs" lib key, these
    glyphs will not be exported to the final font. If these glyphs are used as
    components in any other glyph, those components get decomposed. If the lib
    key doesn't exist in the Designspace, all glyphs are exported (keys in
    individual UFOs are ignored). UFO groups and kerning will be pruned of
    skipped glyphs.

    The DesignSpaceDocument should contain SourceDescriptor objects with 'font'
    attribute set to an already loaded defcon.Font object (or compatible UFO
    Font class). If 'font' attribute is unset or None, an AttributeError exception
    is thrown.

    Return a copy of the DesignSpaceDocument object (or the same one if
    inplace=True) with the source's 'font' attribute set to the corresponding
    TTFont instance.

    For sources that have the 'layerName' attribute defined, the corresponding TTFont
    object will contain only a minimum set of tables ("head", "hmtx", "glyf", "loca",
    "maxp", "post" and "vmtx"), and no OpenType layout tables.
    """
    kwargs = init_kwargs(kwargs, compileInterpolatableTTFs_args)
    ufos, kwargs["layerNames"] = [], []
    for source in designSpaceDoc.sources:
        if source.font is None:
            raise AttributeError(
                "designspace source '%s' is missing required 'font' attribute"
                % getattr(source, "name", "<Unknown>")
            )
        ufos.append(source.font)
        # 'layerName' is None for the default layer
        kwargs["layerNames"].append(source.layerName)

    kwargs["skipExportGlyphs"] = designSpaceDoc.lib.get("public.skipExportGlyphs", [])

    if kwargs["notdefGlyph"] is None:
        kwargs["notdefGlyph"] = _getDefaultNotdefGlyph(designSpaceDoc)

    ttfs = compileInterpolatableTTFs(ufos, **kwargs)

    if kwargs["inplace"]:
        result = designSpaceDoc
    else:
        result = designSpaceDoc.deepcopyExceptFonts()
    for source, ttf in zip(result.sources, ttfs):
        source.font = ttf
    return result


compileInterpolatableOTFs_args = {
    **base_args,
    **dict(
        preProcessorClass=OTFPreProcessor,
        outlineCompilerClass=OutlineOTFCompiler,
        featureCompilerClass=None,
        roundTolerance=None,
        optimizeCFF=CFFOptimization.NONE,
        colrLayerReuse=False,
    ),
}


def compileInterpolatableOTFsFromDS(designSpaceDoc, **kwargs):
    """Create FontTools CFF fonts from the DesignSpaceDocument UFO sources
    with interpolatable outlines.

    Interpolatable means without subroutinization and specializer optimizations
    and no removal of overlaps.

    If the Designspace contains a "public.skipExportGlyphs" lib key, these
    glyphs will not be exported to the final font. If these glyphs are used as
    components in any other glyph, those components get decomposed. If the lib
    key doesn't exist in the Designspace, all glyphs are exported (keys in
    individual UFOs are ignored). UFO groups and kerning will be pruned of
    skipped glyphs.

    The DesignSpaceDocument should contain SourceDescriptor objects with 'font'
    attribute set to an already loaded defcon.Font object (or compatible UFO
    Font class). If 'font' attribute is unset or None, an AttributeError exception
    is thrown.

    Return a copy of the DesignSpaceDocument object (or the same one if
    inplace=True) with the source's 'font' attribute set to the corresponding
    TTFont instance.

    For sources that have the 'layerName' attribute defined, the corresponding TTFont
    object will contain only a minimum set of tables ("head", "hmtx", "CFF ", "maxp",
    "vmtx" and "VORG"), and no OpenType layout tables.
    """
    kwargs = init_kwargs(kwargs, compileInterpolatableOTFs_args)
    for source in designSpaceDoc.sources:
        if source.font is None:
            raise AttributeError(
                "designspace source '%s' is missing required 'font' attribute"
                % getattr(source, "name", "<Unknown>")
            )

    kwargs["skipExportGlyphs"] = designSpaceDoc.lib.get("public.skipExportGlyphs", [])

    if kwargs["notdefGlyph"] is None:
        kwargs["notdefGlyph"] = _getDefaultNotdefGlyph(designSpaceDoc)

    otfs = []
    for source in designSpaceDoc.sources:
        otfs.append(
            compileOTF(
                ufo=source.font,
                **{
                    **kwargs,
                    **dict(
                        layerName=source.layerName,
                        removeOverlaps=False,
                        overlapsBackend=None,
                        optimizeCFF=CFFOptimization.NONE,
                        _tables=SPARSE_OTF_MASTER_TABLES if source.layerName else None,
                    ),
                },
            )
        )

    if kwargs["inplace"]:
        result = designSpaceDoc
    else:
        result = designSpaceDoc.deepcopyExceptFonts()

    for source, otf in zip(result.sources, otfs):
        source.font = otf

    return result


def compileFeatures(
    ufo,
    ttFont=None,
    glyphSet=None,
    featureCompilerClass=None,
    debugFeatureFile=None,
    **kwargs,
):
    """Compile OpenType Layout features from `ufo` into FontTools OTL tables.
    If `ttFont` is None, a new TTFont object is created containing the new
    tables, else the provided `ttFont` is updated with the new tables.

    If no explicit `featureCompilerClass` is provided, the one used will
    depend on whether the ufo contains any MTI feature files in its 'data'
    directory (thus the `MTIFeatureCompiler` is used) or not (then the
    default FeatureCompiler for Adobe FDK features is used).

    If skipExportGlyphs is provided (see description in the ``compile*``
    functions), the feature compiler will prune groups (removing them if empty)
    and kerning of the UFO of these glyphs. The feature file is left untouched.

    `debugFeatureFile` can be a file or file-like object opened in text mode,
    in which to dump the text content of the feature file, useful for debugging
    auto-generated OpenType features like kern, mark, mkmk etc.
    """
    if featureCompilerClass is None:
        if any(
            fn.startswith(MTI_FEATURES_PREFIX) and fn.endswith(".mti")
            for fn in ufo.data.fileNames
        ):
            featureCompilerClass = MtiFeatureCompiler
        else:
            featureCompilerClass = FeatureCompiler

    kwargs = prune_unknown_kwargs(kwargs, featureCompilerClass)
    featureCompiler = featureCompilerClass(ufo, ttFont, glyphSet=glyphSet, **kwargs)
    otFont = featureCompiler.compile()

    if debugFeatureFile:
        if hasattr(featureCompiler, "writeFeatures"):
            featureCompiler.writeFeatures(debugFeatureFile)

    return otFont


compileVariableTTF_args = {
    **base_args,
    **dict(
        preProcessorClass=TTFInterpolatablePreProcessor,
        outlineCompilerClass=OutlineTTFCompiler,
        cubicConversionError=None,
        reverseDirection=True,
        flattenComponents=False,
        excludeVariationTables=(),
        optimizeGvar=True,
    ),
}


def compileVariableTTF(designSpaceDoc, **kwargs):
    """Create FontTools TrueType variable font from the DesignSpaceDocument UFO sources
    with interpolatable outlines, using fontTools.varLib.build.

    *optimizeGvar*, if set to False, will not perform IUP optimization on the
      generated 'gvar' table.

    *excludeVariationTables* is a list of sfnt table tags (str) that is passed on
      to fontTools.varLib.build, to skip building some variation tables.

    The rest of the arguments works the same as in the other compile functions.

    Returns a new variable TTFont object.
    """
    kwargs = init_kwargs(kwargs, compileVariableTTF_args)
    fonts = compileVariableTTFs(designSpaceDoc, **kwargs)
    if len(fonts) != 1:
        raise ValueError(
            "Tried to build a DesignSpace version 5 with multiple variable "
            "fonts using the old ufo2ft API `compileVariableTTF`. "
            "Use the new API instead `compileVariableTTFs`"
        )
    return next(iter(fonts.values()))


compileVariableTTFs_args = {
    **compileVariableTTF_args,
    **dict(variableFontNames=None),
}


def compileVariableTTFs(designSpaceDoc: DesignSpaceDocument, **kwargs):
    """Create FontTools TrueType variable fonts for each variable font defined
    in the given DesignSpaceDocument, using their UFO sources
    with interpolatable outlines, using fontTools.varLib.build.

    *optimizeGvar*, if set to False, will not perform IUP optimization on the
      generated 'gvar' table.

    *excludeVariationTables* is a list of sfnt table tags (str) that is passed on
      to fontTools.varLib.build, to skip building some variation tables.

    *variableFontNames* is an optional list of names of variable fonts
      to build. If not provided, all variable fonts listed in the given
      designspace will by built.

    The rest of the arguments works the same as in the other compile functions.

    Returns a dictionary that maps each variable font filename to a new variable
    TTFont object. If no variable fonts are defined in the Designspace, returns
    an empty dictionary.

    .. versionadded:: 2.28.0
    """
    kwargs = init_kwargs(kwargs, compileVariableTTFs_args)
    optimizeGvar = kwargs.pop("optimizeGvar")
    excludeVariationTables = kwargs.pop("excludeVariationTables")
    variableFontNames = kwargs.pop("variableFontNames")
    colrLayerReuse = kwargs.pop("colrLayerReuse")

    # Pop inplace because we'll make a copy at this level so deeper functions
    # don't need to worry
    inplace = kwargs.pop("inplace")
    if not inplace:
        designSpaceDoc = designSpaceDoc.deepcopyExceptFonts()

    vfNameToBaseUfo = _compileNeededSources(
        kwargs, designSpaceDoc, variableFontNames, compileInterpolatableTTFsFromDS
    )

    if not vfNameToBaseUfo:
        return {}

    logger.info("Building variable TTF fonts: %s", ", ".join(vfNameToBaseUfo))

    vfNameToTTFont = varLib.build_many(
        designSpaceDoc,
        exclude=excludeVariationTables,
        optimize=optimizeGvar,
        skip_vf=lambda vf_name: variableFontNames and vf_name not in variableFontNames,
        colr_layer_reuse=colrLayerReuse,
    )

    for vfName, varfont in list(vfNameToTTFont.items()):
        vfNameToTTFont[vfName] = call_postprocessor(
            varfont, vfNameToBaseUfo[vfName], glyphSet=None, **kwargs
        )

    return vfNameToTTFont


compileVariableCFF2_args = {
    **base_args,
    **dict(
        preProcessorClass=OTFPreProcessor,
        outlineCompilerClass=OutlineOTFCompiler,
        roundTolerance=None,
        excludeVariationTables=(),
        optimizeCFF=CFFOptimization.SPECIALIZE,
    ),
}


def compileVariableCFF2(designSpaceDoc, **kwargs):
    """Create FontTools CFF2 variable font from the DesignSpaceDocument UFO sources
    with interpolatable outlines, using fontTools.varLib.build.

    *excludeVariationTables* is a list of sfnt table tags (str) that is passed on
      to fontTools.varLib.build, to skip building some variation tables.

    *optimizeCFF* (int) defines whether the CFF charstrings should be
      specialized and subroutinized. 1 (default) only enables the specialization;
      2 (default) does both specialization and subroutinization. The value 0 is supposed
      to disable both optimizations, however it's currently unused, because fontTools
      has some issues generating a VF with non-specialized CFF2 charstrings:
      fonttools/fonttools#1979.
      NOTE: Subroutinization of variable CFF2 requires the "cffsubr" extra requirement.

    The rest of the arguments works the same as in the other compile functions.

    Returns a new variable TTFont object.
    """
    kwargs = init_kwargs(kwargs, compileVariableCFF2_args)
    fonts = compileVariableCFF2s(designSpaceDoc, **kwargs)
    if len(fonts) != 1:
        raise ValueError(
            "Tried to build a DesignSpace version 5 with multiple variable "
            "fonts using the old ufo2ft API `compileVariableCFF2`. "
            "Use the new API instead `compileVariableCFF2s`"
        )
    return next(iter(fonts.values()))


compileVariableCFF2s_args = {
    **compileVariableCFF2_args,
    **dict(variableFontNames=None),
}


def compileVariableCFF2s(designSpaceDoc, **kwargs):
    """Create FontTools CFF2 variable fonts for each variable font defined
    in the given DesignSpaceDocument, using their UFO sources
    with interpolatable outlines, using fontTools.varLib.build.

    *excludeVariationTables* is a list of sfnt table tags (str) that is passed on
      to fontTools.varLib.build, to skip building some variation tables.

    *optimizeCFF* (int) defines whether the CFF charstrings should be
      specialized and subroutinized. 1 (default) only enables the specialization;
      2 (default) does both specialization and subroutinization. The value 0 is supposed
      to disable both optimizations, however it's currently unused, because fontTools
      has some issues generating a VF with non-specialized CFF2 charstrings:
      fonttools/fonttools#1979.
      NOTE: Subroutinization of variable CFF2 requires the "cffsubr" extra requirement.

    *variableFontNames* is an optional list of filenames of variable fonts
      to build. If not provided, all variable fonts listed in the given
      designspace will by built.

    The rest of the arguments works the same as in the other compile functions.

    Returns a dictionary that maps each variable font filename to a new variable
    TTFont object.

    .. versionadded:: 2.28.0
    """
    kwargs = init_kwargs(kwargs, compileVariableCFF2s_args)
    excludeVariationTables = kwargs.pop("excludeVariationTables")
    optimizeCFF = CFFOptimization(kwargs.pop("optimizeCFF"))
    variableFontNames = kwargs.pop("variableFontNames")
    colrLayerReuse = kwargs.pop("colrLayerReuse")

    # Pop inplace because we'll make a copy at this level so deeper functions
    # don't need to worry
    inplace = kwargs.pop("inplace")
    if not inplace:
        designSpaceDoc = designSpaceDoc.deepcopyExceptFonts()

    vfNameToBaseUfo = _compileNeededSources(
        kwargs, designSpaceDoc, variableFontNames, compileInterpolatableOTFsFromDS
    )

    if not vfNameToBaseUfo:
        logger.warning("No variable fonts to build")
        return {}

    logger.info(f"Building variable CFF2 fonts: {', '.join(vfNameToBaseUfo)}")

    vfNameToTTFont = varLib.build_many(
        designSpaceDoc,
        exclude=excludeVariationTables,
        # NOTE optimize=False won't change anything until this PR is merged
        # https://github.com/fonttools/fonttools/pull/1979
        optimize=optimizeCFF >= CFFOptimization.SPECIALIZE,
        skip_vf=lambda vf_name: variableFontNames and vf_name not in variableFontNames,
        colr_layer_reuse=colrLayerReuse,
    )

    for vfName, varfont in list(vfNameToTTFont.items()):
        vfNameToTTFont[vfName] = call_postprocessor(
            varfont,
            vfNameToBaseUfo[vfName],
            glyphSet=None,
            **kwargs,
            optimizeCFF=optimizeCFF >= CFFOptimization.SUBROUTINIZE,
        )

    return vfNameToTTFont


def _compileNeededSources(
    kwargs, designSpaceDoc, variableFontNames, compileInterpolatableFunc
):
    # We'll need to map <source> elements to TTFonts, to do so make sure that
    # each <source> has a name.
    ensure_all_sources_have_names(designSpaceDoc)

    # Go through VFs to build and gather list of needed sources to compile
    interpolableSubDocs = [
        subDoc for _location, subDoc in splitInterpolable(designSpaceDoc)
    ]
    vfNameToBaseUfo = {}
    sourcesToCompile = set()
    for subDoc in interpolableSubDocs:
        for vfName, vfDoc in splitVariableFonts(subDoc):
            if variableFontNames is not None and vfName not in variableFontNames:
                # This VF is not needed so we don't need to compile its sources
                continue
            default_source = vfDoc.findDefault()
            if default_source is None:
                raise InvalidDesignSpaceData("No default source.")
            vfNameToBaseUfo[vfName] = default_source.font
            for source in vfDoc.sources:
                sourcesToCompile.add(source.name)

    # Match sources to compile to their Descriptor in the original designspace
    sourcesByName = {}
    for source in designSpaceDoc.sources:
        if source.name in sourcesToCompile:
            sourcesByName[source.name] = source

    # Compile all needed sources in each interpolable subspace to make sure
    # they're all compatible; that also ensures that sub-vfs within the same
    # interpolable sub-space are compatible too.
    for subDoc in interpolableSubDocs:
        # Only keep the sources that we've identified earlier as need-to-compile
        subDoc.sources = [s for s in subDoc.sources if s.name in sourcesToCompile]
        if not subDoc.sources:
            continue

        # FIXME: Hack until we get a fontTools config module. Disable GPOS
        # compaction while building masters because the compaction will be undone
        # anyway by varLib merge and then done again on the VF
        gpos_compact_value = os.environ.pop(GPOS_COMPACT_MODE_ENV_KEY, None)
        try:
            ttfDesignSpace = compileInterpolatableFunc(
                subDoc,
                **{
                    **kwargs,
                    **dict(
                        useProductionNames=False,  # will rename glyphs after varfont is built
                        # No need to post-process intermediate fonts.
                        postProcessorClass=None,
                    ),
                },
            )
        finally:
            if gpos_compact_value is not None:
                os.environ[GPOS_COMPACT_MODE_ENV_KEY] = gpos_compact_value

        # Stick TTFs back into original big DS
        for ttfSource in ttfDesignSpace.sources:
            sourcesByName[ttfSource.name].font = ttfSource.font

    return vfNameToBaseUfo
