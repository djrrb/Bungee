# Copyright 2016 Georg Seifert. All Rights Reserved.
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


import copy
import logging
import math
import os
import re
import uuid
from collections import OrderedDict
from io import StringIO
from typing import Any, Dict, Optional, Tuple, Union

import openstep_plist

from fontTools.pens.basePen import AbstractPen
from fontTools.pens.pointPen import (
    AbstractPointPen,
    PointToSegmentPen,
    SegmentToPointPen,
)

from glyphsLib.affine import Affine
from glyphsLib.parser import Parser
from glyphsLib.types import (
    Point,
    Rect,
    Transform,
    UnicodesList,
    floatToString5,
    parse_datetime,
    parse_float_or_int,
    readIntlist,
)
from glyphsLib.writer import Writer

logger = logging.getLogger(__name__)

__all__ = [
    "Glyphs",
    "GSFont",
    "GSFontMaster",
    "GSAlignmentZone",
    "GSInstance",
    "GSCustomParameter",
    "GSClass",
    "GSFeaturePrefix",
    "GSFeature",
    "GSGlyph",
    "GSLayer",
    "GSAnchor",
    "GSComponent",
    "GSSmartComponentAxis",
    "GSPath",
    "GSNode",
    "GSGuide",
    "GSAnnotation",
    "GSHint",
    "GSBackgroundImage",
    # Constants
    "__all__",
    "MOVE",
    "LINE",
    "CURVE",
    "QCURVE",
    "OFFCURVE",
    "GSMOVE",
    "GSLINE",
    "GSCURVE",
    "GSOFFCURVE",
    "GSSHARP",
    "GSSMOOTH",
    "TAG",
    "TOPGHOST",
    "STEM",
    "BOTTOMGHOST",
    "TTANCHOR",
    "TTSTEM",
    "TTALIGN",
    "TTINTERPOLATE",
    "TTDIAGONAL",
    "TTDELTA",
    "CORNER",
    "CAP",
    "TTDONTROUND",
    "TTROUND",
    "TTROUNDUP",
    "TTROUNDDOWN",
    "TRIPLE",
    "TEXT",
    "ARROW",
    "CIRCLE",
    "PLUS",
    "MINUS",
    "LTR",
    "RTL",
    "LTRTTB",
    "RTLTTB",
    "GSTopLeft",
    "GSTopCenter",
    "GSTopRight",
    "GSCenterLeft",
    "GSCenterCenter",
    "GSCenterRight",
    "GSBottomLeft",
    "GSBottomCenter",
    "GSBottomRight",
    "WEIGHT_CODES",
    "WIDTH_CODES",
]

# CONSTANTS
GSMOVE_ = 17
GSLINE_ = 1
GSCURVE_ = 35
GSOFFCURVE_ = 65
GSSHARP = 0
GSSMOOTH = 100

GSMOVE = "move"
GSLINE = "line"
GSCURVE = "curve"
GSQCURVE = "qcurve"
GSOFFCURVE = "offcurve"

MOVE = "move"
LINE = "line"
CURVE = "curve"
OFFCURVE = "offcurve"
QCURVE = "qcurve"

TAG = -2
TOPGHOST = -1
STEM = 0
BOTTOMGHOST = 1
TTANCHOR = 2
TTSTEM = 3
TTALIGN = 4
TTINTERPOLATE = 5
TTDIAGONAL = 6
TTDELTA = 7
CORNER = 16
CAP = 17

TTDONTROUND = 4
TTROUND = 0
TTROUNDUP = 1
TTROUNDDOWN = 2
TRIPLE = 128

# Annotations:
TEXT = 1
ARROW = 2
CIRCLE = 3
PLUS = 4
MINUS = 5

# Directions:
LTR = 0  # Left To Right (e.g. Latin)
RTL = 1  # Right To Left (e.g. Arabic, Hebrew)
LTRTTB = 3  # Left To Right, Top To Bottom
RTLTTB = 2  # Right To Left, Top To Bottom

# Reverse lookup for __repr__
hintConstants = {
    -2: "Tag",
    -1: "TopGhost",
    0: "Stem",
    1: "BottomGhost",
    2: "TTAnchor",
    3: "TTStem",
    4: "TTAlign",
    5: "TTInterpolate",
    6: "TTDiagonal",
    7: "TTDelta",
    16: "Corner",
    17: "Cap",
}

GSTopLeft = 6
GSTopCenter = 7
GSTopRight = 8
GSCenterLeft = 3
GSCenterCenter = 4
GSCenterRight = 5
GSBottomLeft = 0
GSBottomCenter = 1
GSBottomRight = 2

# Writing direction
LTR = 0
RTL = 1
LTRTTB = 3
RTLTTB = 2


WEIGHT_CODES = {
    "Thin": 100,
    "ExtraLight": 200,
    "UltraLight": 200,
    "Light": 300,
    None: 400,  # default value normally omitted in source
    "Normal": 400,
    "Regular": 400,
    "Medium": 500,
    "DemiBold": 600,
    "SemiBold": 600,
    "Bold": 700,
    "UltraBold": 800,
    "ExtraBold": 800,
    "Black": 900,
    "Heavy": 900,
}

WIDTH_CODES = {
    "Ultra Condensed": 1,
    "Extra Condensed": 2,
    "Condensed": 3,
    "SemiCondensed": 4,
    None: 5,  # default value normally omitted in source
    "Medium (normal)": 5,
    "Semi Expanded": 6,
    "Expanded": 7,
    "Extra Expanded": 8,
    "Ultra Expanded": 9,
}


class OnlyInGlyphsAppError(NotImplementedError):
    def __init__(self):
        NotImplementedError.__init__(
            self,
            "This property/method is only available in the real UI-based "
            "version of Glyphs.app.",
        )


def parse_hint_target(line=None):
    if line is None:
        return None
    if line[0] == "{":
        return Point(line)
    else:
        return line


def transformStructToScaleAndRotation(transform):
    Det = transform[0] * transform[3] - transform[1] * transform[2]
    _sX = math.sqrt(math.pow(transform[0], 2) + math.pow(transform[1], 2))
    _sY = math.sqrt(math.pow(transform[2], 2) + math.pow(transform[3], 2))
    if Det < 0:
        _sY = -_sY
    _R = math.atan2(transform[1] * _sY, transform[0] * _sX) * 180 / math.pi

    if Det < 0 and (math.fabs(_R) > 135 or _R < -90):
        _sX = -_sX
        _sY = -_sY
        if _R < 0:
            _R += 180
        else:
            _R -= 180

    quadrant = 0
    if _R < -90:
        quadrant = 180
        _R += quadrant
    if _R > 90:
        quadrant = -180
        _R += quadrant
    _R = _R * _sX / _sY
    _R -= quadrant
    if _R < -179:
        _R += 360

    return _sX, _sY, _R


class GSApplication:
    __slots__ = "font", "fonts"

    def __init__(self):
        self.font = None
        self.fonts = []

    def open(self, path):
        newFont = GSFont(path)
        self.fonts.append(newFont)
        self.font = newFont
        return newFont

    def __repr__(self):
        return "<glyphsLib>"


Glyphs = GSApplication()


class GSBase:
    """Represent the base class for all GS classes.

    Attributes:
        _defaultsForName (dict): Used to determine which values to serialize and which
            to imply by their absence.
    """

    _defaultsForName = {}

    def __repr__(self):
        content = ""
        if hasattr(self, "_dict"):
            content = str(self._dict)
        return f"<{self.__class__.__name__} {content}>"

    # Note:
    # The dictionary API exposed by GS* classes is "private" in the sense that:
    #  * it should only be used by the parser, so it should only
    #    work for key names that are found in the files
    #  * and only for filling data in the objects, which is why it only
    #    implements `__setitem__`
    #
    # Users of the library should only rely on the object-oriented API that is
    # documented at https://docu.glyphsapp.com/
    def __setitem__(self, key, value):
        setattr(self, key, value)

    @classmethod
    def _add_parsers(cls, specification):
        for field in specification:
            keyname = field["plist_name"]
            dict_parser_name = "_parse_%s_dict" % keyname
            target = field.get("object_name", keyname)
            classname = field.get("type")
            transformer = field.get("converter")

            def _generic_parser(
                self,
                parser,
                value,
                keyname=keyname,
                target=target,
                classname=classname,
                transformer=transformer,
            ):
                if transformer:
                    if isinstance(value, list) and transformer != Point:
                        self[target] = [transformer(v) for v in value]
                    else:
                        self[target] = transformer(value)
                else:
                    obj = parser._parse(value, classname)
                    self[target] = obj

            setattr(cls, dict_parser_name, _generic_parser)


class Proxy:
    __slots__ = "_owner"

    def __init__(self, owner):
        self._owner = owner

    def __repr__(self):
        """Return list-lookalike of representation string of objects"""
        strings = []
        for currItem in self:
            strings.append("%s" % currItem)
        return "(%s)" % (", ".join(strings))

    def __len__(self):
        values = self.values()
        if values is not None:
            return len(values)
        return 0

    def pop(self, i):
        if type(i) == int:
            node = self[i]
            del self[i]
            return node
        else:
            raise KeyError

    def __iter__(self):
        values = self.values()
        if values is not None:
            yield from values

    def index(self, value):
        return self.values().index(value)

    def __copy__(self):
        return list(self)

    def __deepcopy__(self, memo):
        return [x.copy() for x in self.values()]

    def setter(self, values):
        method = self.setterMethod()
        if type(values) == list:
            method(values)
        elif (
            type(values) == tuple
            or values.__class__.__name__ == "__NSArrayM"
            or type(values) == type(self)
        ):
            method(list(values))
        elif values is None:
            method(list())
        else:
            raise TypeError


class LayersIterator:
    __slots__ = "curInd", "_owner", "_orderedLayers"

    def __init__(self, owner):
        self.curInd = 0
        self._owner = owner
        self._orderedLayers = None

    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self._owner.parent:
            if self.curInd >= len(self._owner.layers):
                raise StopIteration
            item = self.orderedLayers[self.curInd]
        else:
            if self.curInd >= len(self._owner._layers):
                raise StopIteration
            item = self._owner._layers[self.curInd]
        self.curInd += 1
        return item

    @property
    def orderedLayers(self):
        if not self._orderedLayers:
            glyphLayerIds = [
                l.associatedMasterId
                for l in self._owner._layers.values()
                if l.associatedMasterId == l.layerId
            ]
            masterIds = [m.id for m in self._owner.parent.masters]
            intersectedLayerIds = set(glyphLayerIds) & set(masterIds)
            orderedLayers = [
                self._owner._layers[m.id]
                for m in self._owner.parent.masters
                if m.id in intersectedLayerIds
            ]
            orderedLayers += [
                self._owner._layers[l.layerId]
                for l in self._owner._layers.values()
                if l.layerId not in intersectedLayerIds
            ]
            self._orderedLayers = orderedLayers
        return self._orderedLayers


class FontFontMasterProxy(Proxy):
    """The list of masters. You can access it with the index or the master ID.
    Usage:
        Font.masters[index]
        Font.masters[id]
        for master in Font.masters:
        ...
    """

    def __getitem__(self, Key):
        if isinstance(Key, str):
            # UUIDs are case-sensitive in Glyphs.app.
            return next((master for master in self.values() if master.id == Key), None)
        if isinstance(Key, slice):
            return self.values().__getitem__(Key)
        if isinstance(Key, int):
            if Key < 0:
                Key = self.__len__() + Key
            return self.values()[Key]
        raise KeyError(Key)

    def __setitem__(self, Key, FontMaster):
        FontMaster.font = self._owner
        if isinstance(Key, int):
            OldFontMaster = self.__getitem__(Key)
            if Key < 0:
                Key = self.__len__() + Key
            FontMaster.id = OldFontMaster.id
            self._owner._masters[Key] = FontMaster
        elif isinstance(Key, str):
            OldFontMaster = self.__getitem__(Key)
            FontMaster.id = OldFontMaster.id
            Index = self._owner._masters.index(OldFontMaster)
            self._owner._masters[Index] = FontMaster
        else:
            raise KeyError

    def __delitem__(self, Key):
        if isinstance(Key, int):
            if Key < 0:
                Key = self.__len__() + Key
            return self.remove(self._owner._masters[Key])
        else:
            OldFontMaster = self.__getitem__(Key)
            return self.remove(OldFontMaster)

    def values(self):
        return self._owner._masters

    def append(self, FontMaster):
        FontMaster.font = self._owner
        # If the master to be appended has no ID yet or it's a duplicate,
        # make up a new one.
        if not FontMaster.id or self[FontMaster.id]:
            FontMaster.id = str(uuid.uuid4()).upper()
        self._owner._masters.append(FontMaster)

        # Cycle through all glyphs and append layer
        for glyph in self._owner.glyphs:
            if not glyph.layers[FontMaster.id]:
                newLayer = GSLayer()
                glyph._setupLayer(newLayer, FontMaster.id)
                glyph.layers.append(newLayer)

    def remove(self, FontMaster):

        # First remove all layers in all glyphs that reference this master
        for glyph in self._owner.glyphs:
            for layer in glyph.layers:
                if (
                    layer.associatedMasterId == FontMaster.id
                    or layer.layerId == FontMaster.id
                ):
                    glyph.layers.remove(layer)

        self._owner._masters.remove(FontMaster)

    def insert(self, Index, FontMaster):
        FontMaster.font = self._owner
        self._owner._masters.insert(Index, FontMaster)

    def extend(self, FontMasters):
        for FontMaster in FontMasters:
            self.append(FontMaster)

    def setter(self, values):
        if isinstance(values, Proxy):
            values = list(values)
        self._owner._masters = values
        for m in self._owner._masters:
            m.font = self._owner


class FontGlyphsProxy(Proxy):
    """The list of glyphs. You can access it with the index or the glyph name.
    Usage:
        Font.glyphs[index]
        Font.glyphs[name]
        for glyph in Font.glyphs:
        ...
    """

    def __getitem__(self, key):
        if type(key) == slice:
            return self.values().__getitem__(key)

        # by index
        if isinstance(key, int):
            return self._owner._glyphs[key]

        if isinstance(key, str):
            return self._get_glyph_by_string(key)

        return None

    def __setitem__(self, key, glyph):
        if isinstance(key, int):
            self._owner._setupGlyph(glyph)
            self._owner._glyphs[key] = glyph
        else:
            raise KeyError  # TODO: add other access methods

    def __delitem__(self, key):
        if isinstance(key, int):
            del self._owner._glyphs[key]
        elif isinstance(key, str):
            glyph = self._get_glyph_by_string(key)
            if not glyph:
                raise KeyError("No glyph '%s' in the font" % key)
            self._owner._glyphs.remove(glyph)
        else:
            raise KeyError

    def __contains__(self, item):
        if isinstance(item, str):
            return self._get_glyph_by_string(item) is not None
        return item in self._owner._glyphs

    def _get_glyph_by_string(self, key):
        # FIXME: (jany) looks inefficient
        if isinstance(key, str):
            # by glyph name
            for glyph in self._owner._glyphs:
                if glyph.name == key:
                    return glyph
            # by string representation as u'ä'
            if len(key) == 1:
                for glyph in self._owner._glyphs:
                    if glyph.unicode == "%04X" % (ord(key)):
                        return glyph
            # by unicode
            else:
                for glyph in self._owner._glyphs:
                    if glyph.unicode == key.upper():
                        return glyph
        return None

    def values(self):
        return self._owner._glyphs

    def items(self):
        items = []
        for value in self._owner._glyphs:
            key = value.name
            items.append((key, value))
        return items

    def append(self, glyph):
        self._owner._setupGlyph(glyph)
        self._owner._glyphs.append(glyph)

    def extend(self, objects):
        for glyph in objects:
            self._owner._setupGlyph(glyph)
        self._owner._glyphs.extend(list(objects))

    def __len__(self):
        return len(self._owner._glyphs)

    def setter(self, values):
        if isinstance(values, Proxy):
            values = list(values)
        self._owner._glyphs = values
        for g in self._owner._glyphs:
            g.parent = self._owner
            for layer in g.layers.values():
                if (
                    not hasattr(layer, "associatedMasterId")
                    or layer.associatedMasterId is None
                    or len(layer.associatedMasterId) == 0
                ):
                    g._setupLayer(layer, layer.layerId)


