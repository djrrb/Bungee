import itertools

from ufo2ft.constants import (
    COLOR_LAYER_MAPPING_KEY,
    COLOR_LAYERS_KEY,
    COLOR_PALETTES_KEY,
)
from ufo2ft.filters import isValidFilter, loadFilters
from ufo2ft.filters.decomposeComponents import DecomposeComponentsFilter
from ufo2ft.filters.decomposeTransformedComponents import (
    DecomposeTransformedComponentsFilter,
)
from ufo2ft.fontInfoData import getAttrWithFallback
from ufo2ft.util import _GlyphSet


def _load_custom_filters(ufo, filters=None):
    # Args:
    #   ufo: Font
    #   filters: Optional[List[Union[Filter, EllipsisType]]])
    # Returns: List[Filter]

    # by default, load the filters from the lib; ellipsis is used as a placeholder
    # so one can optionally insert additional filters=[f1, ..., f2] either
    # before or after these, or override them by omitting the ellipsis.
    if filters is None:
        filters = [...]
    seen_ellipsis = False
    result = []
    for f in filters:
        if f is ...:
            if seen_ellipsis:
                raise ValueError("ellipsis not allowed more than once")
            result.extend(itertools.chain(*loadFilters(ufo)))
            seen_ellipsis = True
        else:
            if not isValidFilter(type(f)):
                raise TypeError(f"Invalid filter: {f!r}")
            result.append(f)
    return result


class BasePreProcessor:
    """Base class for objects that performs pre-processing operations on
    the UFO glyphs, such as decomposing composites, removing overlaps, or
    applying custom filters.

    By default the input UFO is **not** modified. The ``process`` method
    returns a dictionary containing the new modified glyphset, keyed by
    glyph name. If ``inplace`` is True, the input UFO is modified directly
    without the need to first copy the glyphs.

    Subclasses can override the ``initDefaultFilters`` method and return
    a list of built-in filters which are performed in a predefined order,
    between the user-defined pre- and post-filters.
    The extra kwargs passed to the constructor can be used to customize the
    initialization of the default filters.

    Custom filters can be applied before or after the default filters.
    These can be specified in the UFO lib.plist under the private key
    "com.github.googlei18n.ufo2ft.filters".
    Alternatively the optional ``filters`` parameter can be used. This is a
    list of filter instances (subclasses of BaseFilter) that overrides
    those defined in the UFO lib. The list can be empty, meaning no custom
    filters are run. If ``filters`` contain the special value ``...`` (i.e.
    the actual ``ellipsis`` singleton, not the str literal '...'), then all
    the filters from the UFO lib are loaded in its place. This allows to
    insert additional filters before or after those already defined in the
    UFO lib, as opposed to discard/replace them which is the default behavior
    when ``...`` is absent.
    """

    def __init__(
        self,
        ufo,
        inplace=False,
        layerName=None,
        skipExportGlyphs=None,
        filters=None,
        **kwargs,
    ):
        self.ufo = ufo
        self.inplace = inplace
        self.layerName = layerName
        self.glyphSet = _GlyphSet.from_layer(
            ufo, layerName, copy=not inplace, skipExportGlyphs=skipExportGlyphs
        )
        self.defaultFilters = self.initDefaultFilters(**kwargs)

        filters = _load_custom_filters(ufo, filters)
        self.preFilters = [f for f in filters if f.pre]
        self.postFilters = [f for f in filters if not f.pre]

    def initDefaultFilters(self, **kwargs):
        return []  # pragma: no cover

    def process(self):
        ufo = self.ufo
        glyphSet = self.glyphSet
        for func in self.preFilters + self.defaultFilters + self.postFilters:
            func(ufo, glyphSet)
        return glyphSet


def _init_explode_color_layer_glyphs_filter(ufo, filters):
    # Initialize ExplodeColorLayerGlyphsFilter, which copies color glyph layers
    # as standalone glyphs to the default glyph set (for building COLR table), if the
    # UFO contains the required 'colorPalettes' key, as well as 'colorLayerMapping' lib
    # keys (in either the font's or glyph's lib).
    # Skip doing that if an explicit 'colorLayers' key is already present.
    if (
        COLOR_PALETTES_KEY in ufo.lib
        and COLOR_LAYERS_KEY not in ufo.lib
        and (
            COLOR_LAYER_MAPPING_KEY in ufo.lib
            or any(COLOR_LAYER_MAPPING_KEY in g.lib for g in ufo)
        )
    ):
        from ufo2ft.filters.explodeColorLayerGlyphs import ExplodeColorLayerGlyphsFilter

        filters.append(ExplodeColorLayerGlyphsFilter())


