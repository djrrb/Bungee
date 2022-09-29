import os
import argparse
import logging

import compreffor
from compreffor.pyCompressor import human_size
from fontTools.ttLib import TTFont
from fontTools.misc.loggingTools import configLogger


def parse_arguments(args=None):
    parser = argparse.ArgumentParser(
        prog='compreffor',
        description="FontTools Compreffor will take a CFF-flavored OpenType font "
                    "and automatically detect repeated routines and generate "
                    "subroutines to minimize the disk space needed to represent "
                    "a font.")
    parser.add_argument("infile", metavar="INPUT",
                        help="path to the input font file")
    parser.add_argument("outfile", nargs="?", metavar="OUTPUT",
                        help="path to the compressed file (default: "
                        "*.compressed.otf)")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="print more messages to stdout; use it multiple "
                        "times to increase the level of verbosity")
    parser.add_argument("-c", "--check", action='store_true',
                        help="verify that the outputted font is valid and "
                             "functionally equivalent to the input")
    parser.add_argument("-d", "--decompress", action="store_true",
                        help="decompress source before compressing (necessary if "
                             "there are subroutines in the source)")
    parser.add_argument("-n", "--nrounds", type=int,
                        help="the number of iterations to run the algorithm"
                             " (default: 4)")
    parser.add_argument("-m", "--max-subrs", type=int,
                        help="limit to the number of subroutines per INDEX "
                        " (default: 65533)")
    parser.add_argument('--generate-cff', action='store_true',
                        help="Also save binary CFF table data as {INPUT}.cff")
    parser.add_argument('--py', dest="method_python", action='store_true',
                        help="Use pure Python method, instead of C++ extension")
    py_meth_group = parser.add_argument_group("options for pure Python method")
    py_meth_group.add_argument("--chunk-ratio", type=float,
                               help="specify the percentage size of the "
                                    "job chunks used for parallel processing "
                                    "(0 < float <= 1; default: 0.1)")
    py_meth_group.add_argument("-p", "--processes", type=int,
                               help="specify number  of concurrent processes to "
                               "run. Use value 1 to perform operation serially "
                               "(default: 12)")

    options = parser.parse_args(args)
    kwargs = vars(options)

    if options.method_python:
        if options.processes is not None and options.processes < 1:
            parser.error('argument --processes expects positive integer > 0')
        if (options.chunk_ratio is not None
                and not (0 < options.chunk_ratio <= 1)):
            parser.error('argument --chunk-ratio expects float number 0 < n <= 1')
    else:
        for attr in ('chunk_ratio', 'processes'):
            if getattr(options, attr):
                opt = attr.replace('_', '-')
                parser.error('argument --%s can only be used with --py (pure '
                             'Python) method' % opt)
            else:
                del kwargs[attr]
    if options.outfile is None:
        options.outfile = "%s.compressed%s" % os.path.splitext(options.infile)

    return kwargs


def main(args=None):
    log = compreffor.log
    timer = compreffor.timer
    timer.reset()

    options = parse_arguments(args)

    # consume kwargs that are not passed on to 'compress' function
    infile = options.pop('infile')
    outfile = options.pop('outfile')
    decompress = options.pop('decompress')
    generate_cff = options.pop('generate_cff')
    check = options.pop('check')
    verbose = options.pop('verbose')

    if verbose == 1:
        level = logging.INFO
    elif verbose > 1:
        level = logging.DEBUG
    else:
        level = logging.WARNING

    configLogger(logger=log, level=level)

    orig_size = os.path.getsize(infile)

    font = TTFont(infile)

    if decompress:
        log.info("Decompressing font with FontTools Subsetter")
        with timer("decompress the font"):
            compreffor.decompress(font)

    log.info("Compressing font through %s Compreffor",
             "pure-Python" if options['method_python'] else "C++")

    compreffor.compress(font, **options)

    with timer("compile and save compressed font"):
        font.save(outfile)

    if generate_cff:
        cff_file = os.path.splitext(outfile)[0] + ".cff"
        with open(cff_file, 'wb') as f:
            font['CFF '].cff.compile(f, None)
        log.info("Saved CFF data to '%s'" % os.path.basename(cff_file))

    if check:
        log.info("Checking compression integrity and call depth")
        passed = compreffor.check(infile, outfile)
        if not passed:
            return 1

    comp_size = os.path.getsize(outfile)
    log.info("Compressed to '%s' -- saved %s" %
             (os.path.basename(outfile), human_size(orig_size - comp_size)))
    log.debug("Total time: %gs", timer.time())


if __name__ == "__main__":
    main()