class FontClassesProxy(Proxy):
    VALUES_ATTR = "_classes"

    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            return self.values().__getitem__(key)
        if isinstance(key, str):
            for index, klass in enumerate(self.values()):
                if klass.name == key:
                    return self.values()[index]
        raise KeyError

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.values()[key] = value
            value._parent = self._owner
        elif isinstance(key, str):
            for index, klass in enumerate(self.values()):
                if klass.name == key:
                    self.values()[index] = value
                    value._parent = self._owner
        else:
            raise KeyError

    def __delitem__(self, key):
        if isinstance(key, int):
            del self.values()[key]
        elif isinstance(key, str):
            for index, klass in enumerate(self.values()):
                if klass.name == key:
                    del self.values()[index]

    def __contains__(self, item):
        if isinstance(item, str):
            for klass in self.values():
                if klass.name == item:
                    return True
            return False
        return item in self.values()

    def append(self, item):
        self.values().append(item)
        item._parent = self._owner

    def insert(self, key, item):
        self.values().insert(key, item)
        item._parent = self._owner

    def extend(self, items):
        self.values().extend(items)
        for value in items:
            value._parent = self._owner

    def remove(self, item):
        self.values().remove(item)

    def values(self):
        return getattr(self._owner, self.VALUES_ATTR)

    def setter(self, values):
        if isinstance(values, Proxy):
            values = list(values)
        setattr(self._owner, self.VALUES_ATTR, values)
        for value in values:
            value._parent = self._owner


class FontFeaturesProxy(FontClassesProxy):
    VALUES_ATTR = "_features"


class FontFeaturePrefixesProxy(FontClassesProxy):
    VALUES_ATTR = "_featurePrefixes"


class GlyphLayerProxy(Proxy):
    def __getitem__(self, key):
        self._ensureMasterLayers()
        if isinstance(key, slice):
            return self.values().__getitem__(key)
        elif isinstance(key, int):
            if self._owner.parent:
                return list(self)[key]
            return list(self.values())[key]
        elif isinstance(key, str):
            if key in self._owner._layers:
                return self._owner._layers[key]

    def __setitem__(self, key, layer):
        if isinstance(key, int) and self._owner.parent:
            OldLayer = self._owner._layers.values()[key]
            if key < 0:
                key = self.__len__() + key
            layer.layerId = OldLayer.layerId
            layer.associatedMasterId = OldLayer.associatedMasterId
            self._owner._setupLayer(layer, OldLayer.layerId)
            self._owner._layers[key] = layer
        elif isinstance(key, str) and self._owner.parent:
            # FIXME: (jany) more work to do?
            layer.parent = self._owner
            self._owner._layers[key] = layer
        else:
            raise KeyError

    def __delitem__(self, key):
        if isinstance(key, int) and self._owner.parent:
            if key < 0:
                key = self.__len__() + key
            Layer = self.__getitem__(key)
            key = Layer.layerId
        del self._owner._layers[key]

    def __iter__(self):
        return LayersIterator(self._owner)

    def __len__(self):
        return len(self.values())

    def keys(self):
        self._ensureMasterLayers()
        return self._owner._layers.keys()

    def values(self):
        self._ensureMasterLayers()
        return self._owner._layers.values()

    def append(self, layer):
        assert layer is not None
        self._ensureMasterLayers()
        if not layer.associatedMasterId:
            if self._owner.parent:
                layer.associatedMasterId = self._owner.parent.masters[0].id
        if not layer.layerId:
            layer.layerId = str(uuid.uuid4()).upper()
        self._owner._setupLayer(layer, layer.layerId)
        self._owner._layers[layer.layerId] = layer

    def extend(self, layers):
        for layer in layers:
            self.append(layer)

    def remove(self, layer):
        return self._owner.removeLayerForKey_(layer.layerId)

    def insert(self, index, layer):
        self._ensureMasterLayers()
        self.append(layer)

    def setter(self, values):
        newLayers = OrderedDict()
        if type(values) == list or type(values) == tuple or type(values) == type(self):
            for layer in values:
                newLayers[layer.layerId] = layer
        elif type(values) == dict:  # or isinstance(values, NSDictionary)
            for layer in values.values():
                newLayers[layer.layerId] = layer
        else:
            raise TypeError
        for (key, layer) in newLayers.items():
            self._owner._setupLayer(layer, key)
        self._owner._layers = newLayers

    def _ensureMasterLayers(self):
        # Ensure existence of master-linked layers (even for iteration, len() etc.)
        # if accidentally deleted
        if not self._owner.parent:
            return
        for master in self._owner.parent.masters:
            # if (master.id not in self._owner._layers or
            #         self._owner._layers[master.id] is None):
            if self._owner.parent.masters[master.id] is None:
                newLayer = GSLayer()
                newLayer.associatedMasterId = master.id
                newLayer.layerId = master.id
                self._owner._setupLayer(newLayer, master.id)
                self.__setitem__(master.id, newLayer)

    def plistArray(self):
        return list(self._owner._layers.values())


class LayerAnchorsProxy(Proxy):
    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            return self.values().__getitem__(key)
        elif isinstance(key, str):
            for i, a in enumerate(self._owner._anchors):
                if a.name == key:
                    return self._owner._anchors[i]
        else:
            raise KeyError

    def __setitem__(self, key, anchor):
        if isinstance(key, str):
            anchor.name = key
            for i, a in enumerate(self._owner._anchors):
                if a.name == key:
                    self._owner._anchors[i] = anchor
                    return
            anchor._parent = self._owner
            self._owner._anchors.append(anchor)
        else:
            raise TypeError

    def __delitem__(self, key):
        if isinstance(key, int):
            del self._owner._anchors[key]
        elif isinstance(key, str):
            for i, a in enumerate(self._owner._anchors):
                if a.name == key:
                    self._owner._anchors[i]._parent = None
                    del self._owner._anchors[i]
                    return

    def values(self):
        return self._owner._anchors

    def append(self, anchor):
        for i, a in enumerate(self._owner._anchors):
            if a.name == anchor.name:
                anchor._parent = self._owner
                self._owner._anchors[i] = anchor
                return
        if anchor.name:
            self._owner._anchors.append(anchor)
        else:
            raise ValueError("Anchor must have name")

    def extend(self, anchors):
        for anchor in anchors:
            anchor._parent = self._owner
        self._owner._anchors.extend(anchors)

    def remove(self, anchor):
        if isinstance(anchor, str):
            anchor = self.values()[anchor]
        return self._owner._anchors.remove(anchor)

    def insert(self, index, anchor):
        anchor._parent = self._owner
        self._owner._anchors.insert(index, anchor)

    def __len__(self):
        return len(self._owner._anchors)

    def setter(self, anchors):
        if isinstance(anchors, Proxy):
            anchors = list(anchors)
        self._owner._anchors = anchors
        for anchor in anchors:
            anchor._parent = self._owner


class IndexedObjectsProxy(Proxy):
    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            return self.values().__getitem__(key)
        else:
            raise KeyError

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.values()[key] = value
            value._parent = self._owner
        else:
            raise KeyError

    def __delitem__(self, key):
        if isinstance(key, int):
            del self.values()[key]
        else:
            raise KeyError

    def values(self):
        return getattr(self._owner, self._objects_name)

    def append(self, value):
        self.values().append(value)
        value._parent = self._owner

    def extend(self, values):
        self.values().extend(values)
        for value in values:
            value._parent = self._owner

    def remove(self, value):
        self.values().remove(value)

    def insert(self, index, value):
        self.values().insert(index, value)
        value._parent = self._owner

    def __len__(self):
        return len(self.values())

    def setter(self, values):
        setattr(self._owner, self._objects_name, list(values))
        for value in self.values():
            value._parent = self._owner


class LayerShapesProxy(IndexedObjectsProxy):
    _objects_name = "_shapes"
    _filter = None

    def __init__(self, owner):
        super().__init__(owner)

    def append(self, value):
        self._owner._shapes.append(value)
        value._parent = self._owner

    def extend(self, values):
        self._owner._shapes.extend(values)
        for value in values:
            value._parent = self._owner

    def remove(self, value):
        self._owner._shapes.remove(value)

    def insert(self, index, value):
        self._owner._shapes.insert(index, value)
        value._parent = self._owner

    def __setitem__(self, key, value):
        if isinstance(key, int):
            index = self._owner._shapes.index(self.values()[key])
            self._owner._shapes[index] = value
            value._parent = self._owner
        else:
            raise KeyError

    def __delitem__(self, key):
        if isinstance(key, int):
            index = self._owner._shapes.index(self.values()[key])
            del self._owner._shapes[index]
        else:
            raise KeyError

    def setter(self, values):
        newvalues = list(
            filter(lambda s: not isinstance(s, self._filter), self._owner._shapes)
        )
        newvalues.extend(list(values))
        self._owner._shapes = newvalues
        for value in newvalues:
            value._parent = self._owner

    def values(self):
        return list(filter(lambda s: isinstance(s, self._filter), self._owner._shapes))


class LayerHintsProxy(IndexedObjectsProxy):
    _objects_name = "_hints"

    def __init__(self, owner):
        super().__init__(owner)


class LayerAnnotationProxy(IndexedObjectsProxy):
    _objects_name = "_annotations"

    def __init__(self, owner):
        super().__init__(owner)


class LayerGuideLinesProxy(IndexedObjectsProxy):
    _objects_name = "_guides"

    def __init__(self, owner):
        super().__init__(owner)


class PathNodesProxy(IndexedObjectsProxy):
    _objects_name = "_nodes"

    def __init__(self, owner):
        super().__init__(owner)


class CustomParametersProxy(Proxy):
    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.values().__getitem__(key)
        if isinstance(key, int):
            return self._owner._customParameters[key]
        else:
            customParameter = self._get_parameter_by_key(key)
            if customParameter is not None:
                return customParameter.value
        return None

    def _get_parameter_by_key(self, key):
        if key == "Axes" and isinstance(self._owner, GSFont):
            return self._owner._get_custom_parameter_from_axes()
        for customParameter in self._owner._customParameters:
            if customParameter.name == key:
                return customParameter

    def __setitem__(self, key, value):
        if key == "Axes" and isinstance(self._owner, GSFont):
            self._owner._set_axes_from_custom_parameter(value)
            return
        customParameter = self._get_parameter_by_key(key)
        if customParameter is not None:
            customParameter.value = value
        else:
            parameter = GSCustomParameter(name=key, value=value)
            self._owner._customParameters.append(parameter)

    def __delitem__(self, key):
        if isinstance(key, int):
            del self._owner._customParameters[key]
        elif isinstance(key, str):
            for parameter in self._owner._customParameters:
                if parameter.name == key:
                    self._owner._customParameters.remove(parameter)
        else:
            raise KeyError

    def __contains__(self, item):
        if isinstance(item, str):
            if item == "Axes" and isinstance(self._owner, GSFont):
                return self._owner.axes
            if item == "Axis Location" and isinstance(self._owner, GSInstance):
                return self._owner.axes
            return self.__getitem__(item) is not None
        return item in self._owner._customParameters

    def __iter__(self):
        for index in range(len(self._owner._customParameters)):
            yield self._owner._customParameters[index]
        if self._should_add_axes():
            yield self._owner._get_custom_parameter_from_axes()

    def _should_add_axes(self):
        if isinstance(self._owner, GSFont) and self._owner.format_version < 3:
            axes = self._owner._get_custom_parameter_from_axes()
            if axes:
                return True
        return False

    def append(self, parameter):
        parameter.parent = self._owner
        self._owner._customParameters.append(parameter)

    def extend(self, parameters):
        for parameter in parameters:
            parameter.parent = self._owner
        self._owner._customParameters.extend(parameters)

    def remove(self, parameter):
        if isinstance(parameter, str):
            parameter = self.__getitem__(parameter)
        self._owner._customParameters.remove(parameter)

    def insert(self, index, parameter):
        parameter.parent = self._owner
        self._owner._customParameters.insert(index, parameter)

    def __len__(self):
        if self._should_add_axes():
            return len(self._owner._customParameters) + 1

        return len(self._owner._customParameters)

    def values(self):
        return self._owner._customParameters

    def __setter__(self, parameters):
        for parameter in parameters:
            parameter.parent = self._owner
        self._owner._customParameters = parameters

    def setterMethod(self):
        return self.__setter__


class UserDataProxy(Proxy):
    def __getitem__(self, key):
        if self._owner._userData is None:
            return None
        # This is not the normal `dict` behaviour, because this does not raise
        # `KeyError` and instead just returns `None`. It matches Glyphs.app.
        return self._owner._userData.get(key)

    def __setitem__(self, key, value):
        if self._owner._userData is not None:
            self._owner._userData[key] = value
        else:
            self._owner._userData = {key: value}

    def __delitem__(self, key):
        if self._owner._userData is not None and key in self._owner._userData:
            del self._owner._userData[key]

    def __contains__(self, item):
        if self._owner._userData is None:
            return False
        return item in self._owner._userData

    def __iter__(self):
        if self._owner._userData is None:
            return
        # This is not the normal `dict` behaviour, because this yields values
        # instead of keys. It matches Glyphs.app though. Urg.
        yield from self._owner._userData.values()

    def values(self):
        if self._owner._userData is None:
            return []
        return self._owner._userData.values()

    def keys(self):
        if self._owner._userData is None:
            return []
        return self._owner._userData.keys()

    def items(self):
        if self._owner._userData is None:
            return []
        return self._owner._userData.items()

    def get(self, key):
        if self._owner._userData is None:
            return None
        return self._owner._userData.get(key)

    def setter(self, values):
        self._owner._userData = values


class GSAxis(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "hidden", "if_true")
        writer.writeObjectKeyValue(self, "name", True)
        writer.writeKeyValue("tag", self.axisTag)

    def __init__(self, name="", tag="", hidden=False):
        self.name = name
        self.axisTag = tag
        self.axisId = None
        self.hidden = hidden

    def __eq__(self, other):
        return self.name == other.name and self.axisTag == other.axisTag


GSAxis._add_parsers(
    [
        {"plist_name": "tag", "object_name": "axisTag"},
        {"plist_name": "hidden", "converter": bool},
    ]
)


class GSCustomParameter(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "disabled", self.disabled)
        writer.writeKeyValue("name", self.name)
        writer.writeKeyValue("value", self.value)

    _CUSTOM_INT_PARAMS = frozenset(
        (
            "ascender",
            "blueShift",
            "capHeight",
            "descender",
            "hheaAscender",
            "hheaDescender",
            "hheaLineGap",
            "subscriptXSize",
            "subscriptYSize",
            "subscriptXOffset",
            "subscriptYOffset",
            "superscriptXSize",
            "superscriptYSize",
            "superscriptXOffset",
            "superscriptYOffset",
            "macintoshFONDFamilyID",
            "openTypeHeadLowestRecPPEM",
            "openTypeHheaAscender",
            "openTypeHheaCaretOffset",
            "openTypeHheaCaretSlopeRise",
            "openTypeHheaCaretSlopeRun",
            "openTypeHheaDescender",
            "openTypeHheaLineGap",
            "openTypeOS2StrikeoutPosition",
            "openTypeOS2StrikeoutSize",
            "openTypeOS2SubscriptXOffset",
            "openTypeOS2SubscriptXSize",
            "openTypeOS2SubscriptYOffset",
            "openTypeOS2SubscriptYSize",
            "openTypeOS2SuperscriptXOffset",
            "openTypeOS2SuperscriptXSize",
            "openTypeOS2SuperscriptYOffset",
            "openTypeOS2SuperscriptYSize",
            "openTypeOS2TypoAscender",
            "openTypeOS2TypoDescender",
            "openTypeOS2TypoLineGap",
            "openTypeOS2WeightClass",
            "openTypeOS2WidthClass",
            "openTypeOS2WinAscent",
            "openTypeOS2WinDescent",
            "openTypeVheaCaretOffset",
            "openTypeVheaCaretSlopeRise",
            "openTypeVheaCaretSlopeRun",
            "openTypeVheaVertTypoAscender",
            "openTypeVheaVertTypoDescender",
            "openTypeVheaVertTypoLineGap",
            "postscriptBlueFuzz",
            "postscriptBlueShift",
            "postscriptDefaultWidthX",
            "postscriptUnderlinePosition",
            "postscriptUnderlineThickness",
            "postscriptUniqueID",
            "postscriptWindowsCharacterSet",
            "shoulderHeight",
            "smallCapHeight",
            "typoAscender",
            "typoDescender",
            "typoLineGap",
            "underlinePosition",
            "underlineThickness",
            "strikeoutSize",
            "strikeoutPosition",
            "unitsPerEm",
            "vheaVertAscender",
            "vheaVertDescender",
            "vheaVertLineGap",
            "weightClass",
            "widthClass",
            "winAscent",
            "winDescent",
            "year",
            "Grid Spacing",
        )
    )
    _CUSTOM_FLOAT_PARAMS = frozenset(("postscriptSlantAngle", "postscriptBlueScale"))

    _CUSTOM_BOOL_PARAMS = frozenset(
        (
            "isFixedPitch",
            "postscriptForceBold",
            "postscriptIsFixedPitch",
            "Don\u2019t use Production Names",
            "DisableAllAutomaticBehaviour",
            "Use Typo Metrics",
            "Has WWS Names",
            "Use Extension Kerning",
            "Disable Subroutines",
            "Don't use Production Names",
            "Disable Last Change",
        )
    )
    _CUSTOM_INTLIST_PARAMS = frozenset(
        (
            "fsType",
            "openTypeOS2CodePageRanges",
            "openTypeOS2FamilyClass",
            "openTypeOS2Panose",
            "openTypeOS2Type",
            "openTypeOS2UnicodeRanges",
            "panose",
            "unicodeRanges",
            "codePageRanges",
            "openTypeHeadFlags",
        )
    )
    _CUSTOM_DICT_PARAMS = frozenset("GASP Table")

    def __init__(self, name="New Value", value="New Parameter"):
        self.name = name
        self.value = value
        self.disabled = False

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}: {self._value}>"

    def plistValue(self, format_version=2):
        string = StringIO()
        writer = Writer(string, format_version=format_version)
        self._serialize_to_plist(writer)
        return "{\n" + string.getvalue() + "}"

    def getValue(self):
        return self._value

    def setValue(self, value):
        """Cast some known data in custom parameters."""
        if self.name in self._CUSTOM_INT_PARAMS:
            value = int(value)
        elif self.name in self._CUSTOM_FLOAT_PARAMS:
            value = float(value)
        elif self.name in self._CUSTOM_BOOL_PARAMS:
            value = bool(value)
        elif self.name in self._CUSTOM_INTLIST_PARAMS:
            value = readIntlist(value)
        elif self.name in self._CUSTOM_DICT_PARAMS:
            parser = Parser()
            value = parser.parse(value)
        elif self.name == "note":
            value = str(value)
        self._value = value

    value = property(getValue, setValue)


