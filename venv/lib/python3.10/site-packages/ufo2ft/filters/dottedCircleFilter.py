"""
Dotted Circle Filter

This filter checks whether a font contains a glyph for U+25CC (DOTTED CIRCLE),
which is inserted by complex shapers to display mark glyphs which have no
associated base glyph, usually as a result of broken clusters but also for
pedagogical reasons. (For example, to display the marks in a table of glyphs.)

If no dotted circle glyph is present in the font, then one is drawn and added.

Next, the filter creates any additional anchors for the dotted circle glyph to
ensure that all marks can be attached to it. It does this by gathering a list
of anchors, finding the set of base glyphs for each anchor, computing the
average position of the anchor on the base glyph (relative to the glyph's width),
and then creating an anchor at that average position on the dotted circle glyph.

The filter must be run as a "pre" filter. This can be done from the command
line like so::

    fontmake -o ttf -g MyFont.glyphs --filter "DottedCircleFilter(pre=True)"

or in the ``lib.plist`` file of a UFO::

    <key>com.github.googlei18n.ufo2ft.filters</key>
    <array>
      <dict>
        <key>name</key>
        <string>DottedCircleFilter</string>
        <key>pre</key>
        <true/>
      </dict>
    </array>

The filter supports the following options:

margin
    When drawing a dotted circle, the vertical space in units around the dotted
    circle.
sidebearings
    When drawing a dotted circle, additional horizontal space in units around
    the dotted circle.
dots
    Number of dots in the circle.

"""
import logging
import math
from statistics import mean

from fontTools.misc.fixedTools import otRound
from ufoLib2.objects import Glyph

from ufo2ft.constants import OPENTYPE_CATEGORIES_KEY
from ufo2ft.featureCompiler import parseLayoutFeatures
from ufo2ft.featureWriters import ast
from ufo2ft.filters import BaseFilter
from ufo2ft.util import _GlyphSet, _LazyFontName

logger = logging.getLogger(__name__)

DO_NOTHING = -1  # Sentinel value (not a valid glyph name)

# Length of cubic Bezier handle used when drawing quarter circles.
# See https://pomax.github.io/bezierinfo/#circles_cubic
CIRCULAR_SUPERNESS = 0.551784777779014


def circle(pen, origin, radius):
    w = (origin[0] - radius, origin[1])
    n = (origin[0], origin[1] + radius)
    e = (origin[0] + radius, origin[1])
    s = (origin[0], origin[1] - radius)

    pen.moveTo(w)
    pen.curveTo(
        (w[0], w[1] + radius * CIRCULAR_SUPERNESS),
        (n[0] - radius * CIRCULAR_SUPERNESS, n[1]),
        n,
    )
    pen.curveTo(
        (n[0] + radius * CIRCULAR_SUPERNESS, n[1]),
        (e[0], e[1] + radius * CIRCULAR_SUPERNESS),
        e,
    )
    pen.curveTo(
        (e[0], e[1] - radius * CIRCULAR_SUPERNESS),
        (s[0] + radius * CIRCULAR_SUPERNESS, s[1]),
        s,
    )
    pen.curveTo(
        (s[0] - radius * CIRCULAR_SUPERNESS, s[1]),
        (w[0], w[1] - radius * CIRCULAR_SUPERNESS),
        w,
    )
    pen.closePath()


