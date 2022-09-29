from diffenator import DFontTable, DFontTableIMG
from fontTools.pens.areaPen import AreaPen
import datetime
import logging

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger('fontdiffenator')


def dump_nametable(font):
    """Dump a font's nametable

    Parameters
    ----------
    font: DFont

    Returns
    -------
    DFontTable
        Each row in the table is represented as a dict.
        [
            {'id': (1, 3, 1, 1033), 'string': 'Noto Sans'},
            {'id': (2, 3, 1, 1033), 'string': 'Regular'},
            ...
        ]
    """
    table = DFontTable(font, "names")
    name_table = font.ttfont['name']

    for name in name_table.names:
        table.append({
            'string': name.toUnicode(),
            'id': (name.nameID, name.platformID, name.platEncID, name.langID)
        })
    table.report_columns(["id", "string"])
    return table



def _panose(panose):
    return '{}-{}-{}-{}-{}-{}-{}-{}-{}-{}'.format(
        panose.bFamilyType,
        panose.bSerifStyle,
        panose.bWeight,
        panose.bProportion,
        panose.bContrast,
        panose.bStrokeVariation,
        panose.bArmStyle,
        panose.bLetterForm,
        panose.bMidline,
        panose.bXHeight
        )


def _timestamp(epoch):
    """fontTool's epoch origin is 1904, not 1970.

    days between datetime(1970,1,1,1) - datetime(1904,1,1,1) = 24107

    https://github.com/fonttools/fonttools/issues/99"""
    d = datetime.datetime.fromtimestamp(epoch) - datetime.timedelta(days=24107)
    return d.strftime('%Y/%m/%d %H:%M:%S')


OS2 = [
    # 'fsFirstCharIndex',
    # 'fsLastCharIndex',
    ('fsSelection', int),
    ('fsType', int),
    ('panose', _panose),
    ('sCapHeight', int),
    ('sFamilyClass', int),
    ('sTypoAscender', int),
    ('sTypoDescender', int),
    ('sTypoLineGap', int),
    ('sxHeight', int),
    ('ulCodePageRange1', int),
    ('ulCodePageRange2', int),
    ('ulUnicodeRange1', int),
    ('ulUnicodeRange2', int),
    ('ulUnicodeRange3', int),
    ('ulUnicodeRange4', int),
    ('usBreakChar', int),
    ('usDefaultChar', int),
#    ('usFirstCharIndex', int),
#    ('usLastCharIndex', int),
#    ('usMaxContex', int),
#    ('usMaxContext', int),
    ('usWeightClass', int),
    ('usWidthClass', int),
    ('usWinAscent', int),
    ('usWinDescent', int),
    ('version', int),
    # 'xAvgCharWidth', int),
    ('yStrikeoutPosition', int),
    ('yStrikeoutSize', int),
    ('ySubscriptXOffset', int),
    ('ySubscriptXSize', int),
    ('ySubscriptYOffset', int),
    ('ySubscriptYSize', int),
    ('ySuperscriptXOffset', int),
    ('ySuperscriptXSize', int),
    ('ySuperscriptYOffset', int),
    ('ySuperscriptYSize', int)
]

HHEA = [
    # ('advanceWidthMax', int),
    ('ascent', int),
    ('caretOffset', int),
    ('caretSlopeRise', int),
    ('caretSlopeRun', int),
    ('descent', int),
    ('lineGap', int),
    # ('metricDataFormat', int),
    # ('minLeftSideBearing', int),
    # ('minRightSideBearing', int),
    # ('numberOfHMetrics', int),
    ('reserved0', int),
    ('reserved1', int),
    ('reserved2', int),
    ('reserved3', int),
    # ('tableTag', int),
    ('tableVersion', int),
]

GASP = [
    ('gaspRange', dict),
    ('version', int),
]

HEAD = [
    # ('checkSumAdjustment', int),
    ('fontRevision', float),
    # ('glyphDataFormat', int),
    ('macStyle', int),
    # ('magicNumber', int),
    ('modified', _timestamp),
    # ('tableTag', int),
    ('tableVersion', int),
    ('unitsPerEm', int),
    ('xMax', int),
    ('xMin', int),
    ('yMax', int),
    ('yMin', int),
]

POST = [
    ('isFixedPitch', int),
    ('italicAngle', float),
    ('underlinePosition', int),
    ('underlineThickness', int),
]