class GSMetric(GSBase):
    def __init__(self, name="", type=""):
        self.name = name
        self.type = type
        self.id = ""
        self.filter = ""
        self.horizontal = False

    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "horizontal", "if_true")
        writer.writeObjectKeyValue(self, "filter", "if_true")
        writer.writeObjectKeyValue(self, "name", "if_true")
        writer.writeObjectKeyValue(self, "type", "if_true")


class GSMetricValue(GSBase):
    def __init__(self, position=0, overshoot=0):
        self.position = position
        self.overshoot = overshoot
        self.name = ""
        self.filter = ""
        self.metric = ""

    def _serialize_to_plist(self, writer):
        writer.writeKeyValue("over", self.overshoot)
        if self.position:
            writer.writeKeyValue("pos", self.position)


GSMetricValue._add_parsers(
    [
        {"plist_name": "over", "object_name": "overshoot"},
        {"plist_name": "pos", "object_name": "position"},
    ]
)


class GSAlignmentZone(GSBase):
    def __init__(self, pos=0, size=20):
        self.position = pos
        self.size = size

    def read(self, src):
        if src is not None:
            p = Point(src)
            self.position = parse_float_or_int(p.value[0])
            self.size = parse_float_or_int(p.value[1])
        return self

    def __repr__(self):
        return "<{} pos:{:g} size:{:g}>".format(
            self.__class__.__name__, self.position, self.size
        )

    def __lt__(self, other):
        return (self.position, self.size) < (other.position, other.size)

    def plistValue(self, format_version=2):
        return '"{{{}, {}}}"'.format(
            floatToString5(self.position), floatToString5(self.size)
        )


class GSGuide(GSBase):
    def _serialize_to_plist(self, writer):
        for field in ["alignment", "angle", "filter"]:
            writer.writeObjectKeyValue(self, field, "if_true")
        if writer.format_version == 3:
            writer.writeObjectKeyValue(self, "lockAngle", "if_true")
        writer.writeObjectKeyValue(self, "locked", "if_true")

        writer.writeObjectKeyValue(self, "name", "if_true")
        if writer.format_version == 3 and self.position != Point(0, 0):
            writer.writeKeyValue("pos", self.position)
        else:
            writer.writeObjectKeyValue(self, "position", self.position != Point(0, 0))
        writer.writeObjectKeyValue(self, "showMeasurement", "if_true")

    _parent = None
    _defaultsForName = {"position": Point(0, 0), "angle": 0}

    def __init__(self):
        self.alignment = ""
        self.angle = 0
        self.filter = ""
        self.locked = False
        self.name = ""
        self.position = Point(0, 0)
        self.showMeasurement = False
        self.lockAngle = False

    def __repr__(self):
        return "<{} x={:.1f} y={:.1f} angle={:.1f}>".format(
            self.__class__.__name__, self.position.x, self.position.y, self.angle
        )

    @property
    def parent(self):
        return self._parent


GSGuide._add_parsers(
    [
        {"plist_name": "position", "converter": Point},  # v2
        {"plist_name": "pos", "object_name": "position", "converter": Point},  # v3
    ]
)


MASTER_NAME_WEIGHTS = ("Light", "SemiLight", "SemiBold", "Bold")
MASTER_NAME_WIDTHS = ("Condensed", "SemiCondensed", "Extended", "SemiExtended")


class GSFontMaster(GSBase):
    def _serialize_to_plist(self, writer):
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "alignmentZones", "if_true")
            writer.writeObjectKeyValue(self, "ascender")
        if writer.format_version == 3 and self.axes:
            writer.writeKeyValue("axesValues", self.axes)
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "capHeight")
            if self.customName:
                writer.writeKeyValue("custom", self.customName)
            writer.writeObjectKeyValue(self, "customValue", "if_true")
            writer.writeObjectKeyValue(self, "customValue1", "if_true")
            writer.writeObjectKeyValue(self, "customValue2", "if_true")
            writer.writeObjectKeyValue(self, "customValue3", "if_true")

        writer.writeObjectKeyValue(self, "customParameters", "if_true")

        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "descender")

        if self.guides:
            if writer.format_version == 3:
                writer.writeKeyValue("guides", self.guides)
            else:
                writer.writeKeyValue("guideLines", self.guides)

        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "horizontalStems", "if_true")

        writer.writeObjectKeyValue(self, "iconName", "if_true")
        writer.writeObjectKeyValue(self, "id")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "italicAngle", "if_true")
        if writer.format_version == 3:
            writer.writeKeyValue("metricValues", self.metrics)

        if (self._name and self._name != self.name) or writer.format_version == 3:
            writer.writeKeyValue("name", self._name or "Regular")

        if writer.format_version == 3:
            writer.writeObjectKeyValue(
                self, "numbers", "if_true", keyName="numberValues"
            )
            writer.writeObjectKeyValue(self, "stems", "if_true", keyName="stemValues")

        writer.writeObjectKeyValue(self, "userData", "if_true")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "verticalStems", "if_true")
        if writer.format_version == 3:
            writer.writeObjectKeyValue(self, "visible", "if_true")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "weight", self.weight != "Regular")
            writer.writeObjectKeyValue(self, "weightValue", self.weightValue != 100)
            writer.writeObjectKeyValue(self, "width", self.width != "Regular")
            writer.writeObjectKeyValue(self, "widthValue", self.widthValue != 100)
            writer.writeObjectKeyValue(self, "xHeight")

    _defaultsForName = {
        # FIXME: (jany) In the latest Glyphs (1113), masters don't have a width
        # and weight anymore as attributes, even though those properties are
        # still written to the saved files.
        "weight": "Regular",
        "width": "Regular",
        "x-height": 500,
        "cap height": 700,
        "ascender": 800,
        "descender": -200,
        "italic angle": 0,
    }

    _axis_defaults = (100, 100)

    def _parse_alignmentZones_dict(self, parser, text):
        _zones = parser._parse(text, str)
        self.alignmentZones = [GSAlignmentZone().read(x) for x in _zones]

    def __init__(self):
        self._customParameters = []
        self._name = None
        self._userData = None
        self.alignmentZones = []
        self.axes = list(self._axis_defaults)
        self.metrics = []
        self.customName = ""
        self.font = None
        self.guides = []
        self.horizontalStems = 0
        self.iconName = ""
        self.id = str(uuid.uuid4()).upper()
        self.numbers = []
        self.stems = []
        self.verticalStems = 0
        self.visible = False
        self.weight = self._defaultsForName["weight"]
        self.width = self._defaultsForName["width"]

    def __repr__(self):
        return '<GSFontMaster "{}" width {} weight {}>'.format(
            self.name, self.widthValue, self.weightValue
        )

    @property
    def metricsSource(self):
        """Returns the source master to be used for glyph and kerning metrics.

        If linked metrics parameters are being used, the master is returned here,
        otherwise None."""
        if self.customParameters["Link Metrics With First Master"]:
            return self.font.masters[0]
        source_master_id = self.customParameters["Link Metrics With Master"]

        # No custom parameters apply, go home
        if not source_master_id:
            return None

        # Try by master id
        source_master = self.font.masterForId(source_master_id)
        if source_master is not None:
            return source_master

        # Try by name
        for source_master in self.font.masters:
            if source_master.name == source_master_id:
                return source_master

        logger.warning(f"Source master for metrics not found: '{source_master_id}'")
        return self

    @property
    def name(self):
        name = self.customParameters["Master Name"]
        if name:
            return name
        if self._name:
            return self._name
        return self._joinName()

    @name.setter
    def name(self, name):
        """This function will take the given name and split it into components
        weight, width, customName, and possibly the full name.
        This is what Glyphs 1113 seems to be doing, approximately.
        """
        weight, width, custom_name = self._splitName(name)
        self.set_all_name_components(name, weight, width, custom_name)

    def set_all_name_components(self, name, weight, width, custom_name):
        """This function ensures that after being called, the master.name,
        master.weight, master.width, and master.customName match the given
        values.
        """
        self.weight = weight or "Regular"
        self.width = width or "Regular"
        self.customName = custom_name or ""
        # Only store the requested name if we can't build it from the parts
        if self._joinName() == name:
            self._name = None
            del self.customParameters["Master Name"]
        else:
            self._name = name
            self.customParameters["Master Name"] = name

    def _joinName(self):
        # Remove None and empty string
        names = list(filter(None, [self.width, self.weight, self.customName]))
        # Remove redundant occurences of 'Regular'
        while len(names) > 1 and "Regular" in names:
            names.remove("Regular")
        if self.italicAngle:
            if names == ["Regular"]:
                return "Italic"
            if "Italic" not in self.customName:
                names.append("Italic")
        return " ".join(names)

    def _splitName(self, value):
        if value is None:
            value = ""
        weight = "Regular"
        width = "Regular"
        custom = ""
        names = []
        previous_was_removed = False
        for name in value.split(" "):
            if name == "Regular":
                pass
            elif name in MASTER_NAME_WEIGHTS:
                if previous_was_removed:
                    # Get the double space in custom
                    names.append("")
                previous_was_removed = True
                weight = name
            elif name in MASTER_NAME_WIDTHS:
                if previous_was_removed:
                    # Get the double space in custom
                    names.append("")
                previous_was_removed = True
                width = name
            else:
                previous_was_removed = False
                names.append(name)
        custom = " ".join(names).strip()
        return weight, width, custom

    customParameters = property(
        lambda self: CustomParametersProxy(self),
        lambda self, value: CustomParametersProxy(self).setter(value),
    )

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value),
    )

    def _get_metric(self, metricname):
        if not self.font:
            metrics = GSFont._defaultMetrics
        else:
            metrics = self.font.metrics
        metricLabels = [x.type for x in metrics]
        if metricname not in metricLabels:
            return self._defaultsForName[metricname]
        metricIndex = metricLabels.index(metricname)
        if metricIndex > len(self.metrics) - 1:
            return self._defaultsForName[metricname]
        return self.metrics[metricIndex].position

    def _set_metric(self, metricname, value):
        if not self.font:
            metrics = GSFont._defaultMetrics
        else:
            metrics = self.font.metrics
        metricLabels = [x.type for x in metrics]
        if metricname not in metricLabels:
            self.font.metrics.append(GSMetric(type=metricname))
        metricIndex = metricLabels.index(metricname)
        while metricIndex > len(self.metrics) - 1:
            # Pad array with ... zeroes?
            self.metrics.append(GSMetricValue(position=0))
        self.metrics[metricIndex] = GSMetricValue(position=value)

    @property
    def ascender(self):
        return self._get_metric("ascender")

    @ascender.setter
    def ascender(self, value):
        self._set_metric("ascender", value)

    @property
    def xHeight(self):
        return self._get_metric("x-height")

    @xHeight.setter
    def xHeight(self, value):
        self._set_metric("x-height", value)

    @property
    def capHeight(self):
        return self._get_metric("cap height")

    @capHeight.setter
    def capHeight(self, value):
        self._set_metric("cap height", value)

    @property
    def descender(self):
        return self._get_metric("descender")

    @descender.setter
    def descender(self, value):
        self._set_metric("descender", value)

    @property
    def italicAngle(self):
        return self._get_metric("italic angle")

    @italicAngle.setter
    def italicAngle(self, value):
        self._set_metric("italic angle", value)

    def _get_axis_value(self, index):
        if index < len(self.axes):
            return self.axes[index]
        if index < len(self._axis_defaults):
            return self._axis_defaults[index]
        return 0

    def _set_axis_value(self, index, value):
        if index < len(self.axes):
            self.axes[index] = value
            return
        for j in range(len(self.axes), index):
            if j < len(self._axis_defaults):
                self.axes.append(self._axis_defaults[j])
            else:
                self.axes.append(0)
        self.axes.append(value)

    @property
    def weightValue(self):
        return self._get_axis_value(0)

    @weightValue.setter
    def weightValue(self, value):
        return self._set_axis_value(0, value)

    @property
    def widthValue(self):
        return self._get_axis_value(1)

    @widthValue.setter
    def widthValue(self, value):
        return self._set_axis_value(1, value)

    @property
    def customValue(self):
        return self._get_axis_value(2)

    @customValue.setter
    def customValue(self, value):
        return self._set_axis_value(2, value)

    @property
    def customValue1(self):
        return self._get_axis_value(3)

    @customValue1.setter
    def customValue1(self, value):
        return self._set_axis_value(3, value)

    @property
    def customValue2(self):
        return self._get_axis_value(4)

    @customValue2.setter
    def customValue2(self, value):
        return self._set_axis_value(4, value)

    @property
    def customValue3(self):
        return self._get_axis_value(5)

    @customValue3.setter
    def customValue3(self, value):
        return self._set_axis_value(5, value)


GSFontMaster._add_parsers(
    [
        {"plist_name": "customParameters", "type": GSCustomParameter},
        {"plist_name": "guideLines", "object_name": "guides", "type": GSGuide},  # v2
        {"plist_name": "guides", "object_name": "guides", "type": GSGuide},  # v3
        {"plist_name": "custom", "object_name": "customName"},
        {"plist_name": "axesValues", "object_name": "axes"},  # v3
        {"plist_name": "numberValues", "object_name": "numbers"},  # v3
        {"plist_name": "stemValues", "object_name": "stems"},  # v3
        {
            "plist_name": "metricValues",
            "object_name": "metrics",
            "type": GSMetricValue,
        },  # v3
        {"plist_name": "name", "object_name": "_name"},
    ]
)


