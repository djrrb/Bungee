import argparse
import logging

from fontTools.misc.cliTools import makeOutputFileName

from ufo2ft.filters import loadFilterFromString, logger

try:
    import ufoLib2

    loader = ufoLib2.Font.open
except ImportError:
    import defcon

    loader = defcon.Font

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description="Filter a UFO file")
parser.add_argument("--output", "-o", metavar="OUTPUT", help="output file name")
include_group = parser.add_mutually_exclusive_group(required=False)
include_group.add_argument(
    "--include", metavar="GLYPHS", help="comma-separated list of glyphs to filter"
)
include_group.add_argument(
    "--exclude", metavar="GLYPHS", help="comma-separated list of glyphs to not filter"
)
parser.add_argument("ufo", metavar="UFO", help="UFO file")
parser.add_argument("filters", metavar="FILTER", nargs="+", help="filter name")

args = parser.parse_args()
if not args.output:
    args.output = makeOutputFileName(args.ufo)

ufo = loader(args.ufo)

include = None

if args.include:
    include_set = set(args.include.split(","))

    def include(g):
        return g.name in include_set

elif args.exclude:
    exclude_set = set(args.exclude.split(","))

    def include(g):
        return g.name not in exclude_set


for filtername in args.filters:
    f = loadFilterFromString(filtername)
    if include is not None:
        f.include = include
    f(ufo)

logger.info("Written on %s" % args.output)
ufo.save(args.output)