def dump_attribs(font):
    """""Dump a font's attribs

    Parameters
    ----------
    font: DFont

    Returns
    -------
    DFontTable
        Each row in the table is represented as a dict.
        [
            {'table': 'OS/2', 'attrib': 'fsSelection': 'value': 128},
            {'table': 'hhea', 'attrib': 'ascender', 'value': 1100}
            ...
        ]
    """
    attribs = DFontTable(font, "attribs")
    for table_tag, font_table in zip(['OS/2', 'hhea', 'gasp', 'head', 'post'],
                                     [OS2, HHEA, GASP, HEAD, POST]):
        if table_tag in font.ttfont:
            for attr, converter in font_table:
                try:
                    row = {
                        'attrib': attr,
                        'value': converter(getattr(font.ttfont[table_tag], attr)),
                        'table': table_tag
                    }
                    attribs.append(row)
                except AttributeError:
                    logger.info("{} Missing attrib {}".format(table_tag, attr))
    attribs.report_columns(["table", "attrib", "value"])
    return attribs


def glyph_area(glyphset, glyph):
    """Get the surface area of a glyph"""
    pen = AreaPen(glyphset)
    glyphset[glyph].draw(pen)
    return int(pen.value)


def dump_glyphs(font):
    """Dump info for each glyph in a font

    Parameters
    ----------
    font: DFont

    Returns
    -------
    DFontTableIMG
    Each row in the table is represented as a dict.
        [
            {'glyph': A, 'area': 1000, string': 'A',
             'description': "A | ()", 'features': []},
            {'glyph': B, 'area': 1100, string': 'B',
             'description': "B | ()", 'features': []},
            ...
        ]
    """
    glyphset = font.ttfont.getGlyphSet()
    table = DFontTableIMG(font, "glyphs", renderable=True)
    for name, glyph in sorted(font.glyphset.items()):
        table.append({
            "glyph": glyph,
            "area": glyph_area(glyphset, name),
            "string": glyph.characters,
            'features': glyph.features,
            'htmlfeatures': u', '.join(glyph.features)
        })
    table.report_columns(["glyph", "area", "string"])
    table.sort(key=lambda k: k["glyph"].characters)
    return table


def dump_glyph_metrics(font):
    """Dump the metrics for each glyph in a font

    Parameters
    ----------
    font: DFont

    Returns
    -------
    DFontTableIMG
    Each row in the table is represented as a dict.
        [
            {'glyph': A, 'lsb': 50, 'rsb': 50, 'adv': 200,
             'string': 'A', 'description': "A | ()"},
            {'glyph': B, 'lsb': 80, 'rsb': 50, 'adv': 230,
             'string': 'B', 'description': "B | ()"},
            ...
        ]
    """
    table = DFontTableIMG(font, "metrics", renderable=True)

    glyphset = font.ttfont.getGlyphSet()
    for name, glyph in font.glyphset.items():
        adv = font.ttfont["hmtx"][name][0]
        if "glyf" in font.ttfont.keys():
            try:
                lsb = font.ttfont["glyf"][name].xMin
                rsb = adv - font.ttfont['glyf'][name].xMax
            except AttributeError:
                lsb = 0
                rsb = 0
        elif "CFF " in font.ttfont.keys():
            try:
                bounds = font.ttfont["CFF "].cff.values()[0].CharStrings[name].calcBounds(glyphset)
                lsb = bounds[0]
                rsb = adv - bounds[-2]
            except TypeError:
                lsb = 0
                rsb = 0
        else:
            raise Exception("Only ttf and otf fonts are supported")
        table.append({'glyph': glyph,
                'lsb': lsb, 'rsb': rsb, 'adv': adv,
                'string': glyph.characters,
                'description': u'{} | {}'.format(
                    glyph.name, glyph.features
                ),
                'features': glyph.features,
                'htmlfeatures': u', '.join(glyph.features)})
    table.report_columns(["glyph", "rsb", "lsb", "adv"])
    return table


def _kerning_lookup_indexes(font):
    """Return the lookup ids for the kern feature"""
    for feat in font['GPOS'].table.FeatureList.FeatureRecord:
        if feat.FeatureTag == 'kern':
            return feat.Feature.LookupListIndex
    return None