class GSNode(GSBase):
    _PLIST_VALUE_RE = re.compile(
        r"([-.e\d]+) ([-.e\d]+) (LINE|CURVE|QCURVE|OFFCURVE|n/a)"
        r"(?: (SMOOTH))?(?: ({.*}))?",
        re.DOTALL,
    )

    __slots__ = "_parent", "_userData", "_position", "smooth", "type"

    def __init__(
        self, position=(0, 0), type=LINE, smooth=False, name=None, nodetype=None
    ):
        self._position = Point(position[0], position[1])
        self._userData = None
        self.smooth = smooth
        self.type = type
        if nodetype is not None:  # for backward compatibility
            self.type = nodetype
        # Optimization: Points can number in the 10000s, don't access the userDataProxy
        # through `name` unless needed.
        if name is not None:
            self.name = name

    def __repr__(self):
        content = self.type
        if self.smooth:
            content += " smooth"
        return "<{} {:g} {:g} {}>".format(
            self.__class__.__name__, self.position.x, self.position.y, content
        )

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value),
    )

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        if not isinstance(value, Point):
            value = Point(value[0], value[1])
        self._position = value

    @property
    def parent(self):
        return self._parent

    def plistValue(self, format_version=2):
        string = ""
        if self._userData is not None and len(self._userData) > 0:
            string = StringIO()
            writer = Writer(string, format_version=format_version)
            writer.writeDict(self._userData)
        if format_version == 2:
            content = self.type.upper()
            if self.smooth:
                content += " SMOOTH"
            if string:
                content += " "
                content += self._encode_dict_as_string(string.getvalue())
            return '"{} {} {}"'.format(
                floatToString5(self.position[0]),
                floatToString5(self.position[1]),
                content,
            )
        else:
            if self.type == CURVE:
                content = "c"
            elif self.type == QCURVE:
                content = "q"
            elif self.type == OFFCURVE:
                content = "o"
            elif self.type == LINE:
                content = "l"
            if self.smooth:
                content += "s"
            if string:
                content += "," + string.getvalue()
            return "({},{},{})".format(
                floatToString5(self.position[0]),
                floatToString5(self.position[1]),
                content,
            )

    @classmethod
    def read(cls, line):
        """Parse a Glyphs node string into a GSNode.

        The format of a Glyphs node string (`line`) is:

            "X Y (LINE|CURVE|QCURVE|OFFCURVE)"
            "X Y (LINE|CURVE|QCURVE|OFFCURVE) SMOOTH"
            "X Y (LINE|CURVE|QCURVE|OFFCURVE) SMOOTH {dictionary}"
            "X Y (LINE|CURVE|QCURVE|OFFCURVE) {dictionary}"

        X and Y can be integers or floats, positive or negative.

        WARNING: This method is HOT. It is called for every single node and can
        account for a significant portion of the file parsing time.
        """
        m = cls._PLIST_VALUE_RE.match(line).groups()
        node = cls(
            position=(parse_float_or_int(m[0]), parse_float_or_int(m[1])),
            type=m[2].lower(),
            smooth=bool(m[3]),
        )
        if m[4] is not None and len(m[4]) > 0:
            value = cls._decode_dict_as_string(m[4])
            parser = Parser()
            node._userData = parser.parse(value)

        return node

    @classmethod
    def read_v3(cls, lst):
        position = (lst[0], lst[1])
        smooth = lst[2].endswith("s")
        if lst[2][0] == "c":
            node_type = CURVE
        elif lst[2][0] == "o":
            node_type = OFFCURVE
        elif lst[2][0] == "l":
            node_type = LINE
        elif lst[2][0] == "q":
            node_type = QCURVE
        else:
            node_type = None
        node = cls(position=position, type=node_type, smooth=smooth)
        if len(lst) > 3:
            node._userData = lst[3]
        return node

    @property
    def name(self):
        if "name" in self.userData:
            return self.userData["name"]
        return None

    @name.setter
    def name(self, value):
        if value is None:
            if "name" in self.userData:
                del self.userData["name"]
        else:
            self.userData["name"] = value

    @property
    def index(self):
        assert self.parent
        return self.parent.nodes.index(self)

    @property
    def nextNode(self):
        assert self.parent
        index = self.index
        if index == (len(self.parent.nodes) - 1):
            return self.parent.nodes[0]
        elif index < len(self.parent.nodes):
            return self.parent.nodes[index + 1]

    @property
    def prevNode(self):
        assert self.parent
        index = self.index
        if index == 0:
            return self.parent.nodes[-1]
        elif index < len(self.parent.nodes):
            return self.parent.nodes[index - 1]

    def makeNodeFirst(self):
        assert self.parent
        if self.type == "offcurve":
            raise ValueError("Off-curve points cannot become start points.")
        nodes = self.parent.nodes
        index = self.index
        newNodes = nodes[index : len(nodes)] + nodes[0:index]
        self.parent.nodes = newNodes

    def toggleConnection(self):
        self.smooth = not self.smooth

    # TODO
    @property
    def connection(self):
        raise NotImplementedError

    # TODO
    @property
    def selected(self):
        raise OnlyInGlyphsAppError

    @staticmethod
    def _encode_dict_as_string(value):
        """Takes the PLIST string of a dict, and returns the same string
        encoded such that it can be included in the string representation
        of a GSNode."""
        # Strip the first and last newlines
        if value.startswith("{\n"):
            value = "{" + value[2:]
        if value.endswith("\n}"):
            value = value[:-2] + "}"
        # escape double quotes and newlines
        return value.replace('"', '\\"').replace("\\n", "\\\\n").replace("\n", "\\n")

    _ESCAPED_CHAR_RE = re.compile(r'\\(\\*)(?:(n)|("))')

    @staticmethod
    def _unescape_char(m):
        backslashes = m.group(1) or ""
        if m.group(2):
            return "\n" if not backslashes else backslashes + "n"
        else:
            return backslashes + '"'

    @classmethod
    def _decode_dict_as_string(cls, value):
        """Reverse function of _encode_string_as_dict"""
        # strip one level of backslashes preceding quotes and newlines
        return cls._ESCAPED_CHAR_RE.sub(cls._unescape_char, value)

    def _indices(self):
        """Find the path_index and node_index that identify the given node."""
        path = self.parent
        layer = path.parent
        for path_index in range(len(layer.paths)):
            if path == layer.paths[path_index]:
                for node_index in range(len(path.nodes)):
                    if self == path.nodes[node_index]:
                        return Point(path_index, node_index)
        return None


class GSPath(GSBase):
    _defaultsForName = {"closed": True}
    _parent = None

    def _serialize_to_plist(self, writer):
        if writer.format_version == 3 and self.attributes:
            writer.writeObjectKeyValue(self, "attributes", keyName="attr")
        writer.writeObjectKeyValue(self, "closed")
        writer.writeObjectKeyValue(self, "nodes", "if_true")

    def _parse_nodes_dict(self, parser, d):
        if parser.format_version == 3:
            read_node = GSNode.read_v3
        else:
            read_node = GSNode.read
        for x in d:
            node = read_node(x)
            node._parent = self
            self._nodes.append(node)

    def __init__(self):
        self.closed = self._defaultsForName["closed"]
        self._nodes = []
        self.attributes = {}

    @property
    def parent(self):
        return self._parent

    nodes = property(
        lambda self: PathNodesProxy(self),
        lambda self, value: PathNodesProxy(self).setter(value),
    )

    @property
    def segments(self):
        self._segments = []
        self._segmentLength = 0

        nodeCount = 0
        segmentCount = 0
        nodes = list(self.nodes)
        # Cycle node list until curve or line at end
        cycled = False
        for i, n in enumerate(nodes):
            if n.type == "offcurve" or n.type == "line":
                nodes = nodes[i:] + nodes[:i]
                cycled = True
                break
        if not cycled:
            return []

        def wrap(i):
            if i >= len(nodes):
                i = i % len(nodes)
            return i

        while nodeCount < len(nodes):
            newSegment = segment()
            newSegment.parent = self
            newSegment.index = segmentCount

            if nodeCount == 0:
                newSegment.appendNode(nodes[-1])
            else:
                newSegment.appendNode(nodes[nodeCount - 1])

            if nodes[nodeCount].type == "offcurve":
                newSegment.appendNode(nodes[nodeCount])
                newSegment.appendNode(nodes[wrap(nodeCount + 1)])
                newSegment.appendNode(nodes[wrap(nodeCount + 2)])
                nodeCount += 3
            elif nodes[nodeCount].type == "line":
                newSegment.appendNode(nodes[nodeCount])
                nodeCount += 1

            self._segments.append(newSegment)
            self._segmentLength += 1
            segmentCount += 1

        return self._segments

    @segments.setter
    def segments(self, value):
        if type(value) in (list, tuple):
            self.setSegments(value)
        else:
            raise TypeError

    def setSegments(self, segments):
        self.nodes = []
        for segment in segments:
            if len(segment.nodes) == 2 or len(segment.nodes) == 4:
                self.nodes.extend(segment.nodes[1:])
            else:
                raise ValueError

    @property
    def bounds(self):
        left, bottom, right, top = None, None, None, None
        for segment in self.segments:
            newLeft, newBottom, newRight, newTop = segment.bbox()
            if left is None:
                left = newLeft
            else:
                left = min(left, newLeft)
            if bottom is None:
                bottom = newBottom
            else:
                bottom = min(bottom, newBottom)
            if right is None:
                right = newRight
            else:
                right = max(right, newRight)
            if top is None:
                top = newTop
            else:
                top = max(top, newTop)
        return Rect(Point(left, bottom), Point(right - left, top - bottom))

    @property
    def direction(self):
        direction = 0
        for i in range(len(self.nodes)):
            thisNode = self.nodes[i]
            nextNode = thisNode.nextNode
            direction += (nextNode.position.x - thisNode.position.x) * (
                nextNode.position.y + thisNode.position.y
            )
        if direction < 0:
            return -1
        else:
            return 1

    @property
    def selected(self):
        raise OnlyInGlyphsAppError

    @property
    def bezierPath(self):
        raise OnlyInGlyphsAppError

    def reverse(self):
        segments = list(reversed(self.segments))
        for s, segment in enumerate(segments):
            segment.nodes = list(reversed(segment.nodes))
            if s == len(segments) - 1:
                nextSegment = segments[0]
            else:
                nextSegment = segments[s + 1]
            if len(segment.nodes) == 2 and segment.nodes[-1].type == "curve":
                segment.nodes[-1].type = "line"
                nextSegment.nodes[0].type = "line"
            elif len(segment.nodes) == 4 and segment.nodes[-1].type == "line":
                segment.nodes[-1].type = "curve"
                nextSegment.nodes[0].type = "curve"
        self.setSegments(segments)

    # TODO
    def addNodesAtExtremes(self):
        raise NotImplementedError

    # TODO
    def applyTransform(self, transformationMatrix):
        assert len(transformationMatrix) == 6
        for node in self.nodes:
            transformation = Affine(
                transformationMatrix[0],
                transformationMatrix[1],
                transformationMatrix[4],
                transformationMatrix[2],
                transformationMatrix[3],
                transformationMatrix[5],
            )
            x, y = (node.position.x, node.position.y) * transformation
            node.position.x = x
            node.position.y = y

    def draw(self, pen: AbstractPen) -> None:
        """Draws contour with the given pen."""
        pointPen = PointToSegmentPen(pen)
        self.drawPoints(pointPen)

    def drawPoints(self, pointPen: AbstractPointPen) -> None:
        """Draws points of contour with the given point pen."""
        nodes = list(self.nodes)

        pointPen.beginPath()

        if not nodes:
            pointPen.endPath()
            return

        if not self.closed:
            node = nodes.pop(0)
            assert node.type == "line", "Open path starts with off-curve points"
            node_data = dict(node.userData)
            node_name = node_data.pop("name", None)
            pointPen.addPoint(
                tuple(node.position),
                segmentType="move",
                name=node_name,
                userData=node_data,
            )
        else:
            # In Glyphs.app, the starting node of a closed contour is always
            # stored at the end of the nodes list.
            nodes.insert(0, nodes.pop())

        for node in nodes:
            node_type = node.type if node.type in _UFO_NODE_TYPES else None
            node_data = dict(node.userData)
            node_name = node_data.pop("name", None)
            pointPen.addPoint(
                tuple(node.position),
                segmentType=node_type,
                smooth=node.smooth,
                name=node_name,
                userData=node_data,
            )
        pointPen.endPath()


GSPath._add_parsers([{"plist_name": "attr", "object_name": "attributes"}])  # V3


# 'offcurve' GSNode.type is equivalent to 'None' in UFO PointPen API
_UFO_NODE_TYPES = {"line", "curve", "qcurve"}


class segment(list):
    def appendNode(self, node):
        if not hasattr(
            self, "nodes"
        ):  # instead of defining this in __init__(), because I hate super()
            self.nodes = []
        self.nodes.append(node)
        self.append(Point(node.position.x, node.position.y))

    @property
    def nextSegment(self):
        assert self.parent
        index = self.index
        if index == (len(self.parent._segments) - 1):
            return self.parent._segments[0]
        elif index < len(self.parent._segments):
            return self.parent._segments[index + 1]

    @property
    def prevSegment(self):
        assert self.parent
        index = self.index
        if index == 0:
            return self.parent._segments[-1]
        elif index < len(self.parent._segments):
            return self.parent._segments[index - 1]

    def bbox(self):
        if len(self) == 2:
            left = min(self[0].x, self[1].x)
            bottom = min(self[0].y, self[1].y)
            right = max(self[0].x, self[1].x)
            top = max(self[0].y, self[1].y)
            return left, bottom, right, top
        elif len(self) == 4:
            left, bottom, right, top = self.bezierMinMax(
                self[0].x,
                self[0].y,
                self[1].x,
                self[1].y,
                self[2].x,
                self[2].y,
                self[3].x,
                self[3].y,
            )
            return left, bottom, right, top
        else:
            raise ValueError

    def bezierMinMax(self, x0, y0, x1, y1, x2, y2, x3, y3):
        tvalues = []
        xvalues = []
        yvalues = []

        for i in range(2):
            if i == 0:
                b = 6 * x0 - 12 * x1 + 6 * x2
                a = -3 * x0 + 9 * x1 - 9 * x2 + 3 * x3
                c = 3 * x1 - 3 * x0
            else:
                b = 6 * y0 - 12 * y1 + 6 * y2
                a = -3 * y0 + 9 * y1 - 9 * y2 + 3 * y3
                c = 3 * y1 - 3 * y0

            if abs(a) < 1e-12:
                if abs(b) < 1e-12:
                    continue
                t = -c / b
                if 0 < t < 1:
                    tvalues.append(t)
                continue

            b2ac = b * b - 4 * c * a
            if b2ac < 0:
                continue
            sqrtb2ac = math.sqrt(b2ac)
            t1 = (-b + sqrtb2ac) / (2 * a)
            if 0 < t1 < 1:
                tvalues.append(t1)
            t2 = (-b - sqrtb2ac) / (2 * a)
            if 0 < t2 < 1:
                tvalues.append(t2)

        for j in range(len(tvalues) - 1, -1, -1):
            t = tvalues[j]
            mt = 1 - t
            newxValue = (
                (mt * mt * mt * x0)
                + (3 * mt * mt * t * x1)
                + (3 * mt * t * t * x2)
                + (t * t * t * x3)
            )
            if len(xvalues) > j:
                xvalues[j] = newxValue
            else:
                xvalues.append(newxValue)
            newyValue = (
                (mt * mt * mt * y0)
                + (3 * mt * mt * t * y1)
                + (3 * mt * t * t * y2)
                + (t * t * t * y3)
            )
            if len(yvalues) > j:
                yvalues[j] = newyValue
            else:
                yvalues.append(newyValue)

        xvalues.append(x0)
        xvalues.append(x3)
        yvalues.append(y0)
        yvalues.append(y3)

        return min(xvalues), min(yvalues), max(xvalues), max(yvalues)