class DottedCircleFilter(BaseFilter):

    _kwargs = {"margin": 80, "sidebearing": 160, "dots": 12}

    def __call__(self, font, glyphSet=None):
        fontName = _LazyFontName(font)
        if glyphSet is not None and getattr(glyphSet, "name", None):
            logger.info("Running %s on %s-%s", self.name, fontName, glyphSet.name)
        else:
            logger.info("Running %s on %s", self.name, fontName)

        if glyphSet is None:
            glyphSet = _GlyphSet.from_layer(font)

        self.set_context(font, glyphSet)
        added_glyph = False
        dotted_circle_glyph = self.check_dotted_circle()

        if dotted_circle_glyph == DO_NOTHING:
            return []

        if not dotted_circle_glyph:
            dotted_circle_glyph = self.draw_dotted_circle(glyphSet)
            added_glyph = True

        added_anchors = self.check_and_add_anchors(dotted_circle_glyph)

        if added_anchors:
            self.ensure_base(dotted_circle_glyph)

        if added_glyph or added_anchors:
            return [dotted_circle_glyph.name]
        else:
            return []

    def check_dotted_circle(self):
        """Check for the presence of a dotted circle glyph and return it"""
        font = self.context.font
        glyphset = self.context.glyphSet
        dotted_circle = next((g.name for g in font if 0x25CC in g.unicodes), None)
        if dotted_circle:
            if dotted_circle not in glyphset:
                logger.debug(
                    "Found dotted circle glyph %s in font but not in glyphset",
                    dotted_circle,
                )
                return DO_NOTHING
            logger.debug("Found dotted circle glyph %s", dotted_circle)
            return glyphset[dotted_circle]

    def draw_dotted_circle(self, glyphSet):
        """Add a new dotted circle glyph, drawing its outlines"""
        font = self.context.font
        logger.debug("Adding dotted circle glyph")
        glyph = Glyph(name="uni25CC", unicodes=[0x25CC])
        pen = glyph.getPen()

        bigradius = (font.info.xHeight - 2 * self.options.margin) / 2
        littleradius = bigradius / 6
        left = self.options.sidebearing + littleradius
        right = self.options.sidebearing + bigradius * 2 - littleradius
        middleY = font.info.xHeight / 2
        middleX = (left + right) / 2
        subangle = 2 * math.pi / self.options.dots
        for t in range(self.options.dots):
            angle = t * subangle
            cx = middleX + bigradius * math.cos(angle)
            cy = middleY + bigradius * math.sin(angle)
            circle(pen, (cx, cy), littleradius)

        glyph.setRightMargin(self.options.sidebearing)

        glyphSet["uni25CC"] = glyph
        return glyph

    def check_and_add_anchors(self, dotted_circle_glyph):
        """Check that all mark-attached anchors are present on the dotted
        circle glyph, synthesizing a position for any missing anchors."""
        font = self.context.font

        # First we will gather information about all the anchors in the
        # font at present; for the anchors on marks (starting with "_")
        # we just want to know their names, so we can match them with
        # bases later. For the anchors on bases, we also want to store
        # the position of the anchor so we can average them.
        all_anchors = {}
        any_added = False
        anchorclass = None
        for glyph in font:
            width = None
            try:
                bounds = glyph.getBounds(font)
                if bounds:
                    width = bounds.xMax - bounds.xMin
            except AttributeError:
                bounds = glyph.bounds
                if bounds:
                    width = bounds[2] - bounds[0]
            if width is None:
                width = glyph.width
            for anchor in glyph.anchors:
                anchorclass = anchor.__class__
                if anchor.name.startswith("_"):
                    all_anchors[anchor.name] = []
                    continue
                if not width:
                    continue
                x_percentage = anchor.x / width
                all_anchors.setdefault(anchor.name, []).append((x_percentage, anchor.y))

        # Now we move to the dotted circle. What anchors do we have already?
        dsanchors = set([a.name for a in dotted_circle_glyph.anchors])
        for anchor, positions in all_anchors.items():
            # Skip existing anchors on the dotted-circle, and any anchors
            # which don't have a matching mark glyph (mark-to-lig etc.).
            if anchor in dsanchors or f"_{anchor}" not in all_anchors:
                continue

            # And now we're creating a new one
            anchor_x = dotted_circle_glyph.width * mean([v[0] for v in positions])
            anchor_y = mean([v[1] for v in positions])
            logger.debug(
                "Adding anchor %s to dotted circle glyph at %i,%i",
                anchor,
                anchor_x,
                anchor_y,
            )
            try:
                newanchor = anchorclass()
                newanchor.x = otRound(anchor_x)
                newanchor.y = otRound(anchor_y)
            except TypeError:
                newanchor = anchorclass(otRound(anchor_x), otRound(anchor_y))
            newanchor.name = anchor
            dotted_circle_glyph.appendAnchor(newanchor)
            any_added = True
        return any_added

    # We have added some anchors to the dotted circle glyph. Now we need to
    # ensure the glyph is a base (and specifically a base glyph, not just
    # unclassified), or else it won't be in the list of base glyphs when
    # we come to the mark features writer, and all our work will be for nothing.
    # Also note that if we had a dotted circle glyph in the font already and
    # we have come from Glyphs, glyphsLib would only consider the glyph to
    # be a base if it has anchors, and it might not have had any when glyphsLib
    # wrote the GDEF table.
    # So we have to go digging around for a GDEF table and modify it.
    def ensure_base(self, dotted_circle_glyph):
        dotted_circle = dotted_circle_glyph.name
        font = self.context.font
        feaFile = parseLayoutFeatures(font)
        if ast.findTable(feaFile, "GDEF") is None:
            # We have no GDEF table. GDEFFeatureWriter will create one
            # using the font's lib.
            if OPENTYPE_CATEGORIES_KEY in font.lib:
                font.lib[OPENTYPE_CATEGORIES_KEY][dotted_circle] = "base"
            return
        # We have GDEF table, so we need to find the GlyphClassDef, and add
        # ourselves to the baseGlyphs set.
        for st in feaFile.statements:
            if isinstance(st, ast.TableBlock) and st.name == "GDEF":
                for st2 in st.statements:
                    if isinstance(st2, ast.GlyphClassDefStatement):
                        if (
                            st2.baseGlyphs
                            and dotted_circle not in st2.baseGlyphs.glyphSet()
                        ):
                            st2.baseGlyphs.glyphs.append(dotted_circle)
        # And then put the modified feature file back into the font
        font.features.text = feaFile.asFea()