def _flatten_pair_kerning(table, results):
    """Flatten pair on pair kerning"""
    seen = set(results)
    first_glyphs = {idx: g for idx, g in enumerate(table.Coverage.glyphs)}

    for idx, pairset in enumerate(table.PairSet):
        first_glyph = first_glyphs[idx]

        for record in pairset.PairValueRecord:

            if not hasattr(record.Value1, "XAdvance"):
                continue
            kern = (first_glyph, record.SecondGlyph, record.Value1.XAdvance)

            if kern not in seen:
                results.append(kern)
                seen.add(kern)


def _flatten_class_kerning(table, results):
    """Flatten class on class kerning"""
    seen = set(results)
    classes1 = _kern_class(table.ClassDef1.classDefs, table.Coverage.glyphs)
    classes2 = _kern_class(table.ClassDef2.classDefs, table.Coverage.glyphs)

    for idx1, class1 in enumerate(table.Class1Record):
        for idx2, class2 in enumerate(class1.Class2Record):

            if idx1 not in classes1:
                continue
            if idx2 not in classes2:
                continue

            if not hasattr(class2.Value1, 'XAdvance'):
                continue
            if abs(class2.Value1.XAdvance) > 0:
                for glyph1 in classes1[idx1]:
                    for glyph2 in classes2[idx2]:

                        kern = (glyph1, glyph2, class2.Value1.XAdvance)
                        if kern not in seen:
                            results.append(kern)
                            seen.add(kern)


def _kern_class(class_definition, coverage_glyphs):
    """Transpose a ttx classDef

    {glyph_name: idx, glyph_name: idx} --> {idx: [glyph_name, glyph_name]}

    Classdef 0 is not defined in the font. It is created by subtracting
    the glyphs found in the lookup coverage against all the glyphs used to
    define the other classes."""
    classes = {}
    seen_glyphs = set()
    for glyph, idx in class_definition.items():
        if idx not in classes:
            classes[idx] = []
        classes[idx].append(glyph)
        seen_glyphs.add(glyph)

    classes[0] = set(coverage_glyphs) - seen_glyphs
    return classes


def dump_kerning(font):
    """Dump a font's kerning.

    If no GPOS kerns exist, try and dump the kern table instead

    Parameters
    ----------
    font: DFont

    Returns
    -------
    DFontTableIMG
        Each row in the table is represented as a dict.
        [
            {'left': A, 'right': V, 'value': -50,
             'string': 'AV', 'description': "AV | ()", 'features': []},
            {'left': V, 'right': A, 'value': -50,
             'string': 'VA', 'description': "VA | ()", 'features': []},
            ...
        ]
    """
    kerning = _dump_gpos_kerning(font)
    if not kerning:
        kerning = _dump_table_kerning(font)
    return kerning


def _dump_gpos_kerning(font):
    """Dump a font's GPOS kerning.

    TODO (Marc Foley) Flattening produced too much output. Perhaps it's better
    to keep the classes and map each class to a single glyph?

    Perhaps it would be better to combine our efforts and help improve
    https://github.com/adobe-type-tools/kern-dump which has similar
    functionality?"""
    if 'GPOS' not in font.ttfont:
        logger.warning("Font doesn't have GPOS table. No kerns found")
        return []

    kerning_lookup_indexes = _kerning_lookup_indexes(font.ttfont)
    if not kerning_lookup_indexes:
        logger.warning("Font doesn't have a GPOS kern feature")
        return []

    kern_table = []
    for lookup_idx in kerning_lookup_indexes:
        lookup = font.ttfont['GPOS'].table.LookupList.Lookup[lookup_idx]

        for sub_table in lookup.SubTable:

            if hasattr(sub_table, 'ExtSubTable'):
                sub_table = sub_table.ExtSubTable

            if hasattr(sub_table, 'PairSet'):
                _flatten_pair_kerning(sub_table, kern_table)

            if hasattr(sub_table, 'ClassDef2'):
                _flatten_class_kerning(sub_table, kern_table)

    _kern_table = DFontTableIMG(font, "kerning", renderable=True)
    for left, right, val in kern_table:
        left = font.glyph(left)
        right = font.glyph(right)
        _kern_table.append({
            'left': left,
            'right': right,
            'value': val,
            'string': left.characters + right.characters,
            'description': u'{}+{} | {}'.format(
                left.name,
                right.name,
                left.features),
            "features": left.features + right.features,
            'htmlfeatures': u'{}, {}'.format(
                ', '.join(left.features),
                ', '.join(right.features))
        })
    _kern_table.report_columns(["left", "right", "string", "value"])
    return _kern_table