class GSComponent(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "alignment", "if_true")
        writer.writeObjectKeyValue(self, "anchor", "if_true")
        writer.writeObjectKeyValue(self, "locked", "if_true")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "name")
        if self.smartComponentValues:
            writer.writeKeyValue("piece", self.smartComponentValues)
        if writer.format_version > 2:
            writer.writeObjectKeyValue(
                self, "position", keyName="pos", default=Point(0, 0)
            )
            writer.writeObjectKeyValue(self, "rotation", keyName="angle", default=0)
            writer.writeObjectKeyValue(self, "name", keyName="ref")
            if self.scale != (1, 1):
                writer.writeKeyValue("scale", Point(list(self.scale)))
        if writer.format_version == 2:
            writer.writeObjectKeyValue(
                self, "transform", self.transform != Transform(1, 0, 0, 1, 0, 0)
            )

    _defaultsForName = {"transform": Transform(1, 0, 0, 1, 0, 0)}
    _parent = None

    # TODO: glyph arg is required
    def __init__(self, glyph="", offset=(0, 0), scale=(1, 1), transform=None):
        self.alignment = 0
        self.anchor = ""
        self.locked = False

        if isinstance(glyph, str):
            self.name = glyph
        elif isinstance(glyph, GSGlyph):
            self.name = glyph.name

        self.smartComponentValues = {}

        if transform is None:
            if scale != (1, 1) or offset != (0, 0):
                xx, yy = scale
                dx, dy = offset
                self.transform = Transform(xx, 0, 0, yy, dx, dy)
            else:
                self.transform = copy.deepcopy(self._defaultsForName["transform"])
        else:
            self.transform = transform

    def __repr__(self):
        return '<GSComponent "{}" x={:.1f} y={:.1f}>'.format(
            self.name, self.transform[4], self.transform[5]
        )

    @property
    def parent(self):
        return self._parent

    # .position
    @property
    def position(self):
        return Point(self.transform[4], self.transform[5])

    @position.setter
    def position(self, value):
        self.transform[4] = value[0]
        self.transform[5] = value[1]

    # .scale
    @property
    def scale(self):
        self._sX, self._sY, self._R = transformStructToScaleAndRotation(
            self.transform.value
        )
        return self._sX, self._sY

    @scale.setter
    def scale(self, value):
        self._sX, self._sY, self._R = transformStructToScaleAndRotation(
            self.transform.value
        )
        if type(value) in [int, float]:
            self._sX = value
            self._sY = value
        elif type(value) in [tuple, list] and len(value) == 2:
            self._sX, self._sY = value
        else:
            raise ValueError
        self.updateAffineTransform()

    # .rotation
    @property
    def rotation(self):
        self._sX, self._sY, self._R = transformStructToScaleAndRotation(
            self.transform.value
        )
        return self._R

    @rotation.setter
    def rotation(self, value):
        self._sX, self._sY, self._R = transformStructToScaleAndRotation(
            self.transform.value
        )
        self._R = value
        self.updateAffineTransform()

    def updateAffineTransform(self):
        affine = list(
            Affine.translation(self.transform[4], self.transform[5])
            * Affine.scale(self._sX, self._sY)
            * Affine.rotation(self._R)
        )[:6]
        self.transform = Transform(
            affine[0], affine[1], affine[3], affine[4], affine[2], affine[5]
        )

    @property
    def componentName(self):
        return self.name

    @componentName.setter
    def componentName(self, value):
        self.name = value

    @property
    def component(self):
        return self.parent.parent.parent.glyphs[self.name]

    @property
    def layer(self):
        return self.parent.parent.parent.glyphs[self.name].layers[self.parent.layerId]

    def applyTransformation(self, x, y):
        x *= self.scale[0]
        y *= self.scale[1]
        x += self.position.x
        y += self.position.y
        # TODO:
        # Integrate rotation
        return x, y

    @property
    def bounds(self):
        bounds = self.layer.bounds
        if bounds is not None:
            left, bottom, width, height = self.layer.bounds
            right = left + width
            top = bottom + height

            left, bottom = self.applyTransformation(left, bottom)
            right, top = self.applyTransformation(right, top)

            if (
                left is not None
                and bottom is not None
                and right is not None
                and top is not None
            ):
                return Rect(Point(left, bottom), Point(right - left, top - bottom))

    # smartComponentValues = property(
    #     lambda self: self.piece,
    #     lambda self, value: setattr(self, "piece", value))

    def draw(self, pen: AbstractPen) -> None:
        """Draws component with given pen."""
        pen.addComponent(self.name, self.transform)

    def drawPoints(self, pointPen: AbstractPointPen) -> None:
        """Draws points of component with given point pen."""
        pointPen.addComponent(self.name, self.transform)


GSComponent._add_parsers(
    [
        {"plist_name": "transform", "object_name": "transform", "converter": Transform},
        {"plist_name": "piece", "object_name": "smartComponentValues", "type": dict},
        {"plist_name": "angle", "object_name": "rotation", "type": float},
        {"plist_name": "pos", "object_name": "position", "converter": Point},
        {"plist_name": "ref", "object_name": "name"},
        {"plist_name": "locked", "converter": bool},
    ]
)


class GSSmartComponentAxis(GSBase):
    def _serialize_to_plist(self, writer):
        if writer.format_version == 3:
            writer.writeObjectKeyValue(self, "bottomName", "if_true")
            writer.writeObjectKeyValue(self, "bottomValue")
            writer.writeObjectKeyValue(self, "name")
        else:
            writer.writeObjectKeyValue(self, "name")
            writer.writeObjectKeyValue(self, "bottomName", "if_true")
            writer.writeObjectKeyValue(self, "bottomValue", True)
        writer.writeObjectKeyValue(self, "topName", "if_true")
        writer.writeObjectKeyValue(self, "topValue", True)

    _defaultsForName = {"bottomValue": 0, "topValue": 0}

    def __init__(self):
        self.bottomName = ""
        self.bottomValue = self._defaultsForName["bottomValue"]
        self.name = ""
        self.topName = ""
        self.topValue = self._defaultsForName["topValue"]


class GSAnchor(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "name", "if_true")
        posKey = "position"
        if writer.format_version > 2:
            posKey = "pos"
        writer.writeObjectKeyValue(
            self, "position", True, keyName=posKey, default=Point(0, 0)
        )

    _parent = None
    _defaultsForName = {"position": Point(0, 0)}

    def __init__(self, name=None, position=None):
        self.name = "" if name is None else name
        if position is None:
            self.position = copy.deepcopy(self._defaultsForName["position"])
        else:
            self.position = position

    def __repr__(self):
        return '<{} "{}" x={:.1f} y={:.1f}>'.format(
            self.__class__.__name__, self.name, self.position[0], self.position[1]
        )

    @property
    def parent(self):
        return self._parent


GSAnchor._add_parsers(
    [
        {"plist_name": "pos", "object_name": "position", "converter": Point},
        {"plist_name": "position", "converter": Point},
    ]
)


class GSHint(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "horizontal", "if_true")

        for field in ["origin", "place"]:
            writer.writeObjectKeyValue(self, field)
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "target")
        elif self.target:
            writer.writeKey("target")
            if isinstance(self.target, list):
                writer.file.write("(%i,%i)" % (self.target[0], self.target[1]))
            else:
                writer.writeValue(self.target)
            writer.file.write(";\n")
        for field in ["other1", "other2", "scale"]:
            writer.writeObjectKeyValue(self, field)
        writer.writeObjectKeyValue(self, "stem", self.stem != -2)

        for field in ["type", "name", "options", "settings"]:
            writer.writeObjectKeyValue(self, field, condition="if_true")

    _defaultsForName = {
        # TODO: (jany) check defaults in glyphs
        "origin": None,
        "other1": None,
        "other2": None,
        "place": None,
        "scale": None,
        "stem": -2,
    }

    def _parse_target_dict(self, parser, value):
        # In glyphs 2 this is a string, in glyphs 3 it is a point or string
        if isinstance(value, str):
            self._target = parse_hint_target(value)
        else:
            self._target = Point([int(x) for x in value])

    def __init__(self):
        self.horizontal = False
        self.name = ""
        self.options = 0
        self.origin = self._defaultsForName["origin"]
        self.other1 = self._defaultsForName["other1"]
        self.other2 = self._defaultsForName["other2"]
        self.place = self._defaultsForName["place"]
        self.scale = self._defaultsForName["scale"]
        self.settings = {}
        self.stem = self._defaultsForName["stem"]
        self.type = ""
        self._target = None
        self._targetNode = None

    def _origin_pos(self):
        if self.originNode:
            if self.horizontal:
                return self.originNode.position.y
            else:
                return self.originNode.position.x
        return self.origin

    def _width_pos(self):
        if self.targetNode:
            if self.horizontal:
                return self.targetNode.position.y
            else:
                return self.targetNode.position.x
        return self.width

    def __repr__(self):
        if self.horizontal:
            direction = "horizontal"
        else:
            direction = "vertical"
        if self.type == "BOTTOMGHOST" or self.type == "TOPGHOST":
            return "<GSHint {} origin=({})>".format(self.type, self._origin_pos())
        elif self.type == "STEM":
            return "<GSHint {} Stem origin=({}) target=({})>".format(
                direction, self._origin_pos(), self._width_pos()
            )
        elif self.type == "CORNER" or self.type == "CAP":
            return f"<GSHint {self.type} {self.name}>"
        else:
            return f"<GSHint {self.type} {direction}>"

    @property
    def parent(self):
        return self._parent

    @property
    def originNode(self):
        if self._originNode is not None:
            return self._originNode
        if self._origin is not None:
            return self.parent._find_node_by_indices(self._origin)

    @originNode.setter
    def originNode(self, node):
        self._originNode = node
        self._origin = None

    @property
    def origin(self):
        if self._origin is not None:
            return self._origin
        if self._originNode is not None:
            return self._originNode._indices()

    @origin.setter
    def origin(self, origin):
        self._origin = origin
        self._originNode = None

    @property
    def targetNode(self):
        if self._targetNode is not None:
            return self._targetNode
        if self._target is not None:
            return self.parent._find_node_by_indices(self._target)

    @targetNode.setter
    def targetNode(self, node):
        self._targetNode = node
        self._target = None

    @property
    def target(self):
        if self._target is not None:
            return self._target
        if self._targetNode is not None:
            return self._targetNode._indices()

    @target.setter
    def target(self, target):
        self._target = target
        self._targetNode = None

    @property
    def otherNode1(self):
        if self._otherNode1 is not None:
            return self._otherNode1
        if self._other1 is not None:
            return self.parent._find_node_by_indices(self._other1)

    @otherNode1.setter
    def otherNode1(self, node):
        self._otherNode1 = node
        self._other1 = None

    @property
    def other1(self):
        if self._other1 is not None:
            return self._other1
        if self._otherNode1 is not None:
            return self._otherNode1._indices()

    @other1.setter
    def other1(self, other1):
        self._other1 = other1
        self._otherNode1 = None

    @property
    def otherNode2(self):
        if self._otherNode2 is not None:
            return self._otherNode2
        if self._other2 is not None:
            return self.parent._find_node_by_indices(self._other2)

    @otherNode2.setter
    def otherNode2(self, node):
        self._otherNode2 = node
        self._other2 = None

    @property
    def other2(self):
        if self._other2 is not None:
            return self._other2
        if self._otherNode2 is not None:
            return self._otherNode2._indices()

    @other2.setter
    def other2(self, other2):
        self._other2 = other2
        self._otherNode2 = None


GSHint._add_parsers(
    [
        {"plist_name": "origin", "object_name": "_origin", "converter": Point},
        {"plist_name": "other1", "object_name": "_other1", "converter": Point},
        {"plist_name": "other2", "object_name": "_other2", "converter": Point},
        {"plist_name": "place", "converter": Point},
        {"plist_name": "scale", "converter": Point},
        {"plist_name": "horizontal", "converter": bool},
    ]
)


class GSFeature(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "automatic", "if_true")
        writer.writeObjectKeyValue(self, "disabled", "if_true")
        writer.writeObjectKeyValue(self, "code", True)
        if writer.format_version == 3:
            writer.writeObjectKeyValue(self, "labels", "if_true")
            writer.writeKeyValue("tag", self.name)
        else:
            writer.writeKeyValue("name", self.name)
        writer.writeObjectKeyValue(self, "notes", "if_true")

    def __init__(self, name="xxxx", code=""):
        self.automatic = False
        self.code = code
        self.disabled = False
        self.name = name
        self.notes = ""
        self.labels = []

    def getCode(self):
        return self._code

    def setCode(self, code):
        replacements = (
            ("\\012", "\n"),
            ("\\011", "\t"),
            ("\\U2018", "'"),
            ("\\U2019", "'"),
            ("\\U201C", '"'),
            ("\\U201D", '"'),
        )
        for escaped, unescaped in replacements:
            code = code.replace(escaped, unescaped)
        self._code = code

    code = property(getCode, setCode)

    def __repr__(self):
        return f'<{self.__class__.__name__} "{self.name}">'

    @property
    def parent(self):
        return self._parent


GSFeature._add_parsers(
    [
        {"plist_name": "code", "object_name": "_code"},
        {"plist_name": "tag", "object_name": "name"},
        {"plist_name": "labels", "type": dict},
    ]
)


class GSClass(GSFeature):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "automatic", "if_true")
        writer.writeObjectKeyValue(self, "disabled", "if_true")
        writer.writeObjectKeyValue(self, "code", True)
        writer.writeKeyValue("name", self.name)

    pass


class GSFeaturePrefix(GSClass):
    pass


class GSAnnotation(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "angle", default=0)
        posKey = "position"
        if writer.format_version > 2:
            posKey = "pos"
        writer.writeObjectKeyValue(
            self, "position", keyName=posKey, default=Point(0, 0)
        )
        writer.writeObjectKeyValue(self, "text", "if_true")
        writer.writeObjectKeyValue(self, "type", "if_true")
        writer.writeObjectKeyValue(self, "width", default=100)

    _defaultsForName = {
        "angle": 0,
        "position": Point(0, 0),
        "text": None,
        "type": 0,
        "width": 100,
    }
    _parent = None

    def __init__(self):
        self.angle = self._defaultsForName["angle"]
        self.position = copy.deepcopy(self._defaultsForName["position"])
        self.text = self._defaultsForName["text"]
        self.type = self._defaultsForName["type"]
        self.width = self._defaultsForName["width"]

    @property
    def parent(self):
        return self._parent


GSAnnotation._add_parsers(
    [
        {"plist_name": "pos", "object_name": "position", "converter": Point},
        {"plist_name": "position", "converter": Point},
    ]
)


class GSFontInfoValue(GSBase):  # Combines localizable/nonlocalizable properties
    def __init__(self, key="", value=""):
        self.key = key
        self.value = value
        self.localized_values = None

    def _parse_values_dict(self, parser, values):
        self.localized_values = {}
        for v in values:
            if "language" not in v or "value" not in v:
                continue
            self.localized_values[v["language"]] = v["value"]

    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "key", "if_true")
        if self.localized_values:
            writer.writeKeyValue(
                "values",
                [{"language": l, "value": v} for l, v in self.localized_values.items()],
            )
        else:
            writer.writeObjectKeyValue(self, "value")

    @property
    def defaultValue(self):
        if not self.localized_values:
            return self.value
        for key in ["dflt", "default", "ENG"]:
            if key in self.localized_values:
                return self.localized_values[key]
        return list(self.localized_values.values())[0]