class OTFPreProcessor(BasePreProcessor):
    """Preprocessor for building CFF-flavored OpenType fonts.

    By default, it decomposes all the components.

    If ``removeOverlaps`` is True, it performs a union boolean operation on
    all the glyphs' contours.

    By default, booleanOperations is used to remove overlaps. You can choose
    skia-pathops by setting ``overlapsBackend`` to the enum value
    ``RemoveOverlapsFilter.SKIA_PATHOPS``, or the string "pathops".
    """

    def initDefaultFilters(self, removeOverlaps=False, overlapsBackend=None):
        filters = []

        _init_explode_color_layer_glyphs_filter(self.ufo, filters)

        filters.append(DecomposeComponentsFilter())

        if removeOverlaps:
            from ufo2ft.filters.removeOverlaps import RemoveOverlapsFilter

            if overlapsBackend is not None:
                filters.append(RemoveOverlapsFilter(backend=overlapsBackend))
            else:
                filters.append(RemoveOverlapsFilter())

        return filters


class TTFPreProcessor(OTFPreProcessor):
    """Preprocessor for building TrueType-flavored OpenType fonts.

    By default, it decomposes all the glyphs with mixed component/contour
    outlines. If the ``flattenComponents`` setting is True, glyphs with
    nested components are flattened so that they have at most one level of
    components.

    If ``removeOverlaps`` is True, it performs a union boolean operation on
    all the glyphs' contours.

    By default, booleanOperations is used to remove overlaps. You can choose
    skia-pathops by setting ``overlapsBackend`` to the enum value
    ``RemoveOverlapsFilter.SKIA_PATHOPS``, or the string "pathops".

    By default, it also converts all the PostScript cubic Bezier curves to
    TrueType quadratic splines. If the outlines are already quadratic, you
    can skip this by setting ``convertCubics`` to False.

    The optional ``conversionError`` argument controls the tolerance
    of the approximation algorithm. It is measured as the maximum distance
    between the original and converted curve, and it's relative to the UPM
    of the font (default: 1/1000 or 0.001).

    When converting curves to quadratic, it is assumed that the contours'
    winding direction is set following the PostScript counter-clockwise
    convention. Thus, by default the direction is reversed, in order to
    conform to opposite clockwise convention for TrueType outlines.
    You can disable this by setting ``reverseDirection`` to False.

    If both ``inplace`` and ``rememberCurveType`` options are True, the curve
    type "quadratic" is saved in font' lib under a private cu2qu key; the
    preprocessor will not try to convert them again if the curve type is
    already set to "quadratic".
    """

    def initDefaultFilters(
        self,
        removeOverlaps=False,
        overlapsBackend=None,
        flattenComponents=False,
        convertCubics=True,
        conversionError=None,
        reverseDirection=True,
        rememberCurveType=True,
    ):
        filters = []

        _init_explode_color_layer_glyphs_filter(self.ufo, filters)

        # len(g) is the number of contours, so we include the all glyphs
        # that have both components and at least one contour
        filters.append(DecomposeComponentsFilter(include=lambda g: len(g)))

        if flattenComponents:
            from ufo2ft.filters.flattenComponents import FlattenComponentsFilter

            filters.append(FlattenComponentsFilter())

        if removeOverlaps:
            from ufo2ft.filters.removeOverlaps import RemoveOverlapsFilter

            if overlapsBackend is not None:
                filters.append(RemoveOverlapsFilter(backend=overlapsBackend))
            else:
                filters.append(RemoveOverlapsFilter())

        if convertCubics:
            from ufo2ft.filters.cubicToQuadratic import CubicToQuadraticFilter

            filters.append(
                CubicToQuadraticFilter(
                    conversionError=conversionError,
                    reverseDirection=reverseDirection,
                    rememberCurveType=rememberCurveType and self.inplace,
                )
            )
        return filters