def _dump_table_kerning(font):
    """Some fonts still contain kern tables. Most modern fonts include
    kerning in the GPOS table"""
    kerns = DFontTableIMG(font, "kerns", renderable=True)
    if not 'kern' in font.ttfont:
        return kerns
    logger.warn('Font contains kern table. Newer fonts are GPOS only')
    for table in font.ttfont['kern'].kernTables:
        for kern in table.kernTable:
            left = font.glyph(kern[0])
            right = font.glyph(kern[1])
            kerns.append({
                'left': left,
                'right': right,
                'value': table.kernTable[kern],
                'string': left.characters + right.characters,
                'description': u'{}+{} | {}'.format(
                    left.name,
                    right.name,
                    left.features),
                'features': left.features + right.features,
                'htmlfeatures': u'{}, {}'.format(
                    ', '.join(left.features),
                    ', '.join(right.features)
                )
            })
    return kerns


class DumpAnchors:
    """Dump a font's mark and mkmks positions"""
    def __init__(self, font):
        self._font = font
        self.ttfont = font.ttfont
        self._lookups = self._get_lookups() if 'GPOS' in self.ttfont.keys() else []

        self._base = []
        self._marks = []

        self._mark1 = []
        self._mark2 = []
        self._get_groups()

        self._marks_table = self._gen_table("marks", self._base, self._marks,
                                            anc2_is_combining=True)
        self._mkmks_table = self._gen_table("mkmks", self._mark1, self._mark2,
                                           anc1_is_combining=True,
                                           anc2_is_combining=True)

    @property
    def base_groups(self):
        return self._base

    @property
    def mark_groups(self):
        return self._marks

    @property
    def marks_table(self):
        return self._marks_table

    @property
    def mkmks_table(self):
        return self._mkmks_table

    def _get_lookups(self):
        """Return the lookups used for the mark and mkmk feature"""
        gpos = self.ttfont['GPOS']
        lookups = []
        lookup_idxs = []
        for feat in gpos.table.FeatureList.FeatureRecord:
            if feat.FeatureTag in ['mark', 'mkmk']:
                lookup_idxs += feat.Feature.LookupListIndex

        for idx in lookup_idxs:
            lookups.append(gpos.table.LookupList.Lookup[idx])
        if len(lookups) == 0:
            logger.warn("Font has no mark positioned glyphs")
        return lookups

    def _get_groups(self):
        for lookup in self._lookups:
            for sub_table in lookup.SubTable:

                if hasattr(sub_table, 'ExtSubTable'):
                    sub_table = sub_table.ExtSubTable

                # get mark marks
                if sub_table.Format == 1 and sub_table.LookupType == 4:
                    base_lookup_anchors = self._get_base_anchors(
                        sub_table.BaseCoverage.glyphs,
                        sub_table.BaseArray.BaseRecord,
                    )
                    mark_lookup_anchors = self._get_mark_anchors(
                        sub_table.MarkCoverage.glyphs,
                        sub_table.MarkArray.MarkRecord
                    )
                    self._base.append(base_lookup_anchors)
                    self._marks.append(mark_lookup_anchors)

                # get mkmk marks
                if sub_table.Format == 1 and sub_table.LookupType == 6:
                    mark1_lookup_anchors = self._get_mark_anchors(
                        sub_table.Mark1Coverage.glyphs,
                        sub_table.Mark1Array.MarkRecord
                    )
                    mark2_lookup_anchors = self._get_base_anchors(
                        sub_table.Mark2Coverage.glyphs,
                        sub_table.Mark2Array.Mark2Record,
                        anc_type='Mark2Anchor'
                    )
                    self._mark1.append(mark1_lookup_anchors)
                    self._mark2.append(mark2_lookup_anchors)

    def _get_base_anchors(self, glyph_list, anchors_list,
                          anc_type='BaseAnchor'):
        """
        rtype:
        {0: [{'class': 0, 'glyph': 'A', 'x': 199, 'y': 0}],
        {1: [{'class': 0, 'glyph': 'C', 'x': 131, 'y': 74}],
         """
        _anchors = {}
        for glyph, anchors in zip(glyph_list, anchors_list):
            anchors = getattr(anchors, anc_type)
            for idx, anchor in enumerate(anchors):
                if not anchor:  # TODO (M Foley) investigate why fonttools adds Nonetypes
                    continue

                if idx not in _anchors:
                    _anchors[idx] = []
                _anchors[idx].append({
                    'class': idx,
                    'glyph': self._font.glyph(glyph),
                    'x': anchor.XCoordinate,
                    'y': anchor.YCoordinate
                })
        return _anchors

    def _get_mark_anchors(self, glyph_list, anchors_list):
        """
        rtype:
        {0: [{'class': 0, 'glyph': 'uni0300', 'x': 199, 'y': 0}],
        {1: [{'class': 0, 'glyph': 'uni0301', 'x': 131, 'y': 74}],
         """
        _anchors = {}
        for glyph, anchor in zip(glyph_list, anchors_list):
            if not anchor:  # TODO (M Foley) investigate why fonttools adds Nonetypes
                continue

            if anchor.Class not in _anchors:
                _anchors[anchor.Class] = []
            _anchors[anchor.Class].append({
                'glyph': self._font.glyph(glyph),
                'class': anchor.Class,
                'x': anchor.MarkAnchor.XCoordinate,
                'y': anchor.MarkAnchor.YCoordinate
            })
        return _anchors

    def _gen_table(self, name, anchors1, anchors2,
                   anc1_is_combining=False, anc2_is_combining=False):
        """Return a flattened table consisting of mark1_glyphs with their
        attached mark2_glyphs.

        Returns
        -------
        dump_table: list
        [
            {'mark1_glyph': 'a', 'base_x': 300, 'base_y': 450,
             'mark2_glyph': 'acutecomb', 'mark_x': 0, 'mark_y': 550},
            {'mark1_glyph': 'a', 'base_x': 300, 'base_y': 450,
             'mark2_glyph': 'gravecomb', 'mark_x': 0, 'mark_y': 550},
        ]
        """
        table = DFontTableIMG(self._font, name, renderable=True)
        for l_idx in range(len(anchors1)):
            for m_group in anchors1[l_idx]:
                for anchor in anchors1[l_idx][m_group]:
                    if anc1_is_combining and not anchor['glyph'].combining:
                        continue
                    if m_group not in anchors2[l_idx]:
                        continue
                    for anchor2 in anchors2[l_idx][m_group]:
                        if anc2_is_combining and not anchor2['glyph'].combining:
                            continue
                        table.append({
                            'base_glyph': anchor['glyph'],
                            'base_x': anchor['x'],
                            'base_y': anchor['y'],
                            'mark_glyph': anchor2['glyph'],
                            'mark_x': anchor2['x'],
                            'mark_y': anchor2['y'],
                            'string': anchor['glyph'].characters + \
                                      anchor2['glyph'].characters,
                            'description': u'{} + {} | {}'.format(
                                anchor['glyph'].name,
                                anchor2['glyph'].name,
                                anchor['glyph'].features
                            ),
                            'features': anchor['glyph'].features + \
                                        anchor['glyph'].features,
                            'htmlfeatures': u'{}, {}'.format(
                                ', '.join(anchor['glyph'].features),
                                ', '.join(anchor2['glyph'].features)
                            )
                        })
        table.report_columns(["base_glyph", "base_x", "base_y",
                              "mark_glyph", "mark_x", "mark_y"])
        return table