class GSInstance(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "active", condition=(not self.active))
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "axes", keyName="axesValues")
        writer.writeObjectKeyValue(self, "exports", condition=(not self.exports))
        writer.writeObjectKeyValue(self, "customParameters", condition="if_true")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(
                self, "customValue", condition="if_true", keyName="interpolationCustom"
            )
            writer.writeObjectKeyValue(
                self,
                "customValue1",
                condition="if_true",
                keyName="interpolationCustom1",
            )
            writer.writeObjectKeyValue(
                self,
                "customValue2",
                condition="if_true",
                keyName="interpolationCustom2",
            )
            writer.writeObjectKeyValue(
                self,
                "customValue3",
                condition="if_true",
                keyName="interpolationCustom3",
            )
            writer.writeObjectKeyValue(
                self, "weightValue", keyName="interpolationWeight", default=100
            )
            writer.writeObjectKeyValue(
                self, "widthValue", keyName="interpolationWidth", default=100
            )
        writer.writeObjectKeyValue(self, "instanceInterpolations", "if_true")
        writer.writeObjectKeyValue(self, "isBold", "if_true")
        writer.writeObjectKeyValue(self, "isItalic", "if_true")
        writer.writeObjectKeyValue(self, "linkStyle", "if_true")
        writer.writeObjectKeyValue(self, "manualInterpolation", "if_true")
        writer.writeObjectKeyValue(self, "name")
        writer.writeObjectKeyValue(
            self, "weight", default="Regular", keyName="weightClass"
        )
        writer.writeObjectKeyValue(
            self, "width", default="Medium (normal)", keyName="widthClass"
        )

    _axis_defaults = (100, 100)

    _defaultsForName = {
        "active": True,
        "exports": True,
        "weightClass": "Regular",
        "widthClass": "Medium (normal)",
        "instanceInterpolations": {},
    }

    def __init__(self):
        self.axes = list(self._axis_defaults)
        self._customParameters = []
        self.active = self._defaultsForName["active"]
        self.custom = None
        self.instanceInterpolations = copy.deepcopy(
            self._defaultsForName["instanceInterpolations"]
        )
        self.isBold = False
        self.isItalic = False
        self.linkStyle = ""
        self.manualInterpolation = False
        self.name = "Regular"
        self.properties = []
        self.visible = True
        self.weight = self._defaultsForName["weightClass"]
        self.width = self._defaultsForName["widthClass"]

    customParameters = property(
        lambda self: CustomParametersProxy(self),
        lambda self, value: CustomParametersProxy(self).setter(value),
    )

    @property
    def exports(self):
        """Deprecated alias for `active`, which is in the documentation."""
        return self.active

    @exports.setter
    def exports(self, value):
        self.active = value

    def _get_from_properties(self, key):
        for p in self.properties:
            if p.key == key:
                return p.defaultValue
        return None

    @property
    def familyName(self):
        value = (
            self._get_from_properties("familyNames")
            or self.customParameters["familyName"]
        )
        if value:
            return value
        return self.parent.familyName

    @familyName.setter
    def familyName(self, value):
        self.customParameters["familyName"] = value

    @property
    def preferredFamily(self):
        value = self.customParameters["preferredFamily"]
        if value:
            return value
        return self.parent.familyName

    @preferredFamily.setter
    def preferredFamily(self, value):
        self.customParameters["preferredFamily"] = value

    @property
    def preferredSubfamilyName(self):
        value = self.customParameters["preferredSubfamilyName"]
        if value:
            return value
        return self.name

    @preferredSubfamilyName.setter
    def preferredSubfamilyName(self, value):
        self.customParameters["preferredSubfamilyName"] = value

    @property
    def windowsFamily(self):
        value = self.customParameters["styleMapFamilyName"]
        if value:
            return value
        if self.name not in ("Regular", "Bold", "Italic", "Bold Italic"):
            return self.familyName + " " + self.name
        else:
            return self.familyName

    @windowsFamily.setter
    def windowsFamily(self, value):
        self.customParameters["styleMapFamilyName"] = value

    @property
    def windowsStyle(self):
        if self.name in ("Regular", "Bold", "Italic", "Bold Italic"):
            return self.name
        else:
            return "Regular"

    @property
    def windowsLinkedToStyle(self):
        value = self.linkStyle
        return value
        if self.name in ("Regular", "Bold", "Italic", "Bold Italic"):
            return self.name
        else:
            return "Regular"

    @property
    def fontName(self):
        value = self.customParameters["postscriptFontName"]
        if value:
            return value
        # TODO: strip invalid characters
        return "".join(self.familyName.split(" ")) + "-" + self.name

    @fontName.setter
    def fontName(self, value):
        self.customParameters["postscriptFontName"] = value

    @property
    def fullName(self):
        value = self.customParameters["postscriptFullName"]
        if value:
            return value
        return self.familyName + " " + self.name

    @fullName.setter
    def fullName(self, value):
        self.customParameters["postscriptFullName"] = value

    # v2 compatibility
    def _get_axis_value(self, index):
        if index < len(self.axes):
            return self.axes[index]
        if index < len(self._axis_defaults):
            return self._axis_defaults[index]
        return 0

    def _set_axis_value(self, index, value):
        if index < len(self.axes):
            self.axes[index] = value
            return
        for j in range(len(self.axes), index):
            if j < len(self._axis_defaults):
                self.axes.append(self._axis_defaults[j])
            else:
                self.axes.append(0)
        self.axes.append(value)

    @property
    def weightValue(self):
        return self._get_axis_value(0)

    @weightValue.setter
    def weightValue(self, value):
        return self._set_axis_value(0, value)

    @property
    def widthValue(self):
        return self._get_axis_value(1)

    @widthValue.setter
    def widthValue(self, value):
        return self._set_axis_value(1, value)

    @property
    def customValue(self):
        return self._get_axis_value(2)

    @customValue.setter
    def customValue(self, value):
        return self._set_axis_value(2, value)

    @property
    def customValue1(self):
        return self._get_axis_value(3)

    @customValue1.setter
    def customValue1(self, value):
        return self._set_axis_value(3, value)

    @property
    def customValue2(self):
        return self._get_axis_value(4)

    @customValue2.setter
    def customValue2(self, value):
        return self._set_axis_value(4, value)

    @property
    def customValue3(self):
        return self._get_axis_value(5)

    @customValue3.setter
    def customValue3(self, value):
        return self._set_axis_value(5, value)


GSInstance._add_parsers(
    [
        {"plist_name": "customParameters", "type": GSCustomParameter},
        {"plist_name": "instanceInterpolations", "type": dict},
        {"plist_name": "interpolationCustom", "object_name": "customValue"},
        {"plist_name": "interpolationCustom1", "object_name": "customValue1"},
        {"plist_name": "interpolationCustom2", "object_name": "customValue2"},
        {"plist_name": "interpolationCustom3", "object_name": "customValue3"},
        {"plist_name": "interpolationWeight", "object_name": "weightValue"},
        {"plist_name": "interpolationWidth", "object_name": "widthValue"},
        {"plist_name": "weightClass", "object_name": "weight"},
        {"plist_name": "widthClass", "object_name": "width"},
        {"plist_name": "axesValues", "object_name": "axes"},
        {"plist_name": "manualInterpolation", "converter": bool},
        {"plist_name": "properties", "type": GSFontInfoValue},
    ]
)


class GSBackgroundImage(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "_alpha", keyName="alpha", default=50)
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "rotation", keyName="angle", default=0)
            writer.writeObjectKeyValue(self, "crop", default=Rect())
        else:
            writer.writeObjectKeyValue(self, "crop")
        writer.writeObjectKeyValue(self, "imagePath")
        writer.writeObjectKeyValue(self, "locked", "if_true")
        if writer.format_version > 2:
            if self.position != Point(0, 0):
                writer.writeObjectKeyValue(self, "position", keyName="pos")
            if self.scale != (1.0, 1.0):
                writer.writeKeyValue("scale", Point(list(self.scale)))
        else:
            writer.writeObjectKeyValue(
                self, "transform", default=Transform(1, 0, 0, 1, 0, 0)
            )

    _defaultsForName = {"alpha": 50, "transform": Transform(1, 0, 0, 1, 0, 0)}

    def __init__(self, path=None):
        self._R = 0.0
        self._sX = 1.0
        self._sY = 1.0
        self.alpha = self._defaultsForName["alpha"]
        self.crop = Rect()
        self.imagePath = path
        self.locked = False
        self.transform = copy.deepcopy(self._defaultsForName["transform"])

    def __repr__(self):
        return "<GSBackgroundImage '%s'>" % self.imagePath

    # .path
    @property
    def path(self):
        return self.imagePath

    @path.setter
    def path(self, value):
        # FIXME: (jany) use posix pathnames here?
        # FIXME: (jany) the following code must have never been tested.
        #   Also it would require to keep track of the parent for background
        #   images.
        # if os.path.dirname(os.path.abspath(value)) == \
        #       os.path.dirname(os.path.abspath(self.parent.parent.parent.filepath)):
        #     self.imagePath = os.path.basename(value)
        # else:
        self.imagePath = value

    # .position
    @property
    def position(self):
        return Point(self.transform[4], self.transform[5])

    @position.setter
    def position(self, value):
        self.transform[4] = value[0]
        self.transform[5] = value[1]

    # .scale
    @property
    def scale(self):
        return self._sX, self._sY

    @scale.setter
    def scale(self, value):
        if type(value) in [int, float]:
            self._sX = value
            self._sY = value
        elif type(value) in [tuple, list] and len(value) == 2:
            self._sX, self._sY = value
        else:
            raise ValueError
        self.updateAffineTransform()

    # .rotation
    @property
    def rotation(self):
        return self._R

    @rotation.setter
    def rotation(self, value):
        self._R = value
        self.updateAffineTransform()

    # .alpha
    @property
    def alpha(self):
        return self._alpha

    @alpha.setter
    def alpha(self, value):
        if not 10 <= value <= 100:
            value = 50
        self._alpha = value

    def updateAffineTransform(self):
        affine = list(
            Affine.translation(self.transform[4], self.transform[5])
            * Affine.scale(self._sX, self._sY)
            * Affine.rotation(self._R)
        )[:6]
        self.transform = Transform(
            affine[0], affine[1], affine[3], affine[4], affine[2], affine[5]
        )


GSBackgroundImage._add_parsers(
    [
        {"plist_name": "transform", "converter": Transform},
        {"plist_name": "crop", "converter": Rect},
        {"plist_name": "locked", "converter": bool},
        {"plist_name": "angle", "object_name": "rotation"},
        {"plist_name": "pos", "object_name": "position"},
    ]
)


class LayerPathsProxy(LayerShapesProxy):
    _filter = GSPath


class LayerComponentsProxy(LayerShapesProxy):
    _filter = GSComponent


class GSLayer(GSBase):
    def _serialize_to_plist(self, writer):
        writer.writeObjectKeyValue(self, "anchors", "if_true")
        writer.writeObjectKeyValue(self, "annotations", "if_true")
        if self.layerId != self.associatedMasterId:
            writer.writeObjectKeyValue(self, "associatedMasterId")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "attributes", "if_true", keyName="attr")
        writer.writeObjectKeyValue(self, "background", self._background is not None)
        writer.writeObjectKeyValue(self, "backgroundImage")
        writer.writeObjectKeyValue(self, "color")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "components", "if_true")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "guides", "if_true")
        elif self.guides:
            writer.writeKeyValue("guideLines", self.guides)
        writer.writeObjectKeyValue(self, "hints", "if_true")
        writer.writeObjectKeyValue(self, "layerId", "if_true")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "metricLeft", keyName="leftMetricsKey")
            writer.writeObjectKeyValue(self, "metricWidth", keyName="widthMetricsKey")
            writer.writeObjectKeyValue(self, "metricRight", keyName="rightMetricsKey")
        else:
            writer.writeObjectKeyValue(self, "metricLeft")
            writer.writeObjectKeyValue(self, "metricRight")
            writer.writeObjectKeyValue(self, "metricWidth")
        if (
            self.name is not None
            and len(self.name) > 0
            and self.layerId != self.associatedMasterId
        ):
            writer.writeObjectKeyValue(self, "name")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "partSelection", "if_true")
            if self._shapes:
                writer.writeKeyValue("shapes", self._shapes)
        else:
            writer.writeObjectKeyValue(self, "paths", "if_true")
        writer.writeObjectKeyValue(self, "userData", "if_true")
        writer.writeObjectKeyValue(self, "visible", "if_true")
        writer.writeObjectKeyValue(self, "vertOrigin")
        writer.writeObjectKeyValue(self, "vertWidth")
        writer.writeObjectKeyValue(
            self, "width", not isinstance(self, GSBackgroundLayer)
        )

    def _parse_shapes_dict(self, parser, shapes):
        for shape_dict in shapes:
            if "ref" in shape_dict:
                shape = parser._parse_dict(shape_dict, GSComponent)
                self.components.append(shape)
            else:
                shape = parser._parse_dict(shape_dict, GSPath)
                self.paths.append(shape)

    _defaultsForName = {
        "width": 600,
        "metricLeft": None,
        "metricRight": None,
        "metricWidth": None,
        "vertWidth": None,
        "vertOrigin": None,
    }

    def _parse_background_dict(self, parser, value):
        self._background = parser._parse(value, GSBackgroundLayer)
        self._background._foreground = self
        self._background.parent = self.parent

    def __init__(self):
        self._anchors = []
        self._annotations = []
        self._background = None
        self._foreground = None
        self._guides = []
        self._hints = []
        self._layerId = ""
        self._name = ""
        self._selection = []
        self._shapes = []
        self._userData = None
        self.attributes = {}
        self.partSelection = {}
        self.associatedMasterId = ""
        self.backgroundImage = None
        self.color = None
        self.metricLeft = self._defaultsForName["metricLeft"]
        self.parent = None
        self.metricRight = self._defaultsForName["metricRight"]
        self.vertOrigin = self._defaultsForName["vertOrigin"]
        self.vertWidth = self._defaultsForName["vertWidth"]
        self.visible = False
        self.width = self._defaultsForName["width"]
        self.metricWidth = self._defaultsForName["metricWidth"]

    def __repr__(self):
        name = self.name
        try:
            # assert self.name
            name = self.name
        except AttributeError:
            name = "orphan (n)"
        try:
            assert self.parent.name
            parent = self.parent.name
        except (AttributeError, AssertionError):
            parent = "orphan"
        return f'<{self.__class__.__name__} "{name}" ({parent})>'

    def __lt__(self, other):
        if self.master and other.master and self.associatedMasterId == self.layerId:
            return (
                self.master.weightValue < other.master.weightValue
                or self.master.widthValue < other.master.widthValue
            )

    @property
    def layerId(self):
        return self._layerId

    @layerId.setter
    def layerId(self, value):
        self._layerId = value
        # Update the layer map in the parent glyph, if any.
        # The "hasattr" is here because this setter is called by the GSBase
        # __init__() method before the parent property is set.
        if hasattr(self, "parent") and self.parent:
            parent_layers = OrderedDict()
            updated = False
            for id, layer in self.parent._layers.items():
                if layer == self:
                    parent_layers[self._layerId] = self
                    updated = True
                else:
                    parent_layers[id] = layer
            if not updated:
                parent_layers[self._layerId] = self
            self.parent._layers = parent_layers

    @property
    def master(self):
        if self.associatedMasterId and self.parent:
            master = self.parent.parent.masterForId(self.associatedMasterId)
            return master

    @property
    def name(self):
        if (
            self.associatedMasterId
            and self.associatedMasterId == self.layerId
            and self.parent
        ):
            master = self.parent.parent.masterForId(self.associatedMasterId)
            if master:
                return master.name
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    anchors = property(
        lambda self: LayerAnchorsProxy(self),
        lambda self, value: LayerAnchorsProxy(self).setter(value),
    )

    hints = property(
        lambda self: LayerHintsProxy(self),
        lambda self, value: LayerHintsProxy(self).setter(value),
    )

    paths = property(
        lambda self: LayerPathsProxy(self),
        lambda self, value: LayerPathsProxy(self).setter(value),
    )

    components = property(
        lambda self: LayerComponentsProxy(self),
        lambda self, value: LayerComponentsProxy(self).setter(value),
    )

    guides = property(
        lambda self: LayerGuideLinesProxy(self),
        lambda self, value: LayerGuideLinesProxy(self).setter(value),
    )

    annotations = property(
        lambda self: LayerAnnotationProxy(self),
        lambda self, value: LayerAnnotationProxy(self).setter(value),
    )

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value),
    )

    @property
    def smartComponentPoleMapping(self):
        if "PartSelection" not in self.userData:
            self.userData["PartSelection"] = {}
        return self.userData["PartSelection"]

    @smartComponentPoleMapping.setter
    def smartComponentPoleMapping(self, value):
        self.userData["PartSelection"] = value

    @property
    def bounds(self):
        left, bottom, right, top = None, None, None, None

        for item in self.paths.values() + self.components.values():

            newLeft, newBottom, newWidth, newHeight = item.bounds
            newRight = newLeft + newWidth
            newTop = newBottom + newHeight

            if left is None:
                left = newLeft
            else:
                left = min(left, newLeft)
            if bottom is None:
                bottom = newBottom
            else:
                bottom = min(bottom, newBottom)
            if right is None:
                right = newRight
            else:
                right = max(right, newRight)
            if top is None:
                top = newTop
            else:
                top = max(top, newTop)

        if (
            left is not None
            and bottom is not None
            and right is not None
            and top is not None
        ):
            return Rect(Point(left, bottom), Point(right - left, top - bottom))

    def _find_node_by_indices(self, point):
        """ "Find the GSNode that is refered to by the given indices.

        See GSNode::_indices()
        """
        path_index, node_index = point
        path = self.paths[int(path_index)]
        node = path.nodes[int(node_index)]
        return node

    @property
    def background(self):
        """Only a getter on purpose. See the tests."""
        if self._background is None:
            self._background = GSBackgroundLayer()
            self._background._foreground = self
            self._background.parent = self.parent
        return self._background

    # FIXME: (jany) how to check whether there is a background without calling
    #               ::background?
    @property
    def hasBackground(self):
        return bool(self._background)

    @property
    def foreground(self):
        """Forbidden, and also forbidden to set it."""
        raise AttributeError

    def getPen(self) -> AbstractPen:
        """Returns a pen for others to draw into self."""
        pen = SegmentToPointPen(self.getPointPen())
        return pen

    def getPointPen(self) -> AbstractPointPen:
        """Returns a point pen for others to draw points into self."""
        pointPen = LayerPointPen(self)
        return pointPen

    def draw(self, pen: AbstractPen) -> None:
        """Draws glyph with the given pen."""
        pointPen = PointToSegmentPen(pen)
        self.drawPoints(pointPen)

    def drawPoints(self, pointPen: AbstractPointPen) -> None:
        """Draws points of glyph with the given point pen."""
        for path in self.paths:
            path.drawPoints(pointPen)
        for component in self.components:
            component.drawPoints(pointPen)

    @property
    def rightMetricsKey(self):
        return self.metricRight

    @property
    def leftMetricsKey(self):
        return self.metricLeft

    @property
    def widthMetricsKey(self):
        return self.metricWidth

    @rightMetricsKey.setter
    def rightMetricsKey(self, value):
        self.metricRight = value

    @leftMetricsKey.setter
    def leftMetricsKey(self, value):
        self.metricLeft = value

    @widthMetricsKey.setter
    def widthMetricsKey(self, value):
        self.metricWidth = value

    BRACKET_LAYER_RE = re.compile(
        r".*(?P<first_bracket>[\[\]])\s*(?P<value>\d+)\s*\].*"
    )

    def _is_bracket_layer(self):
        if self.parent.parent.format_version > 2:
            return "axisRules" in self.attributes  # Glyphs 3
        return re.match(self.BRACKET_LAYER_RE, self.name)  # Glyphs 2

    def _bracket_info(self):
        if not self._is_bracket_layer():
            return None

        if self.parent.parent.format_version > 2:
            # Glyphs 3
            rules = self.attributes["axisRules"]
            if any(rules[1:]):
                raise ValueError("Alternate rules on non-first axis not yet supported")
            return 0, rules[0].get("min"), rules[0].get("max")

        # Glyphs 2
        m = re.match(self.BRACKET_LAYER_RE, self.name)
        axis_index = 0  # For glyphs 2
        reverse = m.group("first_bracket") == "]"
        bracket_crossover = int(m.group("value"))
        if reverse:
            return axis_index, None, bracket_crossover
        else:
            return axis_index, bracket_crossover, None

    def _is_brace_layer(self):
        if self.parent.parent.format_version > 2:
            return "coordinates" in self.attributes  # Glyphs 3
        # Glyphs 2
        return "{" in self.name and "}" in self.name and ".background" not in self.name

    def _brace_coordinates(self):
        if not self._is_brace_layer():
            return None

        if self.parent.parent.format_version > 2:
            return self.attributes["coordinates"]  # Glyphs 3

        # Glyphs 2
        name = self.name
        coordinates = name[name.index("{") + 1 : name.index("}")]
        return [float(c) for c in coordinates.split(",")]

    COLOR_PALETTE_LAYER_RE = re.compile(r"^Color (?P<index>\*|\d+)$")

    def _is_color_palette_layer(self):
        if self.parent.parent.format_version > 2:
            return "colorPalette" in self.attributes  # Glyphs 3
        return re.match(self.COLOR_PALETTE_LAYER_RE, self.name.strip())  # Glyphs 2

    def _color_palette_index(self):
        if not self._is_color_palette_layer():
            return None

        if self.parent.parent.format_version > 2:
            # Glyphs 3
            index = self.attributes["colorPalette"]
            if index == "*":
                return 0xFFFF
            return index

        # Glyphs 2
        m = re.match(self.COLOR_PALETTE_LAYER_RE, self.name)
        index = m.group("index")
        if index.startswith("*"):
            return 0xFFFF
        return int(index)


