import logging
from types import SimpleNamespace

from fontTools.misc.loggingTools import Timer

from ufo2ft.util import _GlyphSet, _LazyFontName, getMaxComponentDepth

logger = logging.getLogger(__name__)


class BaseFilter:

    # tuple of strings listing the names of required positional arguments
    # which will be set as attributes of the filter instance
    _args = ()

    # dictionary containing the names of optional keyword arguments and
    # their default values, which will be set as instance attributes
    _kwargs = {}

    # pre-filter when True, post-filter when False, meaning before or after default
    # filters
    _pre = False

    def __init__(self, *args, **kwargs):
        self.options = options = SimpleNamespace()

        num_required = len(self._args)
        num_args = len(args)
        # process positional arguments as keyword arguments
        if num_args < num_required:
            args = (
                *args,
                *(kwargs.pop(a) for a in self._args[num_args:] if a in kwargs),
            )
            num_args = len(args)
            duplicated_args = [k for k in self._args if k in kwargs]
            if duplicated_args:
                num_duplicated = len(duplicated_args)
                raise TypeError(
                    "got {} duplicated positional argument{}: {}".format(
                        num_duplicated,
                        "s" if num_duplicated > 1 else "",
                        ", ".join(duplicated_args),
                    )
                )
        # process positional arguments
        if num_args < num_required:
            missing = [repr(a) for a in self._args[num_args:]]
            num_missing = len(missing)
            raise TypeError(
                "missing {} required positional argument{}: {}".format(
                    num_missing, "s" if num_missing > 1 else "", ", ".join(missing)
                )
            )
        elif num_args > num_required:
            extra = [repr(a) for a in args[num_required:]]
            num_extra = len(extra)
            raise TypeError(
                "got {} unsupported positional argument{}: {}".format(
                    num_extra, "s" if num_extra > 1 else "", ", ".join(extra)
                )
            )
        for key, value in zip(self._args, args):
            setattr(options, key, value)

        # process optional keyword arguments
        for key, default in self._kwargs.items():
            setattr(options, key, kwargs.pop(key, default))

        # process special pre argument
        self.pre = kwargs.pop("pre", self._pre)

        # process special include/exclude arguments
        include = kwargs.pop("include", None)
        exclude = kwargs.pop("exclude", None)
        if include is not None and exclude is not None:
            raise ValueError("'include' and 'exclude' arguments are mutually exclusive")
        if callable(include):
            # 'include' can be a function (e.g. lambda) that takes a
            # glyph object and returns True/False based on some test
            self.include = include
            self._include_repr = lambda: repr(include)
        elif include is not None:
            # or it can be a list of glyph names to be included
            included = set(include)
            self.include = lambda g: g.name in included
            self._include_repr = lambda: repr(include)
        elif exclude is not None:
            # alternatively one can provide a list of names to not include
            excluded = set(exclude)
            self.include = lambda g: g.name not in excluded
            self._exclude_repr = lambda: repr(exclude)
        else:
            # by default, all glyphs are included
            self.include = lambda g: True

        # raise if any unsupported keyword arguments
        if kwargs:
            num_left = len(kwargs)
            raise TypeError(
                "got {}unsupported keyword argument{}: {}".format(
                    "an " if num_left == 1 else "",
                    "s" if len(kwargs) > 1 else "",
                    ", ".join(f"'{k}'" for k in kwargs),
                )
            )

        # run the filter's custom initialization code
        self.start()

    def __repr__(self):
        items = []
        if self._args:
            items.append(
                ", ".join(repr(getattr(self.options, arg)) for arg in self._args)
            )
        if self._kwargs:
            items.append(
                ", ".join(
                    "{}={!r}".format(k, getattr(self.options, k))
                    for k in sorted(self._kwargs)
                )
            )
        if hasattr(self, "_include_repr"):
            items.append(f"include={self._include_repr()}")
        elif hasattr(self, "_exclude_repr"):
            items.append(f"exclude={self._exclude_repr()}")
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def start(self):
        """Subclasses can perform here custom initialization code."""
        pass

    def set_context(self, font, glyphSet):
        """Populate a `self.context` namespace, which is reset before each
        new filter call.

        Subclasses can override this to provide contextual information
        which depends on other data in the font that is not available in
        the glyphs objects currently being filtered, or set any other
        temporary attributes.

        The default implementation simply sets the current font and glyphSet,
        and initializes an empty set that keeps track of the names of the
        glyphs that were modified.

        Returns the namespace instance.
        """
        self.context = SimpleNamespace(font=font, glyphSet=glyphSet)
        self.context.modified = set()
        return self.context

    def filter(self, glyph):
        """This is where the filter is applied to a single glyph.
        Subclasses must override this method, and return True
        when the glyph was modified.
        """
        raise NotImplementedError

    @property
    def name(self):
        return self.__class__.__name__

    def __call__(self, font, glyphSet=None):
        """Run this filter on all the included glyphs.
        Return the set of glyph names that were modified, if any.

        If `glyphSet` (dict) argument is provided, run the filter on
        the glyphs contained therein (which may be copies).
        Otherwise, run the filter in-place on the font's default
        glyph set.
        """
        fontName = _LazyFontName(font)
        if glyphSet is not None and getattr(glyphSet, "name", None):
            logger.info("Running %s on %s-%s", self.name, fontName, glyphSet.name)
        else:
            logger.info("Running %s on %s", self.name, fontName)

        if glyphSet is None:
            glyphSet = _GlyphSet.from_layer(font)

        context = self.set_context(font, glyphSet)

        filter_ = self.filter
        include = self.include
        modified = context.modified

        # process composite glyphs in decreasing component depth order (i.e. composites
        # with more deeply nested components before shallower ones) to avoid
        # order-dependent interferences while filtering glyphs with nested components
        # https://github.com/googlefonts/ufo2ft/issues/621
        orderedGlyphs = sorted(
            glyphSet.keys(), key=lambda g: -getMaxComponentDepth(glyphSet[g], glyphSet)
        )

        with Timer() as t:
            for glyphName in orderedGlyphs:
                if glyphName in modified:
                    continue
                glyph = glyphSet[glyphName]
                if include(glyph) and filter_(glyph):
                    modified.add(glyphName)

        num = len(modified)
        if num > 0:
            logger.debug(
                "Took %.3fs to run %s on %d glyph%s",
                t,
                self.name,
                len(modified),
                "" if num == 1 else "s",
            )
        return modified
