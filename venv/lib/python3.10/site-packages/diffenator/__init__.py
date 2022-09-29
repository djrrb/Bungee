__version__ = "0.9.12"

import io
import sys
if sys.version_info[0] < 3 and sys.version_info[1] < 6:
    raise ImportError("Visualize module requires Python3.6+!")
from array import array
from PIL import Image
from cairo import Context, ImageSurface, FORMAT_A8, FORMAT_ARGB32
from diffenator.constants import FTHintMode
from freetype.raw import *
import uharfbuzz as hb
import os
import logging
try:
    from StringIO import StringIO
except ImportError:  # py3 workaround
    from io import BytesIO as StringIO
if sys.version_info.major == 3:
    unicode = str

CHOICES = [
    'names',
    'marks',
    'mkmks',
    'attribs',
    'metrics',
    'glyphs',
    'kerns',
    'gdef_base',
    'gdef_mark',
]

logger = logging.getLogger("fontdiffenator")
logger.setLevel(logging.INFO)


class Tbl:

    def __init__(self, table_name, data=None, renderable=False):
        if not data:
            self._data = []
        else:
            self._data = data
        self.table_name = table_name
        self.renderable = renderable
        self._report_columns = None

    def append(self, item):
        self._data.append(item)
        if not self._report_columns:
            self._report_columns = item.keys()

    def report_columns(self, items):
        """Columns to display in report"""
        self._report_columns = items

    def to_txt(self, limit=50, strings_only=False, dst=None):
        return self._report(TXTFormatter, limit, strings_only, dst)

    def to_md(self, limit=50, strings_only=False, dst=None):
        return self._report(MDFormatter, limit, strings_only, dst)

    def to_html(self, limit=50, strings_only=False, image=None,
                dst=None):
        return self._report(HTMLFormatter, limit, strings_only, image, dst)

    def _report(self, formatter, limit=50, strings_only=False, image=None,
                dst=None):
        """Generate a report for a table.

        Parameters
        ----------
        formatter: Formatter
            Text formatter to use for report
        strings_only: bool
            If True only return the character combos.

        Returns
        -------
        str
        """
        report = formatter()

        if strings_only and self.renderable:
            report.subsubheading(self.table_name)
            string = ' '.join([r['string'] for r in self._data[:limit]])
            report.paragraph(string)
        else:
            report.subsubheading("{}: {}".format(
                self.table_name, len(self._data)
            ))
            if self._report_columns:
                report.start_table()
                report.table_heading(self._report_columns)
                for row in self._data[:limit]:
                    culled_row = []
                    for name in self._report_columns:
                        culled_row.append(row[name])
                    report.table_row(culled_row)
                report.close_table()
            if image:
                report.img(image)

        if dst:
            with open(dst, 'w') as doc:
                doc.write("\n".join(report.text))
        return report.text

    def _shape_string(self, font, string, ot_features):
        buf = hb.Buffer.create()
        buf.add_str(string)
        buf.guess_segment_properties()
        try:
            features = {f: True for f in ot_features}
            hb.shape(font.hbfont, buf, features)
        except KeyError:
            hb.shape(font.hbfont, buf)
        return buf

    def _tab_width(self, font, limit=800):
        result = 0
        for row in self._data[:limit]:
            buf = self._shape_string(font, row['string'], row['features'])
            if not buf.glyph_positions:
                continue
            adv = sum([i.x_advance for i in buf.glyph_positions])
            if adv > result:
                result = adv
        return result + 300

    def _to_png(self, font, font_position=None, dst=None,
                limit=800, size=1500, tab_width=1500, prefix_characters="",
                suffix_characters=""):
        """Use HB, FreeType and Cairo to produce a png for a table.

        Parameters
        ----------
        font: DFont
        font_position: str
            Label indicating which font has been used.
        dst: str
            Path to output image. If no path is given, return in-memory
        """
        # TODO (M Foley) better packaging for pycairo, freetype-py
        # and uharfbuzz.
        # Users should be able to pip install these bindings without needing
        # to install the correct libs.

        # A special mention to the individuals who maintain these packages. Using
        # these dependencies has sped up the process of creating diff images
        # significantly. It's an incredible age we live in.
        y_tab = int(1500 / 25)
        x_tab = int(tab_width / 64)
        width, height = 1024, 200

        cells_per_row = int((width - x_tab) / x_tab)
        # Compute height of image
        x, y, baseline = x_tab, 0, 0
        for idx, row in enumerate(self._data[:limit]):
            x += x_tab

            if idx % cells_per_row == 0:
                y += y_tab
                x = x_tab
        height += y
        height += 100

        # draw image
        Z = ImageSurface(FORMAT_ARGB32, width, height)
        ctx = Context(Z)
        ctx.rectangle(0, 0, width, height)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill()

        # label image
        ctx.set_font_size(30)
        ctx.set_source_rgb(0.5, 0.5, 0.5)
        ctx.move_to(x_tab, 50)
        ctx.show_text("{}: {}".format(self.table_name, len(self._data)))
        ctx.move_to(x_tab, 100)
        if font_position:
            ctx.show_text("Font Set: {}".format(font_position))
        if len(self._data) > limit:
            ctx.set_font_size(20)
            ctx.move_to(x_tab, 150)
            ctx.show_text("Warning: {} different items. Only showing most serious {}".format(
                len(self._data), limit)
            )

        hb.ot_font_set_funcs(font.hbfont)

        # Draw glyphs
        x, y, baseline = x_tab, 200, 0
        x_pos = x_tab
        y_pos = 200
        for idx, row in enumerate(self._data[:limit]):
            string = "{}{}{}".format(
                prefix_characters,
                row['string'],
                suffix_characters)
            buf = self._shape_string(font, string, row['features'])
            char_info = buf.glyph_infos
            char_pos = buf.glyph_positions
            if not char_info or not char_pos:
                continue
            for info, pos in zip(char_info, char_pos):
                gid = info.codepoint
                font.ftfont.load_glyph(gid, flags=font.ft_load_glyph_flags)
                bitmap = font.ftslot.bitmap

                if bitmap.width > 0:
                    ctx.set_source_rgb(0, 0, 0)
                    glyph_surface = _make_image_surface(font.ftfont.glyph.bitmap, copy=False)
                    ctx.set_source_surface(glyph_surface,
                                           x_pos + font.ftslot.bitmap_left + (pos.x_offset / 64.),
                                           y_pos - font.ftslot.bitmap_top - (pos.y_offset / 64.))
                    glyph_surface.flush()
                    ctx.paint()
                x_pos += (pos.x_advance) / 64.
                y_pos += (pos.y_advance) / 64.

            x_pos += x_tab - (x_pos % x_tab)
            if idx % cells_per_row == 0:
                # add label
                if font_position:
                    ctx.set_source_rgb(0.5, 0.5, 0.5)
                    ctx.set_font_size(10)
                    ctx.move_to(width - 20, y_pos)
                    ctx.rotate(1.5708)
                    ctx.show_text(font_position)
                    ctx.set_source_rgb(0,0,0)
                    ctx.rotate(-1.5708)
                # Start a new row
                y_pos += y_tab
                x_pos = x_tab
        Z.flush()
        if dst:
            Z.write_to_png(dst)
        else:
            img = StringIO()
            Z.write_to_png(img)
            return Image.open(img)

    def sort(self, *args, **kwargs):
        self._data.sort(*args, **kwargs)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        for i in self._data:
            yield i