GSLayer._add_parsers(
    [
        {
            "plist_name": "annotations",
            "object_name": "_annotations",
            "type": GSAnnotation,
        },
        {"plist_name": "backgroundImage", "type": GSBackgroundImage},
        {"plist_name": "paths", "type": GSPath},
        {"plist_name": "anchors", "type": GSAnchor},
        {"plist_name": "guideLines", "object_name": "guides", "type": GSGuide},  # V2
        {"plist_name": "guides", "type": GSGuide},  # V3
        {"plist_name": "components", "type": GSComponent},
        {"plist_name": "hints", "type": GSHint},
        {"plist_name": "userData", "object_name": "_userData", "type": dict},
        {"plist_name": "partSelection", "object_name": "partSelection", "type": dict},
        {
            "plist_name": "leftMetricsKey",
            "object_name": "metricLeft",
            "type": str,
        },  # V2
        {
            "plist_name": "rightMetricsKey",
            "object_name": "metricRight",
            "type": str,
        },  # V2
        {
            "plist_name": "widthMetricsKey",
            "object_name": "metricWidth",
            "type": str,
        },  # V2
        {"plist_name": "attr", "object_name": "attributes", "type": dict},  # V3
    ]
)


class GSBackgroundLayer(GSLayer):
    @property
    def background(self):
        return None

    @property
    def foreground(self):
        return self._foreground

    # The width property of this class behaves like this in Glyphs:
    #  - Always returns 600.0
    #  - Settable but does not remember the value (basically useless)
    # Reproduce this behaviour here so that the roundtrip does not rely on it.
    @property
    def width(self):
        return 600

    @width.setter
    def width(self, whatever):
        pass


class GSGlyph(GSBase):
    def _serialize_to_plist(self, writer):
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "case")
            writer.writeObjectKeyValue(self, "category")
        writer.writeObjectKeyValue(self, "color")
        writer.writeObjectKeyValue(self, "export", not self.export)
        writer.writeKeyValue("glyphname", self.name)
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "production", "if_true")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(
                self, "leftKerningGroup", "if_true", keyName="kernLeft"
            )
            writer.writeObjectKeyValue(
                self, "rightKerningGroup", "if_true", keyName="kernRight"
            )
        writer.writeObjectKeyValue(self, "lastChange")
        writer.writeObjectKeyValue(self, "layers", "if_true")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "metricLeft", "if_true")
            writer.writeObjectKeyValue(self, "metricWidth", "if_true")
        else:
            writer.writeObjectKeyValue(self, "leftKerningGroup", "if_true")
            writer.writeObjectKeyValue(
                self, "metricLeft", "if_true", keyName="leftMetricsKey"
            )
            writer.writeObjectKeyValue(
                self, "metricWidth", "if_true", keyName="widthMetricsKey"
            )
            writer.writeObjectKeyValue(
                self, "metricVertWidth", "if_true", keyName="vertWidthMetricsKey"
            )
        writer.writeObjectKeyValue(self, "note")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "metricRight", "if_true")
        else:
            writer.writeObjectKeyValue(self, "rightKerningGroup", "if_true")
            writer.writeObjectKeyValue(
                self, "metricRight", "if_true", keyName="rightMetricsKey"
            )
        writer.writeObjectKeyValue(self, "topKerningGroup", "if_true")
        writer.writeObjectKeyValue(self, "topMetricsKey", "if_true")
        writer.writeObjectKeyValue(self, "bottomKerningGroup", "if_true")
        writer.writeObjectKeyValue(self, "bottomMetricsKey", "if_true")
        if self.unicodes and writer.format_version == 2:
            writer.writeKeyValue("unicode", self.unicodes)
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "production", "if_true")
        writer.writeObjectKeyValue(self, "script")
        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "category")
        writer.writeObjectKeyValue(self, "subCategory")
        if writer.format_version > 2:
            writer.writeObjectKeyValue(self, "tags", "if_true")
        if self.unicodes and writer.format_version > 2:
            writer.writeKeyValue("unicode", self.unicodes)
        writer.writeObjectKeyValue(self, "userData", "if_true")
        if self.smartComponentAxes:
            writer.writeKeyValue("partsSettings", self.smartComponentAxes)

    _defaultsForName = {
        "category": None,
        "color": None,
        "export": True,
        "lastChange": None,
        "leftKerningGroup": None,
        "metricLeft": None,
        "name": None,
        "note": None,
        "rightKerningGroup": None,
        "metricRight": None,
        "script": None,
        "subCategory": None,
        "userData": None,
        "metricWidth": None,
        "metricVertWidth": None,
    }

    def _parse_unicode_dict(self, parser, value):
        parser.current_type = None
        if parser.format_version == 3:
            if not isinstance(value, list):
                value = [value]
            uni = ["%x" % x for x in value]
        elif isinstance(value, int):
            # This is unfortunate. We've used the openstep_plist parser with
            # use_numbers=True, and it's seen something like "0041". It's
            # then interpreted this as a *decimal* integer. We have to make it
            # look like a hex string again
            uni = ["%04i" % value]
        else:
            uni = value
        self["_unicodes"] = UnicodesList(uni)

    def _parse_layers_dict(self, parser, value):
        layers = parser._parse(value, GSLayer)
        for l in layers:
            self.layers.append(l)
        return 0

    def __init__(self, name=None):
        self._layers = OrderedDict()
        self._unicodes = []
        self.bottomKerningGroup = ""
        self.bottomMetricsKey = ""
        self.category = self._defaultsForName["category"]
        self.case = None
        self.color = self._defaultsForName["color"]
        self.export = self._defaultsForName["export"]
        self.lastChange = self._defaultsForName["lastChange"]
        self.leftKerningGroup = self._defaultsForName["leftKerningGroup"]
        self.leftKerningKey = ""
        self.metricLeft = self._defaultsForName["metricLeft"]
        self.name = name
        self.note = self._defaultsForName["note"]
        self.parent = None
        self.partsSettings = []
        self.production = ""
        self.rightKerningGroup = self._defaultsForName["rightKerningGroup"]
        self.rightKerningKey = ""
        self.metricRight = self._defaultsForName["metricRight"]
        self.script = self._defaultsForName["script"]
        self.selected = False
        self.subCategory = self._defaultsForName["subCategory"]
        self.tags = []
        self.topKerningGroup = ""
        self.topMetricsKey = ""
        self.userData = self._defaultsForName["userData"]
        self.vertWidthMetricsKey = ""
        self.metricVertWidth = self._defaultsForName["metricVertWidth"]
        self.metricWidth = self._defaultsForName["metricWidth"]

    def __repr__(self):
        return '<GSGlyph "{}" with {} layers>'.format(self.name, len(self.layers))

    layers = property(
        lambda self: GlyphLayerProxy(self),
        lambda self, value: GlyphLayerProxy(self).setter(value),
    )

    def _setupLayer(self, layer, key):
        assert isinstance(key, str)
        layer.parent = self
        if layer.hasBackground:
            layer._background.parent = self
        layer.layerId = key
        # TODO use proxy `self.parent.masters[key]`
        if self.parent and self.parent.masterForId(key):
            layer.associatedMasterId = key

    # def setLayerForKey(self, layer, key):
    #     if Layer and Key:
    #         Layer.parent = self
    #         Layer.layerId = Key
    #         if self.parent.fontMasterForId(Key):
    #             Layer.associatedMasterId = Key
    #         self._layers[key] = layer

    def removeLayerForKey_(self, key):
        for layer in list(self._layers):
            if layer == key:
                del self._layers[key]

    @property
    def string(self):
        if self.unicode:
            return chr(int(self.unicode, 16))

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value),
    )

    @property
    def glyphname(self):
        return self.name

    @glyphname.setter
    def glyphname(self, value):
        self.name = value

    @property
    def smartComponentAxes(self):
        return self.partsSettings

    @smartComponentAxes.setter
    def smartComponentAxes(self, value):
        self.partsSettings = value

    @property
    def id(self):
        """An unique identifier for each glyph"""
        return self.name

    @property
    def unicode(self):
        if self._unicodes:
            return self._unicodes[0]
        return None

    @unicode.setter
    def unicode(self, unicode):
        self._unicodes = UnicodesList(unicode)

    @property
    def unicodes(self):
        return self._unicodes

    @unicodes.setter
    def unicodes(self, unicodes):
        self._unicodes = UnicodesList(unicodes)

    # V2 compatible interface
    @property
    def rightMetricsKey(self):
        return self.metricRight

    @rightMetricsKey.setter
    def rightMetricsKey(self, value):
        self.metricRight = value

    @property
    def leftMetricsKey(self):
        return self.metricLeft

    @leftMetricsKey.setter
    def leftMetricsKey(self, value):
        self.metricLeft = value

    @property
    def widthMetricsKey(self):
        return self.metricWidth

    @widthMetricsKey.setter
    def widthMetricsKey(self, value):
        self.metricWidth = value

    @property
    def vertWidthMetricsKey(self):
        return self.metricVertWidth

    @vertWidthMetricsKey.setter
    def vertWidthMetricsKey(self, value):
        self.metricVertWidth = value


GSGlyph._add_parsers(
    [
        {"plist_name": "glyphname", "object_name": "name"},
        {
            "plist_name": "partsSettings",
            "object_name": "partsSettings",
            "type": GSSmartComponentAxis,
        },
        {"plist_name": "export", "object_name": "export", "converter": bool},
        {
            "plist_name": "lastChange",
            "object_name": "lastChange",
            "converter": parse_datetime,
        },
        {"plist_name": "kernLeft", "object_name": "leftKerningGroup"},  # V3
        {"plist_name": "kernRight", "object_name": "rightKerningGroup"},  # V3
        {"plist_name": "leftMetricsKey", "object_name": "metricLeft"},  # V2
        {"plist_name": "rightMetricsKey", "object_name": "metricRight"},  # V2
        {"plist_name": "widthMetricsKey", "object_name": "metricWidth"},  # V2
        {"plist_name": "vertWidthMetricsKey", "object_name": "metricVertWidth"},  # V2
    ]
)


