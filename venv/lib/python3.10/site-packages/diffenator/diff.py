# Copyright 2017 Google Inc. All Rights Reserved.
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
"""
Module to diff fonts.
"""
from __future__ import print_function
import collections
from diffenator import DiffTable, TXTFormatter, MDFormatter, HTMLFormatter, read_cbdt
import os
import time
import logging
from PIL import Image


__all__ = ['DiffFonts', 'diff_metrics', 'diff_kerning',
           'diff_marks', 'diff_mkmks', 'diff_attribs', 'diff_glyphs']

logger = logging.getLogger('fontdiffenator')


def timer(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            logger.info('%r  %2.2f ms' % \
                  (method.__name__, (te - ts) * 1000))
        return result
    return timed


class DiffFonts:
    """Wrapper to diff all font tables

    Paramters
    ---------
    font_before: DFont
    font_after: DFont
    settings: dict
    """

    SETTINGS = dict(
        glyphs_thresh=0,
        marks_thresh=0,
        mkmks_thresh=0,
        metrics_thresh=0,
        kerns_thresh=0,
        cbdt_thresh=0,
        to_diff=["*"],
        render_diffs=False,
        render_path=False,
        html_output=False,
    )
    def __init__(self, font_before, font_after, settings=None):
        self.font_before = font_before
        self.font_after = font_after
        self.renderable = font_after.ftfont.is_scalable and font_before.ftfont.is_scalable
        self._data = collections.defaultdict(dict)
        self._settings = self.SETTINGS
        if settings:
            for key in settings:
                if key not in self._settings:
                    continue
                self._settings[key] = settings[key]

        if "*" in self._settings["to_diff"]:
            self.run_all_diffs()
        else:
            if "names" in self._settings["to_diff"]:
                self.names()
            if "attribs" in self._settings["to_diff"]:
                self.attribs()
            if "glyphs" in self._settings["to_diff"]:
                self.glyphs(self._settings["glyphs_thresh"])
            if "kerns" in self._settings["to_diff"]:
                self.kerns(self._settings["kerns_thresh"])
            if "metrics" in self._settings["to_diff"]:
                self.metrics(self._settings["metrics_thresh"])
            if "marks" in self._settings["to_diff"]:
                self.marks(self._settings["marks_thresh"])
            if "mkmks" in self._settings["to_diff"]:
                self.mkmks(self._settings["mkmks_thresh"])
            if "cbdt" in self._settings["to_diff"]:
                self.cbdt(self._settings["cbdt_thresh"])
            if "gdef_base" in self._settings["to_diff"]:
                self.gdef_base()
            if "gdef_mark" in self._settings["to_diff"]:
                self.gdef_mark()

    def run_all_diffs(self):
        self.names()
        self.attribs()
        self.glyphs(self._settings["glyphs_thresh"])
        self.kerns(self._settings["kerns_thresh"])
        self.metrics(self._settings["metrics_thresh"])
        self.marks(self._settings["marks_thresh"])
        self.mkmks(self._settings["mkmks_thresh"])
        self.cbdt(self._settings["cbdt_thresh"])
        self.gdef_base()
        self.gdef_mark()

    def to_dict(self):
        serialised_data = self._serialise()
        return serialised_data

    def to_gifs(self, dst, limit=800):
        """output before and after gifs for table"""
        if not os.path.isdir(dst):
            os.mkdir(dst)

        for table in self._data:
            for subtable in self._data[table]:
                _table = self._data[table][subtable]
                if len(_table) < 1:
                    continue
                if table == "cbdt":
                    _table.to_cbdt_gif(dst)
                elif _table.renderable and self.renderable:
                    filename = _table.table_name.replace(" ", "_") + ".gif"
                    img_path = os.path.join(dst, filename)
                    if table == "metrics":
                        _table.to_gif(img_path, prefix_characters="II", suffix_characters="II", limit=limit)
                    elif table == "gdef_mark":
                        prefix = "A"
                        _table.to_gif(img_path, prefix_characters=prefix, limit=limit)
                    elif table == "gdef_base":
                        suffix = chr(int("0301", 16)) # acutecomb
                        _table.to_gif(img_path, suffix_characters=suffix, limit=limit)

                    else:
                        _table.to_gif(img_path, limit=limit)

    def _to_report(self, limit=50, dst=None, r_type="txt", image_dir=None):
        """Output before and after report"""
        reports = []

        if r_type == "txt":
            report_header = TXTFormatter()
        elif r_type == "md":
            report_header = MDFormatter()
        elif r_type == "html":
            report_header = HTMLFormatter()

        report_header.style()
        report_header.heading("Diffenator")
        report_header.paragraph(("Displaying the {} most significant items in "
            "each table. To increase use the '-ol' flag").format(limit))
        reports.append(report_header.text)
        for table in self._data:
            for subtable in self._data[table]:
                current_table = self._data[table][subtable]
                if len(current_table) < 1:
                    continue
                if r_type == "txt":
                    reports.append(current_table.to_txt(limit=limit))
                elif r_type == "md":
                    reports.append(current_table.to_md(limit=limit))
                elif r_type == "html":
                    if image_dir and self.renderable and current_table.renderable:
                        image = os.path.join(image_dir, "%s_%s.gif" % (table, subtable))
                        reports.append(current_table.to_html(limit=limit,
                                       image=image))
                    else:
                        reports.append(current_table.to_html(limit=limit))

        if dst:
            with open(dst, 'w') as doc:
                doc.write("\n\n".join(reports))
        else:
            return "\n\n".join(reports)

    def to_txt(self, limit=50, dst=None):
        """Output diff report as txt"""
        return self._to_report(limit=limit, dst=dst, r_type="txt")

    def to_md(self, limit=50, dst=None):
        """Output diff report as md"""
        return self._to_report(limit=limit, dst=dst, r_type="md")

    def to_html(self, limit=50, dst=None, image_dir=None):
        return self._to_report(limit=limit, dst=dst, r_type="html",
                               image_dir=image_dir)

    def _serialise(self):
        """Serialiser for container data"""
        # TODO (M Foley)
        pass

    def marks(self, threshold=None):
        if not threshold:
            threshold = self._settings["marks_thresh"]
        self._data["marks"] = diff_marks(
                self.font_before, self.font_after,
                self.font_before.marks, self.font_after.marks,
                name="marks",
                thresh=threshold
        )

    def mkmks(self, threshold=None):
        if not threshold:
            threshold = self._settings["mkmks_thresh"]
        self._data["mkmks"] = diff_marks(
            self.font_before, self.font_after,
            self.font_before.mkmks, self.font_after.mkmks,
            name="mkmks",
            thresh=threshold
        )

    def cbdt(self, threshold=None, render_path=None, html_output=None):
        if not threshold:
            threshold = self._settings["cbdt_thresh"]
        if not render_path:
            render_path = self._settings["render_path"]
        if not html_output:
            html_output = self._settings["html_output"]
        self._data["cbdt"] = diff_cbdt_glyphs(
            self.font_before, self.font_after,
            thresh=threshold, render_path=render_path, html_output=html_output
        )

    def metrics(self, threshold=None):
        if not threshold:
            threshold = self._settings["metrics_thresh"]
        self._data["metrics"] = diff_metrics(self.font_before, self.font_after,
                thresh=threshold)

    def glyphs(self, threshold=None, render_diffs=None):
        if not threshold:
            threshold = self._settings["glyphs_thresh"]
        if not render_diffs:
            render_diffs = self._settings["render_diffs"]
        self._data["glyphs"] = diff_glyphs(self.font_before, self.font_after,
            thresh=threshold, render_diffs=render_diffs)

    def kerns(self, threshold=None):
        if not threshold:
            threshold = self._settings["kerns_thresh"]
        self._data["kerns"] = diff_kerning(self.font_before, self.font_after,
            thresh=threshold)

    def attribs(self):
        self._data["attribs"] = diff_attribs(self.font_before, self.font_after)

    def names(self):
        self._data["names"] = diff_nametable(self.font_before, self.font_after)

    def gdef_base(self):
        self._data["gdef_base"] = diff_gdef_base(self.font_before, self.font_after)

    def gdef_mark(self):
        self._data["gdef_mark"] = diff_gdef_mark(self.font_before, self.font_after)


def _subtract_items(items_a, items_b):
    subtract = set(items_a.keys()) - set(items_b.keys())
    return [items_a[i] for i in subtract]


@timer
def diff_nametable(font_before, font_after):
    """Find nametable differences between two fonts.

    Rows are matched by attribute id.

    Parameters
    ----------
    font_before: DFont
    font_after: DFont

    Returns
    -------
    DiffTable
    """
    nametable_before = font_before.names
    nametable_after = font_after.names

    names_before_h = {i['id']: i for i in nametable_before}
    names_after_h = {i['id']: i for i in nametable_after}

    missing = _subtract_items(names_before_h, names_after_h)
    new = _subtract_items(names_after_h, names_before_h)
    modified = _modified_names(names_before_h, names_after_h)

    new = DiffTable("names new", font_before, font_after, data=new)
    new.report_columns(["id", "string"])
    new.sort(key=lambda k: k["id"])
    missing = DiffTable("names missing", font_before, font_after, data=missing)
    missing.report_columns(["id", "string"])
    missing.sort(key=lambda k: k["id"])
    modified = DiffTable("names modified", font_before, font_after, data=modified)
    modified.report_columns(["id", "string_a", "string_b"])
    modified.sort(key=lambda k: k["id"])
    return {
        'new': new,
        'missing': missing,
        'modified': modified,
    }


def _modified_names(names_before, names_after):
    shared = set(names_before.keys()) & set(names_after.keys())

    table = []
    for k in shared:
        if names_before[k]['string'] != names_after[k]['string']:
            row = {
                'id': names_before[k]['id'],
                'string_a': names_before[k]['string'],
                'string_b': names_after[k]['string']
            }
            table.append(row)
    return table


@timer
def diff_glyphs(font_before, font_after,
                thresh=0.00, scale_upms=True, render_diffs=False):
    """Find glyph differences between two fonts.

    Rows are matched by glyph key, which consists of
    the glyph's characters and OT features.

    Parameters
    ----------
    font_before: DFont
    font_after: DFont
    thresh: Ignore differences below this value
    scale_upms:
        Scale values in relation to the font's upms. See readme
        for example.
    render_diffs: Boolean
        If True, diff glyphs by rendering them. Return ratio of changed
        pixels.
        If False, diff glyphs by calculating the surface area of each glyph.
        Return ratio of changed surface area.

    Returns
    -------
    dict
        {
            "new": DiffTable,
            "missing": DiffTable,
            "modified": DiffTable
        }
    """
    glyphs_before = font_before.glyphs
    glyphs_after = font_after.glyphs

    glyphs_before_h = {r['glyph'].key: r for r in glyphs_before}
    glyphs_after_h = {r['glyph'].key: r for r in glyphs_after}

    missing = _subtract_items(glyphs_before_h, glyphs_after_h)
    new = _subtract_items(glyphs_after_h, glyphs_before_h)
    modified = _modified_glyphs(glyphs_before_h, glyphs_after_h, thresh,
                                scale_upms=scale_upms, render_diffs=render_diffs)
    
    new = DiffTable("glyphs new", font_before, font_after, data=new, renderable=True)
    new.report_columns(["glyph", "area", "string"])
    new.sort(key=lambda k: k["glyph"].name)

    missing = DiffTable("glyphs missing", font_before, font_after, data=missing, renderable=True)
    missing.report_columns(["glyph", "area", "string"])
    missing.sort(key=lambda k: k["glyph"].name)

    modified = DiffTable("glyphs modified", font_before, font_after, data=modified, renderable=True)
    modified.report_columns(["glyph", "diff", "string"])
    modified.sort(key=lambda k: abs(k["diff"]), reverse=True)
    return {
        'new': new,
        'missing': missing,
        'modified': modified
    }


def _modified_glyphs(glyphs_before, glyphs_after, thresh=0.00,
                     upm_before=None, upm_after=None, scale_upms=False,
                     render_diffs=False):
    shared = set(glyphs_before.keys()) & set(glyphs_after.keys())

    table = []
    for k in shared:
        glyph_before = glyphs_before[k]
        glyph_after = glyphs_after[k]
        if all([scale_upms, upm_before, upm_after]):
            glyph_before['area'] = (glyph_before['area'] / upm_before) * upm_after
            glyph_after['area'] = (glyph_after['area'] / upm_after) * upm_before

        if render_diffs:
            diff = diff_rendering(glyph_before['glyph'], glyph_after['glyph'])
        else:
            # using abs does not take into consideration if a curve is reversed
            area_before = abs(glyph_before['area'])
            area_after = abs(glyph_after['area'])
            diff = diff_area(area_before, area_after)
        if diff > thresh:
            glyph = glyph_before
            glyph['diff'] = round(diff, 4)
            table.append(glyph)
    return table


def diff_rendering(glyph_before, glyph_after, ft_size=1500):
    """Diff two glyphs by rendering them. Return pixel differences
    as a percentage"""
    font_before = glyph_before.font
    font_before.ftfont.set_char_size(ft_size)
    font_after = glyph_after.font
    font_after.ftfont.set_char_size(ft_size)

    # Image before
    font_before.ftfont.load_glyph(glyph_before.index, flags=font_before.ft_load_glyph_flags)
    bitmap_before = font_before.ftslot.bitmap
    img_before = Image.new("L", (bitmap_before.width, bitmap_before.rows))
    img_before.putdata(bitmap_before.buffer)

    # Image after
    font_after.ftfont.load_glyph(glyph_after.index, flags=font_after.ft_load_glyph_flags)
    bitmap_after = font_after.ftslot.bitmap
    img_after = Image.new("L", (bitmap_after.width, bitmap_after.rows))
    img_after.putdata(bitmap_after.buffer)
    return _diff_images(img_before, img_after)


def diff_area(area_before, area_after):
    smallest = min([area_before, area_after])
    largest = max([area_before, area_after])
    try:
        diff = abs((float(smallest) / float(largest)) - 1)
    except ZeroDivisionError:
        # for this to happen, both the smallest and largest must be 0. This
        # means the glyph is a whitespace glyph such as a space or uni00A0
        diff = 0
    return diff


def _diff_images(img_before, img_after):
    """Compare two rendered images and return the ratio of changed
    pixels.
    TODO (M FOLEY) Crop images so there are no sidebearings to glyphs"""
    width_before, height_before = img_before.size
    width_after, height_after = img_after.size
    data_before = img_before.getdata()
    data_after = img_after.getdata()

    width, height = max(width_before, width_after), max(height_before, height_after)
    offset_ax = (width - width_before) // 2
    offset_ay = (height - height_before) // 2
    offset_bx = (width - width_after) // 2
    offset_by = (height - height_after) // 2

    diff = 0
    for y in range(height):
        for x in range(width):
            ax, ay = x - offset_ax, y - offset_ay
            bx, by = x - offset_bx, y - offset_by
            if (ax < 0 or bx < 0 or ax >= width_before or bx >= width_after or
                ay < 0 or by < 0 or ay >= height_before or by >= height_after):
                diff += 1
            else:
                if data_before[ax + ay *width_before] != data_after[bx + by * width_after]:
                    diff += 1
    try:
        return round(diff / float(width * height), 4)
    except ZeroDivisionError:
        return 0.0


@timer
def diff_kerning(font_before, font_after, thresh=2, scale_upms=True):
    """Find kerning differences between two fonts.

    Class kerns are flattened and then tested for differences.

    Rows are matched by the left and right glyph keys.

    Some fonts use a kern table instead of gpos kerns, test these
    if no gpos kerns exist. This problem exists in Open Sans v1.

    Parameters
    ----------
    font_before: DFont
    font_after: DFont
    thresh: Ignore differences below this value
    scale_upms:
        Scale values in relation to the font's upms. See readme
        for example.

    Returns
    -------
    dict
        {
            "new": [diff_table],
            "missing": [diff_table],
            "modified": [diff_table]
        }
    """
    kern_before = font_before.kerns
    kern_after = font_after.kerns

    upm_before = font_before.ttfont['head'].unitsPerEm
    upm_after = font_after.ttfont['head'].unitsPerEm

    charset_before = set([font_before.glyph(g).key for g in font_before.glyphset])
    charset_after = set([font_after.glyph(g).key for g in font_after.glyphset])

    kern_before_h = {i['left'].key + i['right'].key: i for i in kern_before
                if i['left'].key in charset_after and i['right'].key in charset_after}
    kern_after_h = {i['left'].key + i['right'].key: i for i in kern_after
                if i['left'].key in charset_before and i['right'].key in charset_before}

    missing = _subtract_items(kern_before_h, kern_after_h)
    missing = [i for i in missing if abs(i["value"]) >= 1]
    new = _subtract_items(kern_after_h, kern_before_h)
    new = [i for i in new if abs(i["value"]) >= 1]
    modified = _modified_kerns(kern_before_h, kern_after_h, thresh,
                               upm_before, upm_after, scale_upms=scale_upms)
    missing = DiffTable("kerns missing", font_before, font_after, data=missing, renderable=True)
    missing.report_columns(["left", "right", "value", "string"])
    missing.sort(key=lambda k: abs(k["value"]), reverse=True)

    new = DiffTable("kerns new", font_before, font_after, data=new, renderable=True)
    new.report_columns(["left", "right", "value", "string"])
    new.sort(key=lambda k: abs(k["value"]), reverse=True)
    
    modified = DiffTable("kerns modified", font_before, font_after, data=modified, renderable=True)
    modified.report_columns(["left", "right", "diff", "string"])
    modified.sort(key=lambda k: abs(k["diff"]), reverse=True)
    return {
        'new': new,
        'missing': missing,
        'modified': modified,
    }


def _modified_kerns(kern_before, kern_after, thresh=2,
                    upm_before=None, upm_after=None, scale_upms=False):
    shared = set(kern_before.keys()) & set(kern_after.keys())

    table = []
    for k in shared:
        if scale_upms and upm_before and upm_after:
            kern_before[k]['value'] = (kern_before[k]['value'] / float(upm_before)) * upm_before
            kern_after[k]['value'] = (kern_after[k]['value'] / float(upm_after)) * upm_before

        diff = kern_after[k]['value'] - kern_before[k]['value']
        if abs(diff) > thresh:
            kern_diff = kern_before[k]
            kern_diff['diff'] = kern_after[k]['value'] - kern_before[k]['value']
            del kern_diff['value']
            table.append(kern_diff)
    return table


@timer
def diff_metrics(font_before, font_after, thresh=1, scale_upms=True):
    """Find metrics differences between two fonts.

    Rows are matched by each using glyph key, which consists of
    the glyph's characters and OT features.

    Parameters
    ----------
    font_before: DFont
    font_after: DFont
    thresh:
        Ignore modified metrics under this value
    scale_upms:
        Scale values in relation to the font's upms. See readme
        for example.

    Returns
    -------
    dict
        {
            "new": [diff_table],
            "missing": [diff_table],
            "modified": [diff_table]
        }
    """
    metrics_before = font_before.metrics
    metrics_after = font_after.metrics

    upm_before = font_before.ttfont['head'].unitsPerEm
    upm_after = font_after.ttfont['head'].unitsPerEm

    metrics_before_h = {i['glyph'].key: i for i in metrics_before}
    metrics_after_h = {i['glyph'].key: i for i in metrics_after}

    modified = _modified_metrics(metrics_before_h, metrics_after_h, thresh,
            upm_before, upm_after, scale_upms)
    modified = DiffTable("metrics modified", font_before, font_after, data=modified, renderable=True)
    modified.report_columns(["glyph", "diff_adv"])
    modified.sort(key=lambda k: k["diff_adv"], reverse=True)
    return {
            'modified': modified
            }


def _modified_metrics(metrics_before, metrics_after, thresh=2,
                      upm_before=None, upm_after=None, scale_upms=False):

    shared = set(metrics_before.keys()) & set(metrics_after.keys())

    table = []
    for k in shared:
        if scale_upms and upm_before and upm_after:
            metrics_before[k]['adv'] = (metrics_before[k]['adv'] / float(upm_before)) * upm_before
            metrics_after[k]['adv'] = (metrics_after[k]['adv'] / float(upm_after)) * upm_before

        diff = abs(metrics_after[k]['adv'] - metrics_before[k]['adv'])
        if diff > thresh:
            metrics = metrics_before[k]
            metrics['diff_adv'] = diff
            metrics['diff_lsb'] = metrics_after[k]['lsb'] - metrics_after[k]['lsb']
            metrics['diff_rsb'] = metrics_after[k]['rsb'] - metrics_after[k]['rsb']
            table.append(metrics)
    return table


@timer
def diff_attribs(font_before, font_after, scale_upm=True):
    """Find attribute differences between two fonts.

    Rows are matched by using attrib.

    Parameters
    ----------
    font_before: DFont
    font_after: DFont
    scale_upms:
        Scale values in relation to the font's upms. See readme
        for example.

    Returns
    -------
    dict
        {
            "modified": [diff_table]
        }
    """
    attribs_before = font_before.attribs
    attribs_after = font_after.attribs

    upm_before = font_before.ttfont['head'].unitsPerEm
    upm_after = font_after.ttfont['head'].unitsPerEm

    attribs_before_h = {i['attrib']: i for i in attribs_before}
    attribs_after_h = {i['attrib']: i for i in attribs_after}

    modified = _modified_attribs(attribs_before_h, attribs_after_h,
                                 upm_before, upm_after, scale_upm=scale_upm)
    modified = DiffTable("attribs modified", font_before, font_after, data=modified)
    modified.report_columns(["table", "attrib", "value_a", "value_b"])
    modified.sort(key=lambda k: k["table"])
    return {'modified': modified}


def _modified_attribs(attribs_before, attribs_after,
        upm_before=None, upm_after=None, scale_upm=False):

    shared = set(attribs_before.keys()) & set(attribs_after.keys())

    table = []
    for k in shared:
        if scale_upm and upm_before and upm_after:
            # If a font's upm changes the following attribs are not affected
            keep = (
                'modified',
                'usBreakChar',
                'ulUnicodeRange2',
                'ulUnicodeRange1',
                'tableVersion',
                'usLastCharIndex',
                'ulCodePageRange1',
                'version',
                'usMaxContex',
                'usWidthClass',
                'fsSelection',
                'caretSlopeRise',
                'usMaxContext',
                'fontRevision',
                'yStrikeoutSize',
                'usWeightClass',
                'unitsPerEm',
                'fsType',
            )
            if attribs_before[k]['attrib'] not in keep and \
               isinstance(attribs_before[k]['value'], (int, float)):
                attribs_before[k]['value'] = round((attribs_before[k]['value'] / float(upm_before)) * upm_after)
                attribs_after[k]['value'] = round((attribs_after[k]['value'] / float(upm_after)) * upm_after)

        if attribs_before[k]['value'] != attribs_after[k]['value']:
            table.append({
                "attrib": attribs_before[k]['attrib'],
                "table": attribs_before[k]['table'],
                "value_a": attribs_before[k]['value'],
                "value_b": attribs_after[k]['value']
            })
    return table


@timer
def diff_marks(font_before, font_after, marks_before, marks_after,
               name=None, thresh=4, scale_upms=True):
    """diff mark positioning.

    Marks are flattened first.

    Rows are matched by each base glyph's + mark glyph's key

    Parameters
    ----------
    font_before: DFont
    font_after: DFont
    marks_before: diff_table
    marks_after: diff_table
    thresh: Ignore differences below this value
    scale_upms:
        Scale values in relation to the font's upms. See readme
        for example.

    Returns
    -------
    dict
        {
            "new": [diff_table],
            "missing": [diff_table],
            "modified": [diff_table]
        }
    """
    upm_before = font_before.ttfont['head'].unitsPerEm
    upm_after = font_after.ttfont['head'].unitsPerEm

    charset_before = set([font_before.glyph(g).key for g in font_before.glyphset])
    charset_after = set([font_after.glyph(g).key for g in font_after.glyphset])

    marks_before_h = {i['base_glyph'].key+i['mark_glyph'].key: i for i in marks_before
                 if i['base_glyph'].key in charset_after and i['mark_glyph'].key in charset_after}
    marks_after_h = {i['base_glyph'].key+i['mark_glyph'].key: i for i in marks_after
                 if i['base_glyph'].key in charset_before and i['mark_glyph'].key in charset_before}

    missing = _subtract_items(marks_before_h, marks_after_h)
    new = _subtract_items(marks_after_h, marks_before_h)
    modified = _modified_marks(marks_before_h, marks_after_h, thresh,
                               upm_before, upm_after, scale_upms=True)

    new = DiffTable(name + "_new", font_before, font_after, data=new, renderable=True)
    new.report_columns(["base_glyph", "base_x", "base_y",
                        "mark_glyph", "mark_x", "mark_y"])
    new.sort(key=lambda k: abs(k["base_x"]) - abs(k["mark_x"]) + \
                           abs(k["base_y"]) - abs(k["mark_y"]))

    missing = DiffTable(name + "_missing", font_before, font_after, data=missing,
                        renderable=True)
    missing.report_columns(["base_glyph", "base_x", "base_y",
                            "mark_glyph", "mark_x", "mark_y"])
    missing.sort(key=lambda k: abs(k["base_x"]) - abs(k["mark_x"]) + \
                               abs(k["base_y"]) - abs(k["mark_y"]))
    modified = DiffTable(name + "_modified", font_before, font_after, data=modified,
                         renderable=True)
    modified.report_columns(["base_glyph", "mark_glyph", "diff_x", "diff_y"])
    modified.sort(key=lambda k: abs(k["diff_x"]) + abs(k["diff_y"]), reverse=True)
    return {
        "new": new,
        "missing": missing,
        "modified": modified,
    }


def _modified_marks(marks_before, marks_after, thresh=4,
        upm_before=None, upm_after=None, scale_upms=True):

    marks = ['base_x', 'base_y', 'mark_x', 'mark_y']

    shared = set(marks_before.keys()) & set(marks_after.keys())

    table = []
    for k in shared:
        if scale_upms and upm_before and upm_after:
            for mark in marks:
                marks_after[k][mark] = (marks_after[k][mark] / float(upm_before)) * upm_before
                marks_after[k][mark] = (marks_after[k][mark] / float(upm_after)) * upm_before
        offset_before_x = marks_before[k]['base_x'] - marks_before[k]['mark_x']
        offset_before_y = marks_before[k]['base_y'] - marks_before[k]['mark_y']
        offset_after_x = marks_after[k]['base_x'] - marks_after[k]['mark_x']
        offset_after_y = marks_after[k]['base_y'] - marks_after[k]['mark_y']

        diff_x = offset_after_x - offset_before_x
        diff_y = offset_after_y - offset_before_y

        if abs(diff_x) > thresh or abs(diff_y) > thresh:
            mark = marks_before[k]
            mark['diff_x'] = diff_x
            mark['diff_y'] = diff_y
            for pos in ['base_x', 'base_y', 'mark_x', 'mark_y']:
                mark.pop(pos)
            table.append(mark)
    return table


@timer
def diff_cbdt_glyphs(font_before, font_after, thresh=4, render_path=None, html_output=False):
    cbdt_before = read_cbdt(font_before.ttfont)
    cbdt_after = read_cbdt(font_after.ttfont)

    chars_before = {r["string"]: str(r["glyph"]) for r in font_before.glyphs}
    chars_after = {r["string"]: str(r["glyph"]) for r in font_after.glyphs}

    modified = []
    for char in set(chars_before) & set(chars_after):
        glyph_name_before = chars_before[char]
        glyph_name_after = chars_after[char]
        if glyph_name_before in cbdt_before and glyph_name_after in cbdt_after:
            diff = _diff_images(cbdt_before[glyph_name_before], cbdt_after[glyph_name_after])
            if diff > thresh:
                modified.append({
                    "glyph before": glyph_name_before,
                    "glyph after": glyph_name_after,
                    "string": char,
                    "diff": diff,
                    "image": f"<img src='{render_path}/{glyph_name_before}.gif'>",
                })

    modified = DiffTable("cbdt glyphs modified", font_before, font_after, data=modified, renderable=True)
    if render_path and html_output:
        modified.report_columns(["glyph before", "glyph after", "diff", "string", "image"])
    else:
        modified.report_columns(["glyph before", "glyph after", "diff", "string"])
    modified.sort(key=lambda k: abs(k["diff"]), reverse=True)

    return {
        "modified": modified
    }


@timer
def diff_gdef_base(font_before, font_after):
    """Diff gdef base glyphs"""
    tables = _gdef(font_before, font_after, "gdef_base")
    return tables


@timer
def diff_gdef_mark(font_before, font_after):
    """Diff gdef mark glyphs"""
    return _gdef(font_before, font_after, "gdef_mark")


def _gdef(font_before, font_after, type_):
    base_before = getattr(font_before, type_)
    base_after = getattr(font_after, type_)

    base_before_h = {i['glyph'].key: i for i in base_before}
    base_after_h = {i['glyph'].key: i for i in base_after}

    missing = _subtract_items(base_before_h, base_after_h)
    new = _subtract_items(base_after_h, base_before_h)
    new = DiffTable(f"{type_} new", font_before, font_after, data=new, renderable=True)
    new.report_columns(["glyph"])
    new.sort(key=lambda k: k["glyph"].width, reverse=True)
    missing = DiffTable(f"{type_} missing", font_before, font_after, data=missing, renderable=True)
    missing.report_columns(["glyph"])
    missing.sort(key=lambda k: k["glyph"].width, reverse=True)
    return {
        "new": new,
        "missing": missing,
    }
