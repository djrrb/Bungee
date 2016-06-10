#!/bin/sh

# Use pyftsubset (part of FontTools) to:
# - Do basic optimisations
# - Strip ".alt0" fake alternates
#
# Note that some internal glyph names will be rewritten,
# e.g. Germandbls becomes uni1E9E
#
# Also note that glyphID's might change. They are referenced
# by the SVG table. Keep them matched up!
pyftsubset Bungee_Color-Regular_svg.ttf --verbose --glyphs-file=subset-glyphs.txt --no-subset-tables+='SVG ' --drop-tables-='SVG ' --output-file=Bungee_Color-Regular-svg-subset.ttf