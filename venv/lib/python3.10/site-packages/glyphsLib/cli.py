# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import os
import sys

import glyphsLib


def main(args=None):
    if not args:
        args = sys.argv[1:]

    python_executable = os.path.basename(sys.executable)
    parser = argparse.ArgumentParser(prog=f"{python_executable} -m glyphsLib")
    subparsers = parser.add_subparsers()

    parser_glyphs2ufo = subparsers.add_parser("glyphs2ufo", help=glyphs2ufo.__doc__)
    parser_glyphs2ufo.set_defaults(func=glyphs2ufo)
    parser_glyphs2ufo.add_argument(
        "--version", action="version", version="glyphsLib %s" % glyphsLib.__version__
    )
    parser_glyphs2ufo.add_argument(
        "glyphs_file", metavar="GLYPHS_FILE", help="Glyphs file to convert."
    )
    parser_glyphs2ufo.add_argument(
        "-m",
        "--output-dir",
        default=None,
        help="Output directory of masters. (default: directory of Glyphs file)",
    )
    parser_glyphs2ufo.add_argument(
        "-d",
        "--designspace-path",
        default=None,
        help="Output path of designspace file. (default: directory of Glyphs file)",
    )
    parser_glyphs2ufo.add_argument(
        "-n",
        "--instance-dir",
        default=None,
        help=(
            "Output directory of instances. (default: output_dir/instance_ufos"
            "). This sets the file path for instances inside the designspace "
            "file."
        ),
    )
    parser_glyphs2ufo.add_argument(
        "--ufo-module",
        metavar="UFO_MODULE",
        choices=("ufoLib2", "defcon"),
        default="ufoLib2",
        help=(
            "Select the default library for writing UFOs. Choose between: %(choices)s "
            "(default: %(default)s)"
        ),
    )
    group = parser_glyphs2ufo.add_argument_group(
        "Roundtripping between Glyphs and UFOs"
    )
    group.add_argument(
        "--minimal",
        action="store_true",
        help=("Create minimal UFO files with only data needed for building fonts."),
    )
    group.add_argument(
        "--no-preserve-glyphsapp-metadata",
        action="store_false",
        help=(
            "Skip preserving Glyphs metadata in master UFOs and designspace "
            "file, which would be used to minimize differences when "
            "roundtripping between Glyphs and UFOs."
        ),
    )
    group.add_argument(
        "--propagate-anchors",
        default=None,
        action="store_true",
        help=(
            "Copy anchors from underlying components to actual "
            "glyph. Glyphs would do this implicitly, only use if you need "
            "full control over all anchors."
        ),
    )
    gdef_gen_group = group.add_mutually_exclusive_group()
    gdef_gen_group.add_argument(
        "--generate-GDEF",
        action="store_true",
        default=False,
        dest="generate_GDEF",
        help=(
            "Write GDEF categories into the UFO's `public.openTypeCatgeories` lib key."
        ),
    )
    gdef_gen_group.add_argument(
        "--no-generate-GDEF",
        action="store_false",
        default=False,
        dest="generate_GDEF",
        help=(
            "Skip writing GDEF categories into the UFO's "
            "`public.openTypeCatgeories` lib key (default behavior, for backward "
            "compatibility)."
        ),
    )
    group.add_argument(
        "-N",
        "--normalize-ufos",
        action="store_true",
        help=(
            "Normalize UFOs with ufonormalizer, which avoids "
            "differences due to spacing, reordering of keys, etc."
        ),
    )
    group.add_argument(
        "--create-background-layers",
        action="store_true",
        help=(
            "Create background layers for all glyphs unless present, "
            "this can help in a workflow with multiple tools that "
            "may create background layers automatically."
        ),
    )
    group.add_argument(
        "--no-store-editor-state",
        action="store_true",
        help=(
            "Skip storing editor state in the UFO, like which glyphs are open "
            "in which tab (DisplayStrings)."
        ),
    )
    group.add_argument(
        "--write-public-skip-export-glyphs",
        action="store_true",
        help=(
            "Store the glyph export flag in the `public.skipExportGlyphs` list "
            "instead of the glyph-level 'com.schriftgestaltung.Glyphs.Export' lib "
            "key."
        ),
    )
    group = parser_glyphs2ufo.add_argument_group("Glyph data")
    group.add_argument(
        "--glyph-data",
        action="append",
        metavar="GLYPHDATA",
        help=(
            "Custom GlyphData XML file with glyph info (production name, "
            "script, category, subCategory, etc.). Can be used more than once."
        ),
    )

    parser_ufo2glyphs = subparsers.add_parser("ufo2glyphs", help=ufo2glyphs.__doc__)
    parser_ufo2glyphs.set_defaults(func=ufo2glyphs)
    parser_ufo2glyphs.add_argument(
        "--version", action="version", version="glyphsLib %s" % glyphsLib.__version__
    )
    parser_ufo2glyphs.add_argument(
        "designspace_file_or_UFOs",
        nargs="+",
        metavar="DESIGNSPACE_FILE_OR_UFOS",
        help=(
            "A single designspace file *or* one or more UFOs to convert to "
            "a Glyphs file."
        ),
    )
    parser_ufo2glyphs.add_argument(
        "--output-path", help="The path to write the Glyphs file to."
    )
    parser_ufo2glyphs.add_argument(
        "--ufo-module",
        metavar="UFO_MODULE",
        choices=("ufoLib2", "defcon"),
        default="ufoLib2",
        help=(
            "Select the default library for reading UFOs. Choose between: %(choices)s "
            "(default: %(default)s)"
        ),
    )
    group = parser_ufo2glyphs.add_argument_group(
        "Roundtripping between UFOs and Glyphs"
    )
    group.add_argument(
        "--no-preserve-glyphsapp-metadata",
        action="store_false",
        help=(
            "Skip preserving Glyphs metadata in master UFOs and designspace "
            "file, which would be used to minimize differences when "
            "roundtripping between Glyphs and UFOs."
        ),
    )
    group.add_argument(
        "--enable-last-change",
        action="store_false",
        help="Store modification timestamp in glyphs. Unnecessary when using Git.",
    )
    group.add_argument(
        "--enable-automatic-alignment",
        action="store_false",
        help="Enable automatic alignment of components in glyphs.",
    )

    options = parser.parse_args(args)

    if "func" in vars(options):
        return options.func(options)
    else:
        parser.print_help()


