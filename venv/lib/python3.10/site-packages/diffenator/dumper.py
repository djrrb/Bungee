"""
Dumper
~~~~~~

Dump a font table.

Tables which can be dumped are attribs, metrics, kerns, glyphs, names,
marks, mkmks, gdef_base and gdef_mark.

Examples
--------

Dump kerning:
dumper /path/to/font.ttf kerns

Dump just kerning pair strings:
dumper /path/to/font.ttf kerns -s

Output report as markdown:
dumper /path/to/font.ttf -md
"""
from __future__ import print_function
from argparse import RawTextHelpFormatter
from diffenator.font import DFont
from diffenator.diff import DiffFonts
from diffenator import CHOICES
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('font')
    parser.add_argument('dump', choices=CHOICES)
    parser.add_argument('-s', '--strings-only', action='store_true')
    parser.add_argument('-ol', '--output-lines', type=int, default=100)
    parser.add_argument('-md', '--markdown', action='store_true')
    parser.add_argument('-i', '--vf-instance',
                        help='Variable font instance to diff')
    parser.add_argument('-r', '--render-path',
                        help="Path to generate png to")
    args = parser.parse_args()

    font = DFont(args.font)

    if font.is_variable and not args.vf_instance:
        raise Exception("Include a VF instance to dump e.g -i wght=400")

    if args.vf_instance:
        variations = {s.split('=')[0]: float(s.split('=')[1]) for s
                      in args.vf_instance.split(", ")}
        font.set_variations(variations)

    table = getattr(font, args.dump, False)
    if not table:
        print(("Font doesn't have {} table".format(args.dump)))
        exit()
    report_len = len(table)

    if args.markdown:
        print(table.to_md(args.output_lines, strings_only=args.strings_only))
    else:
        print(table.to_txt(args.output_lines, strings_only=args.strings_only))

    if args.output_lines < report_len:
        print(("Showing {} out of {} items. Increase the flag -ol "
               "to view more".format(args.output_lines, report_len)))
    if args.render_path:
        table.to_png(args.render_path, limit=args.output_lines)


if __name__ == '__main__':
    main()