def _to_array(content, pixel_mode, dst_pitch):
    buffer_size = content.rows * dst_pitch
    buff = array("B", b"0" * buffer_size)
    dstaddr = buff.buffer_info()[0]
    srcaddr = cast(content.buffer, FT_Pointer).value
    src_pitch = content.pitch

    for i in range(content.rows) :
        memmove(dstaddr, srcaddr, src_pitch)
        dstaddr += dst_pitch
        srcaddr += src_pitch
    return buff


def _make_image_surface(bitmap, copy=True):
    """Convert FreeType bitmap to Cairo ImageSurface.

    Special thanks to Hintak and his example code:
    https://github.com/rougier/freetype-py/blob/master/examples/bitmap_to_surface.py


    TODO (M Foley) understand this better and see if a more elegant
    solution exists."""
    content = bitmap._FT_Bitmap
    cairo_format = FORMAT_A8

    src_pitch = content.pitch
    dst_pitch = ImageSurface.format_stride_for_width(cairo_format, content.width)

    pixels = _to_array(content, content.pixel_mode, dst_pitch)
    result = ImageSurface.create_for_data(
        pixels, cairo_format,
        content.width, content.rows,
        dst_pitch)
    return result


class DiffTable(Tbl):
    def __init__(self, table_name, font_a, font_b,
                 data=None, renderable=False):
        super(DiffTable, self).__init__(table_name, data, renderable=renderable)
        self._font_a = font_a
        self._font_b = font_b

    def to_cbdt_gif(self, dst):
        font_a_images = read_cbdt(self._font_a.ttfont)
        font_b_images = read_cbdt(self._font_b.ttfont)

        for element in self._data:
            key_before = element["glyph before"]
            key_after = element["glyph after"]

            image_1 = font_a_images[key_before]
            image_1_gif = Image.new('RGBA', image_1.size, (255, 255, 255))
            image_1_gif.paste(image_1, image_1)
            image_1_gif = image_1_gif.convert('RGB').convert('P', palette=Image.ADAPTIVE)

            image_2 = font_b_images[key_after]
            image_2_gif = Image.new('RGBA', image_2.size, (255, 255, 255))
            image_2_gif.paste(image_2, image_2)
            image_2_gif = image_2_gif.convert('RGB').convert('P', palette=Image.ADAPTIVE)

            img_path = os.path.join(dst, f"{key_before}.gif")
            image_1_gif.save(img_path,
                             save_all=True,
                             append_images=[image_2_gif],
                             duration=1000,
                             loop=0
            )

    def to_gif(self, dst, prefix_characters="", suffix_characters="", limit=800):
        tab_width = max(self._tab_width(self._font_a),
                        self._tab_width(self._font_b))
        img_a = self._to_png(self._font_a, "Before",
                             tab_width=tab_width,
                             prefix_characters=prefix_characters,
                             suffix_characters=suffix_characters,
                             limit=limit)
        img_b = self._to_png(self._font_b, "After",
                             tab_width=tab_width,
                             prefix_characters=prefix_characters,
                             suffix_characters=suffix_characters,
                             limit=limit)

        img_a.save(
            dst,
            save_all=True,
            append_images=[img_b],
            duration=1000,
            loop=0
        )