GDEF_CLASSES = {1: "base", 2: "ligature", 3: "mark", 4: "component_glyph"}


def dump_gdef(font):
    """Dump a font's GDEF table. Function will return two tables, one for
    base glyphs, the other for mark glyphs."""
    table_base = DFontTableIMG(font, "gdef_base", renderable=True)
    table_mark = DFontTableIMG(font, "gdef_mark", renderable=True)
    if "GDEF" not in font.ttfont:
        return (table_base, table_mark)
    if not font.ttfont['GDEF'].table.GlyphClassDef:
        return (table_base, table_mark)
    gdef_classes = font.ttfont['GDEF'].table.GlyphClassDef.classDefs
    for glyph_name, class_ in gdef_classes.items():
        glyph = font.glyph(glyph_name)
        if class_ == 1:
            table_base.append({
                "glyph": glyph,
                "class": GDEF_CLASSES[class_],
                "string": glyph.characters,
                'features': glyph.features,
            })
        elif class_ == 3:
            table_mark.append({
                "glyph": glyph,
                "class": GDEF_CLASSES[class_],
                "string": glyph.characters,
                'features': glyph.features,
            })
    for tbl in (table_base, table_mark):
        tbl.report_columns(["glyph", "class"])
        tbl.sort(key=lambda k: k["class"])
    return (table_base, table_mark)


# TODO dump GDEF.LigCaretList