class TTFInterpolatablePreProcessor:
    """Preprocessor for building TrueType-flavored OpenType fonts with
    interpolatable quadratic outlines.

    The constructor takes a list of UFO fonts, and the ``process`` method
    returns the modified glyphsets (list of dicts) in the same order.

    The pre-processor performs the conversion from cubic to quadratic on
    all the UFOs at once, then decomposes mixed contour/component glyphs.

    Additional pre/post custom filter are also applied to each single UFOs,
    respectively before or after the default filters, if they are specified
    in the UFO's lib.plist under the private key
    "com.github.googlei18n.ufo2ft.filters".
    NOTE: If you use any custom filters, the resulting glyphsets may no longer
    be interpolation compatible, depending on the particular filter used or
    whether they are applied to only some vs all of the UFOs.

    The ``conversionError``, ``reverseDirection``, ``flattenComponents`` and
    ``rememberCurveType`` arguments work in the same way as in the
    ``TTFPreProcessor``.
    """

    def __init__(
        self,
        ufos,
        inplace=False,
        flattenComponents=False,
        conversionError=None,
        reverseDirection=True,
        rememberCurveType=True,
        layerNames=None,
        skipExportGlyphs=None,
        filters=None,
    ):
        from cu2qu.ufo import DEFAULT_MAX_ERR

        self.ufos = ufos
        self.inplace = inplace
        self.flattenComponents = flattenComponents

        if layerNames is None:
            layerNames = [None] * len(ufos)
        assert len(ufos) == len(layerNames)
        self.layerNames = layerNames

        # For each UFO, make a mapping of name to glyph object (and ensure it
        # contains none of the glyphs to be skipped, or any references to it).
        self.glyphSets = [
            _GlyphSet.from_layer(
                ufo, layerName, copy=not inplace, skipExportGlyphs=skipExportGlyphs
            )
            for ufo, layerName in zip(ufos, layerNames)
        ]
        self._conversionErrors = [
            (conversionError or DEFAULT_MAX_ERR)
            * getAttrWithFallback(ufo.info, "unitsPerEm")
            for ufo in ufos
        ]
        self._reverseDirection = reverseDirection
        self._rememberCurveType = rememberCurveType

        self.defaultFilters = []
        for ufo in ufos:
            self.defaultFilters.append([])
            _init_explode_color_layer_glyphs_filter(ufo, self.defaultFilters[-1])

        filterses = [_load_custom_filters(ufo, filters) for ufo in ufos]
        self.preFilters = [[f for f in filters if f.pre] for filters in filterses]
        self.postFilters = [[f for f in filters if not f.pre] for filters in filterses]

    def process(self):
        from cu2qu.ufo import fonts_to_quadratic

        needs_decomposition = set()

        # first apply all custom pre-filters
        for funcs, ufo, glyphSet in zip(self.preFilters, self.ufos, self.glyphSets):
            for func in funcs:
                if isinstance(func, DecomposeTransformedComponentsFilter):
                    needs_decomposition |= func(ufo, glyphSet)
                else:
                    func(ufo, glyphSet)

        # If we decomposed a glyph in some masters, we must ensure it is decomposed in
        # all masters. (https://github.com/googlefonts/ufo2ft/issues/507)
        if needs_decomposition:
            decompose = DecomposeComponentsFilter(include=needs_decomposition)
            for ufo, glyphSet in zip(self.ufos, self.glyphSets):
                decompose(ufo, glyphSet)

        # then apply all default filters
        for funcs, ufo, glyphSet in zip(self.defaultFilters, self.ufos, self.glyphSets):
            for func in funcs:
                func(ufo, glyphSet)

        fonts_to_quadratic(
            self.glyphSets,
            max_err=self._conversionErrors,
            reverse_direction=self._reverseDirection,
            dump_stats=True,
            remember_curve_type=self._rememberCurveType and self.inplace,
        )

        # TrueType fonts cannot mix contours and components, so pick out all glyphs
        # that have contours (`bool(len(g)) == True`) and decompose their
        # components, if any.
        decompose = DecomposeComponentsFilter(include=lambda g: len(g))
        for ufo, glyphSet in zip(self.ufos, self.glyphSets):
            decompose(ufo, glyphSet)

        if self.flattenComponents:
            from ufo2ft.filters.flattenComponents import FlattenComponentsFilter

            for ufo, glyphSet in zip(self.ufos, self.glyphSets):
                FlattenComponentsFilter()(ufo, glyphSet)

        # finally apply all custom post-filters
        for funcs, ufo, glyphSet in zip(self.postFilters, self.ufos, self.glyphSets):
            for func in funcs:
                func(ufo, glyphSet)

        return self.glyphSets