class DFontTable(Tbl):

    def __init__(self, font, table_name, renderable=False):
        super(DFontTable, self).__init__(table_name, renderable=renderable)
        self._font = font


class DFontTableIMG(DFontTable):

    def to_png(self, dst=None, limit=800):
        font = self._font
        tab_width = self._tab_width(font, limit)
        return self._to_png(font, dst=dst, limit=limit, tab_width=tab_width)


class Formatter:
    """Base Class for formatters"""

    def __init__(self):
        self._text = []

    def style(self):
        pass

    def heading(self, string):
        raise NotImplementedError()

    def subheading(self, string):
        raise NotImplementedError()

    def subsubheading(self, string):
        raise NotImplementedError()

    def table_heading(self, row):
        raise NotImplementedError()

    def table_row(self, row, clip_col=True):
        raise NotImplementedError()

    def linebreak(self):
        self._text.append('')

    def paragraph(self, string):
        self._text.append("{}\n".format(string))

    def start_table(self):
        pass

    def close_table(self):
        pass

    @property
    def text(self):
        return '\n'.join(self._text)


class TXTFormatter(Formatter):
    """Formatter for CommandLines."""
    def heading(self, string):
        self._text.append('**{}**\n'.format(string))

    def subheading(self, string):
        self._text.append('***{}***\n'.format(string))

    def subsubheading(self, string):
        self._text.append('****{}****\n'.format(string))

    def table_heading(self, row):
        header = unicode("{:<20}" * len(row))
        header = header.format(*tuple(row))
        self._text.append(header)

    def table_row(self, row, clip_col=True):
        row = map(str, row)
        if clip_col:
            _row = []
            for item in row:
                if len(item) >= 16:
                    item = item[:16] + "..."
                _row.append(item)
            row = _row
        t_format = unicode("{:<20}" * len(row))
        row = t_format.format(*tuple(row))
        self._text.append(row)


class MDFormatter(Formatter):
    """Formatter for Github Markdown"""
    def heading(self, string):
        self._text.append('# {}\n'.format(string))

    def subheading(self, string):
        self._text.append('## {}\n'.format(string))

    def subsubheading(self, string):
        self._text.append('### {}\n'.format(string))

    def table_heading(self, row):
        string = ' | '.join(row)
        string += '\n'
        string += '--- | ' * len(row)
        self._text.append(string)

    def table_row(self, row):
        row = map(str, row)
        string = ' | '.join(row)
        self._text.append(string)


class HTMLFormatter(Formatter):
    """Formatter for HTML"""

    def style(self):
        self._text.append(
            """
            <style>
            html{font-family: sans-serif; padding: 10px;}

            table{
              font-family: arial, sans-serif;
              border-collapse: collapse;
              width: 100%;
            }

            td, th {
              border: 1px solid #dddddd;
              text-align: left;
              padding: 8px;
            }

            tr:nth-child(even) {
              background-color: #dddddd;
              }
            </style>
            """
        )
    def heading(self, string):
        self._text.append("<h1>{}</h1>\n".format(string))

    def subheading(self, string):
        self._text.append("<h2>{}</h2>\n".format(string))

    def subsubheading(self, string):
        self._text.append("<h3>{}</h3>\n".format(string))

    def start_table(self):
        self._text.append("<table>")

    def close_table(self):
        self._text.append("</table>")

    def table_heading(self, row):
        result = ["<tr>"]
        for cell in row:
            result += ["<th>", cell, "</th>"]
        result += ["</tr>"]
        self._text.append(''.join(result))

    def table_row(self, row):
        result = ["<tr>"]
        for cell in row:
            result += ["<td>", str(cell), "</td>"]
        result += ["</tr>"]
        self._text.append(''.join(result))

    def img(self, path):
        self._text.append("<img src='%s'>" % path)

def read_cbdt(ttfont):
    cbdt_glyphs = {}
    if ttfont.has_key("CBDT"):
        cbdt = ttfont["CBDT"]
        for strike_data in cbdt.strikeData:
            for key, data in strike_data.items():
                cbdt_glyphs[key] = Image.open(io.BytesIO(data.imageData)).convert("RGBA")
    return cbdt_glyphs
