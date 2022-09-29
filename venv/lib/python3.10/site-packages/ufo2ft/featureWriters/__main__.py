import argparse
import logging
from io import StringIO

from fontTools.misc.cliTools import makeOutputFileName

from ufo2ft.featureCompiler import FeatureCompiler
from ufo2ft.featureWriters import loadFeatureWriterFromString, logger

try:
    import ufoLib2

    loader = ufoLib2.Font
except ImportError:
    import defcon

    loader = defcon.Font

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description="Apply feature writers to a UFO file")
parser.add_argument("--output", "-o", metavar="OUTPUT", help="output file name")
parser.add_argument("ufo", metavar="UFO", help="UFO file")
parser.add_argument(
    "writers",
    metavar="WRITER",
    nargs="*",
    help="list of feature writers to enable",
)

args = parser.parse_args()
if not args.output:
    args.output = makeOutputFileName(args.ufo)

ufo = loader(args.ufo)
writers = [loadFeatureWriterFromString(w) for w in args.writers]
compiler = FeatureCompiler(ufo, featureWriters=writers or None)
compiler.setupFeatures()
buf = StringIO()
compiler.writeFeatures(buf)
ufo.features.text = buf.getvalue()

logger.info("Written on %s" % args.output)
ufo.save(args.output)