def glyphs2ufo(options):
    """Converts a Glyphs.app source file into UFO masters and a designspace file."""
    if options.output_dir is None:
        options.output_dir = os.path.dirname(options.glyphs_file) or "."

    if options.designspace_path is None:
        options.designspace_path = os.path.join(
            options.output_dir,
            os.path.basename(os.path.splitext(options.glyphs_file)[0]) + ".designspace",
        )

    # If options.instance_dir is None, instance UFO paths in the designspace
    # file will either use the value in customParameter's UFO_FILENAME_CUSTOM_PARAM or
    # be made relative to "instance_ufos/".
    glyphsLib.build_masters(
        options.glyphs_file,
        options.output_dir,
        options.instance_dir,
        designspace_path=options.designspace_path,
        minimize_glyphs_diffs=options.no_preserve_glyphsapp_metadata,
        propagate_anchors=options.propagate_anchors,
        normalize_ufos=options.normalize_ufos,
        create_background_layers=options.create_background_layers,
        generate_GDEF=options.generate_GDEF,
        store_editor_state=not options.no_store_editor_state,
        write_skipexportglyphs=options.write_public_skip_export_glyphs,
        ufo_module=__import__(options.ufo_module),
        minimal=options.minimal,
        glyph_data=options.glyph_data or None,
    )


def _glyphs2ufo_entry_point():
    """Provides entry point for a script to keep argparsing in main()."""
    args = sys.argv[1:]
    args.insert(0, "glyphs2ufo")
    return main(args)


def ufo2glyphs(options):
    """Convert one designspace file or one or more UFOs to a Glyphs.app source file."""
    import fontTools.designspaceLib
    from glyphsLib.util import open_ufo

    ufo_module = __import__(options.ufo_module)

    sources = options.designspace_file_or_UFOs
    designspace_file = None
    if (
        len(sources) == 1
        and sources[0].endswith(".designspace")
        and os.path.isfile(sources[0])
    ):
        designspace_file = sources[0]
        designspace = fontTools.designspaceLib.DesignSpaceDocument()
        designspace.read(designspace_file)
        object_to_read = designspace
    elif all(source.endswith(".ufo") and os.path.isdir(source) for source in sources):
        ufos = [open_ufo(source, ufo_module.Font) for source in sources]
        ufos.sort(
            key=lambda ufo: [  # Order the masters by weight and width
                ufo.info.openTypeOS2WeightClass or 400,
                ufo.info.openTypeOS2WidthClass or 5,
            ]
        )
        object_to_read = ufos
    else:
        print(
            "Please specify just one designspace file *or* one or more "
            "UFOs. They must end in '.designspace' or '.ufo', respectively.",
            file=sys.stderr,
        )
        return 1

    font = glyphsLib.to_glyphs(
        object_to_read,
        ufo_module=ufo_module,
        minimize_ufo_diffs=options.no_preserve_glyphsapp_metadata,
    )

    # Make the Glyphs file more suitable for roundtrip:
    font.customParameters["Disable Last Change"] = options.enable_last_change
    font.disablesAutomaticAlignment = options.enable_automatic_alignment

    if options.output_path:
        font.save(options.output_path)
    else:
        if designspace_file:
            filename_to_write = os.path.splitext(designspace_file)[0] + ".glyphs"
        else:
            filename_to_write = os.path.join(
                os.path.dirname(sources[0]),
                font.familyName.replace(" ", "") + ".glyphs",
            )
        font.save(filename_to_write)


def _ufo2glyphs_entry_point():
    """Provides entry point for a script to keep argparsing in main()."""
    args = sys.argv[1:]
    args.insert(0, "ufo2glyphs")
    return main(args)