class GSFont(GSBase):
    _defaultsForName = {
        "classes": [],
        "features": [],
        "featurePrefixes": [],
        "customParameters": [],
        "disablesAutomaticAlignment": False,
        "disablesNiceNames": False,
        "gridLength": 1,
        "gridSubDivision": 1,
        "unitsPerEm": 1000,
        "kerning": OrderedDict(),
        "keyboardIncrement": 1,
    }

    def _serialize_to_plist(self, writer):
        writer.writeKeyValue(".appVersion", self.appVersion)
        if self.format_version > 2:
            writer.writeKeyValue(".formatVersion", self.format_version)

        writer.writeObjectKeyValue(self, "DisplayStrings", "if_true")

        if writer.format_version == 3:
            writer.writeObjectKeyValue(self, "axes", "if_true")
        writer.writeObjectKeyValue(self, "classes", "if_true")

        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "copyright", "if_true")

        writer.writeObjectKeyValue(self, "customParameters", "if_true")
        writer.writeObjectKeyValue(self, "date")

        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "designer", "if_true")
            writer.writeObjectKeyValue(self, "designerURL", "if_true")
            writer.writeObjectKeyValue(self, "disablesAutomaticAlignment", "if_true")
            writer.writeObjectKeyValue(self, "disablesNiceNames", "if_true")

        writer.writeObjectKeyValue(self, "familyName")
        if self.featurePrefixes:
            writer.writeObjectKeyValue(self, "featurePrefixes")
        if self.features:
            writer.writeObjectKeyValue(self, "features")
        writer.writeKeyValue("fontMaster", self.masters)
        writer.writeObjectKeyValue(self, "glyphs")

        if writer.format_version == 2:
            if self.grid != 1:
                writer.writeKeyValue("gridLength", self.grid)
            if self.gridSubDivisions != 1:
                writer.writeKeyValue("gridSubDivision", self.gridSubDivisions)

        writer.writeObjectKeyValue(self, "instances")

        if writer.format_version == 2:
            writer.writeObjectKeyValue(self, "keepAlternatesTogether", "if_true")
            if self.kerningLTR:
                writer.writeKeyValue("kerning", self.kerningLTR)
        else:
            writer.writeObjectKeyValue(self, "kerningLTR")
            writer.writeObjectKeyValue(self, "kerningRTL", "if_true")
            writer.writeObjectKeyValue(self, "kerningVertical", "if_true")

        if writer.format_version == 2:
            writer.writeObjectKeyValue(
                self, "keyboardIncrement", self.keyboardIncrement != 1
            )
            writer.writeObjectKeyValue(self, "manufacturer", "if_true")
            writer.writeObjectKeyValue(self, "manufacturerURL", "if_true")

        if writer.format_version == 3:
            writer.writeObjectKeyValue(self, "metrics")
            writer.writeObjectKeyValue(self, "_note", "if_true", keyName="note")
            writer.writeObjectKeyValue(self, "numbers", "if_true")
            writer.writeObjectKeyValue(self, "properties", "if_true")
            writer.writeObjectKeyValue(self, "settings", "if_true")
            writer.writeObjectKeyValue(self, "stems")

        writer.writeKeyValue("unitsPerEm", self.upm or 1000)
        writer.writeObjectKeyValue(self, "userData", "if_true")
        writer.writeObjectKeyValue(self, "versionMajor")
        writer.writeObjectKeyValue(self, "versionMinor")

    _defaultMetrics = [
        GSMetric(type="ascender"),
        GSMetric(type="cap height"),
        GSMetric(type="x-height"),
        GSMetric(type="baseline"),
        GSMetric(type="descender"),
        GSMetric(type="italic angle"),
    ]
    _defaultAxes = [GSAxis(name="Weight", tag="wght"), GSAxis(name="Width", tag="wdth")]

    def _parse_glyphs_dict(self, parser, value):
        glyphs = parser._parse(value, GSGlyph)
        for l in glyphs:
            self.glyphs.append(l)
        return 0

    def _parse_customParameters_dict(self, parser, value):
        _customParameters = parser._parse(value, GSCustomParameter)
        for cp in _customParameters:
            self.customParameters[cp.name] = cp.value  # This will intercept axes

    def _parse_settings_dict(self, parser, settings):
        self.disablesAutomaticAlignment = bool(
            settings.get("disablesAutomaticAlignment", False)
        )
        self.disablesNiceNames = bool(settings.get("disablesNiceNames", False))
        self.grid = settings.get("gridLength", 1)
        self.gridSubDivisions = settings.get("gridSubDivision", 1)
        self.keepAlternatesTogether = bool(
            settings.get("keepAlternatesTogether", False)
        )
        self.keyboardIncrement = settings.get("keyboardIncrement", 1)
        self.keyboardIncrementBig = settings.get("keyboardIncrementBig", 10)
        self.keyboardIncrementHuge = settings.get("keyboardIncrementHuge", 100)

    def _parse___formatVersion_dict(self, parser, val):
        self.format_version = parser.format_version = val

    def __init__(self, path=None):
        self.DisplayStrings = ""
        self._glyphs = []
        self._instances = []
        self._masters = []
        self.axes = copy.deepcopy(self._defaultAxes)
        self._userData = None
        self._versionMinor = 0
        self.format_version = 2
        self.appVersion = "895"  # minimum required version
        self.classes = copy.deepcopy(self._defaultsForName["classes"])
        self.features = copy.deepcopy(self._defaultsForName["features"])
        self.featurePrefixes = copy.deepcopy(self._defaultsForName["featurePrefixes"])
        self.customParameters = copy.deepcopy(self._defaultsForName["customParameters"])
        self.date = None
        self.disablesAutomaticAlignment = self._defaultsForName[
            "disablesAutomaticAlignment"
        ]
        self.disablesNiceNames = self._defaultsForName["disablesNiceNames"]
        self.familyName = "Unnamed font"
        self.filepath = None
        self.grid = self._defaultsForName["gridLength"]
        self.gridSubDivisions = self._defaultsForName["gridSubDivision"]
        self.keepAlternatesTogether = False
        self._kerningLTR = OrderedDict()
        self._kerningRTL = OrderedDict()
        self._kerningVertical = OrderedDict()
        self.keyboardIncrement = self._defaultsForName["keyboardIncrement"]
        self.metrics = copy.deepcopy(self._defaultMetrics)
        self.numbers = []
        self.properties = []
        self.stems = []
        self.keepAlternatesTogether = False
        self.keyboardIncrement = 1
        self.keyboardIncrementBig = 10
        self.keyboardIncrementHuge = 100
        self.upm = self._defaultsForName["unitsPerEm"]
        self.versionMajor = 1
        self._note = ""

        if path:
            path = os.fsdecode(os.fspath(path))
            assert os.path.splitext(path)[-1] == ".glyphs", (
                "Please supply a file path to a .glyphs file",
            )

            with open(path, "r", encoding="utf-8") as fp:
                logger.info('Parsing "%s" file into <GSFont>', path)
                p = Parser()
                p.parse_into_object(self, openstep_plist.load(fp, use_numbers=True))
            self.filepath = path
            for master in self.masters:
                master.font = self

    def __repr__(self):
        return f'<{self.__class__.__name__} "{self.familyName}">'

    def save(self, path=None):
        if path is None:
            if self.filepath:
                path = self.filepath
            else:
                raise ValueError("No path provided and GSFont has no filepath")
        with open(path, "w", encoding="utf-8") as fp:
            w = Writer(fp, format_version=self.format_version)
            logger.info("Writing %r to .glyphs file", self)
            w.write(self)

    def getVersionMinor(self):
        return self._versionMinor

    def setVersionMinor(self, value):
        """Ensure that the minor version number is between 0 and 999."""
        assert 0 <= value <= 999
        self._versionMinor = value

    versionMinor = property(getVersionMinor, setVersionMinor)

    glyphs = property(
        lambda self: FontGlyphsProxy(self),
        lambda self, value: FontGlyphsProxy(self).setter(value),
    )

    def _setupGlyph(self, glyph):
        glyph.parent = self
        for layer in glyph.layers:
            if (
                not hasattr(layer, "associatedMasterId")
                or layer.associatedMasterId is None
                or len(layer.associatedMasterId) == 0
            ):
                glyph._setupLayer(layer, layer.layerId)

    masters = property(
        lambda self: FontFontMasterProxy(self),
        lambda self, value: FontFontMasterProxy(self).setter(value),
    )

    def masterForId(self, key):
        for master in self._masters:
            if master.id == key:
                return master
        return None

    # FIXME: (jany) Why is this not a FontInstanceProxy?
    @property
    def instances(self):
        return self._instances

    @instances.setter
    def instances(self, value):
        self._instances = value
        for i in self._instances:
            i.parent = self

    classes = property(
        lambda self: FontClassesProxy(self),
        lambda self, value: FontClassesProxy(self).setter(value),
    )

    features = property(
        lambda self: FontFeaturesProxy(self),
        lambda self, value: FontFeaturesProxy(self).setter(value),
    )

    featurePrefixes = property(
        lambda self: FontFeaturePrefixesProxy(self),
        lambda self, value: FontFeaturePrefixesProxy(self).setter(value),
    )

    customParameters = property(
        lambda self: CustomParametersProxy(self),
        lambda self, value: CustomParametersProxy(self).setter(value),
    )

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value),
    )

    @property
    def kerning(self):
        return self._kerningLTR

    @kerning.setter
    def kerning(self, kerning):
        self.kerningLTR = kerning

    @property
    def kerningLTR(self):
        return self._kerningLTR

    @kerningLTR.setter
    def kerningLTR(self, kerning):
        self._kerningLTR = kerning
        for master_map in kerning.values():
            for glyph_map in master_map.values():
                for right_glyph, value in glyph_map.items():
                    glyph_map[right_glyph] = parse_float_or_int(value)

    @property
    def kerningRTL(self):
        return self._kerningRTL

    @kerningRTL.setter
    def kerningRTL(self, kerning):
        self._kerningRTL = kerning
        for master_map in kerning.values():
            for glyph_map in master_map.values():
                for right_glyph, value in glyph_map.items():
                    glyph_map[right_glyph] = parse_float_or_int(value)

    @property
    def kerningVertical(self):
        return self._kerningVertical

    @kerningVertical.setter
    def kerningVertical(self, kerning):
        self._kerningVertical = kerning
        for master_map in kerning.values():
            for glyph_map in master_map.values():
                for right_glyph, value in glyph_map.items():
                    glyph_map[right_glyph] = parse_float_or_int(value)

    @property
    def selection(self):
        return (glyph for glyph in self.glyphs if glyph.selected)

    @property
    def note(self):
        if self.format_version < 3:
            value = self.customParameters["note"]
            if value:
                return value
            else:
                return ""
        else:
            return self._note

    @note.setter
    def note(self, value):
        if self.format_version < 3:
            self.customParameters["note"] = value
        else:
            self._note = value

    @property
    def gridLength(self):
        if self.gridSubDivisions > 0:
            return self.grid / self.gridSubDivisions
        else:
            return self.grid

    EMPTY_KERNING_VALUE = (1 << 63) - 1  # As per the documentation

    def kerningForPair(self, fontMasterId, leftKey, rightKey, direction=LTR):
        if direction == LTR:
            kerntable = self._kerningLTR
        elif direction == RTL:
            kerntable = self._kerningRTL
        else:
            kerntable = self._kerningVertical
        if not kerntable:
            return self.EMPTY_KERNING_VALUE
        try:
            return kerntable[fontMasterId][leftKey][rightKey]
        except KeyError:
            return self.EMPTY_KERNING_VALUE

    def setKerningForPair(self, fontMasterId, leftKey, rightKey, value, direction=LTR):
        if direction == LTR:
            if not self._kerningLTR:
                self._kerningLTR = {}
            kerntable = self._kerningLTR
        elif direction == RTL:
            if not self._kerningRTL:
                self._kerningRTL = {}
            kerntable = self._kerningRTL
        else:
            if not self._kerningVertical:
                self._kerningVertical = {}
            kerntable = self._kerningVertical
        if fontMasterId not in kerntable:
            kerntable[fontMasterId] = {}
        if leftKey not in kerntable[fontMasterId]:
            kerntable[fontMasterId][leftKey] = {}
        kerntable[fontMasterId][leftKey][rightKey] = value

    def removeKerningForPair(self, fontMasterId, leftKey, rightKey, direction=LTR):
        if direction == LTR:
            kerntable = self._kerningLTR
        elif direction == RTL:
            kerntable = self._kerningRTL
        else:
            kerntable = self._kerningVertical
        if not kerntable:
            return
        if fontMasterId not in kerntable:
            return
        if leftKey not in kerntable[fontMasterId]:
            return
        if rightKey not in kerntable[fontMasterId][leftKey]:
            return
        del kerntable[fontMasterId][leftKey][rightKey]
        if not kerntable[fontMasterId][leftKey]:
            del kerntable[fontMasterId][leftKey]
        if not kerntable[fontMasterId]:
            del kerntable[fontMasterId]

    @property
    def manufacturer(self):
        return self._get_from_properties("manufacturers")

    @manufacturer.setter
    def manufacturer(self, value):
        self._set_in_properties("manufacturers", value)

    @property
    def manufacturerURL(self):
        return self._get_from_properties("manufacturerURL")

    @manufacturerURL.setter
    def manufacturerURL(self, value):
        self._set_in_properties("manufacturerURL", value)

    @property
    def copyright(self):
        return self._get_from_properties("copyrights")

    @copyright.setter
    def copyright(self, value):
        self._set_in_properties("copyrights", value)

    @property
    def designer(self):
        return self._get_from_properties("designers")

    @designer.setter
    def designer(self, value):
        self._set_in_properties("designers", value)

    @property
    def designerURL(self):
        return self._get_from_properties("designerURL")

    @designerURL.setter
    def designerURL(self, value):
        self._set_in_properties("designerURL", value)

    def _get_from_properties(self, key):
        for p in self.properties:
            if p.key == key:
                return p.defaultValue
        return ""

    def _set_in_properties(self, key, value):
        for p in self.properties:
            if p.key == key:
                p.localized_values = None
                p.value = value
                return
        newprop = GSFontInfoValue(key, value)
        self.properties.append(newprop)

    def _get_custom_parameter_from_axes(self):
        # We were specifically asked for our Axes custom parameter, so we
        # synthesise one.

        # However, if the axes are default, we don't synthesise one *unless*
        # we also have an Axis Mappings custom parameter.
        if (
            len(self.axes) == 2
            and self.axes[0] == self._defaultAxes[0]
            and self.axes[1] == self._defaultAxes[1]
        ) and "Axis Mappings" not in self.customParameters:
            return None
        values = []
        for ax in self.axes:
            value = {"Name": ax.name, "Tag": ax.axisTag}
            if ax.hidden:
                value["Hidden"] = 1
            values.append(value)
        return GSCustomParameter(name="Axes", value=values)

    def _set_axes_from_custom_parameter(self, value):
        self.axes = [
            GSAxis(name=v["Name"], tag=v["Tag"], hidden=v.get("Hidden", False))
            for v in value
        ]

    @property
    def settings(self):
        _settings = OrderedDict()
        if self.disablesAutomaticAlignment:
            _settings["disablesAutomaticAlignment"] = 1
        if self.disablesNiceNames:
            _settings["disablesNiceNames"] = 1
        if self.grid != 1:
            _settings["gridLength"] = self.grid
        if self.gridSubDivisions != 1:
            _settings["gridSubDivision"] = self.gridSubDivisions
        if self.keepAlternatesTogether:
            _settings["keepAlternatesTogether"] = 1
        if self.keyboardIncrement != 1:
            _settings["keyboardIncrement"] = self.keyboardIncrement
        if self.keyboardIncrementBig != 10:
            _settings["keyboardIncrementBig"] = self.keyboardIncrementBig
        if self.keyboardIncrementHuge != 100:
            _settings["keyboardIncrementHuge"] = self.keyboardIncrementHuge

        return _settings


GSFont._add_parsers(
    [
        {"plist_name": "unitsPerEm", "object_name": "upm"},
        {"plist_name": "gridLength", "object_name": "grid"},
        {"plist_name": "gridSubDivisions", "object_name": "gridSubDivision"},
        {"plist_name": "__appVersion", "object_name": "appVersion"},
        {"plist_name": "classes", "type": GSClass},
        {"plist_name": "instances", "type": GSInstance},
        {"plist_name": "featurePrefixes", "type": GSFeaturePrefix},
        {"plist_name": "features", "type": GSFeature},
        {"plist_name": "fontMaster", "object_name": "masters", "type": GSFontMaster},
        {"plist_name": "kerning", "object_name": "_kerningLTR", "type": OrderedDict},
        {"plist_name": "kerningLTR", "type": OrderedDict},
        {"plist_name": "kerningRTL", "type": OrderedDict},
        {"plist_name": "kerningVertical", "type": OrderedDict},
        {"plist_name": "date", "converter": parse_datetime},
        {"plist_name": "disablesAutomaticAlignment", "converter": bool},
        {"plist_name": "axes", "type": GSAxis},
        {"plist_name": "stems", "type": GSMetric},
        {"plist_name": "metrics", "type": GSMetric},
        {"plist_name": "numbers", "type": GSMetric},
        {"plist_name": "properties", "type": GSFontInfoValue},
        {"plist_name": "note", "object_name": "_note"},
    ]
)

Number = Union[int, float]


class LayerPointPen(AbstractPointPen):
    """A point pen to draw onto GSLayer object.

    See :mod:`fontTools.pens.basePen` and :mod:`fontTools.pens.pointPen` for an
    introduction to pens.
    """

    def __init__(self, layer: GSLayer) -> None:
        self._layer: GSLayer = layer
        self._path: Optional[GSPath] = None

    def beginPath(self, **kwargs: Any) -> None:
        if self._path is not None:
            raise ValueError("Call endPath first.")

        self._path = GSPath()
        self._path.closed = True  # Until proven otherwise.

    def endPath(self) -> None:
        if self._path is None:
            raise ValueError("Call beginPath first.")

        if self._path.closed:
            self._path.nodes.append(self._path.nodes.pop(0))
        self._layer.paths.append(self._path)
        self._path = None

    def addPoint(
        self,
        pt: Tuple[Number, Number],
        segmentType: Optional[str] = None,
        smooth: bool = False,
        name: Optional[str] = None,
        userData: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if self._path is None:
            raise ValueError("Call beginPath first.")

        if segmentType == "move":
            if self._path.nodes:
                raise ValueError("For an open contour, 'move' must come first.")
            self._path.closed = False

        node = GSNode(
            Point(*pt),
            nodetype=_to_glyphs_node_type(segmentType),
            smooth=smooth,
            name=name,
        )
        if userData:
            node.userData = userData
        self._path.nodes.append(node)

    def addComponent(
        self,
        baseGlyph: str,
        transformation: Union[
            Transform, Tuple[float, float, float, float, float, float]
        ],
        **kwargs: Any,
    ) -> None:
        if not isinstance(transformation, Transform):
            transformation = Transform(*transformation)
        component = GSComponent(baseGlyph, transform=transformation)
        self._layer.components.append(component)


def _to_glyphs_node_type(node_type):
    if node_type is None:
        return OFFCURVE
    if node_type == "move":
        return LINE
    return node_type
