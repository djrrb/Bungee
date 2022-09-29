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


import os
import logging

from glyphsLib.util import build_ufo_path
from glyphsLib.classes import WEIGHT_CODES, GSCustomParameter
from .constants import GLYPHS_PREFIX, GLYPHLIB_PREFIX, UFO_FILENAME_CUSTOM_PARAM
from .names import build_stylemap_names
from .axes import (
    get_axis_definitions,
    is_instance_active,
    interp,
    WEIGHT_AXIS_DEF,
    WIDTH_AXIS_DEF,
    AxisDefinitionFactory,
)
from .custom_params import to_ufo_custom_params

EXPORT_KEY = GLYPHS_PREFIX + "export"
WIDTH_KEY = GLYPHS_PREFIX + "width"
WEIGHT_KEY = GLYPHS_PREFIX + "weight"
FULL_FILENAME_KEY = GLYPHLIB_PREFIX + "fullFilename"
MANUAL_INTERPOLATION_KEY = GLYPHS_PREFIX + "manualInterpolation"
INSTANCE_INTERPOLATIONS_KEY = GLYPHS_PREFIX + "intanceInterpolations"
CUSTOM_PARAMETERS_KEY = GLYPHS_PREFIX + "customParameters"


logger = logging.getLogger(__name__)


def to_designspace_instances(self):
    """Write instance data from self.font to self.designspace."""
    for instance in self.font.instances:
        if self.minimize_glyphs_diffs or (
            is_instance_active(instance)
            and _is_instance_included_in_family(self, instance)
        ):
            _to_designspace_instance(self, instance)


def _to_designspace_instance(self, instance):
    ufo_instance = self.designspace.newInstanceDescriptor()
    # FIXME: (jany) most of these customParameters are actually attributes,
    # at least according to https://docu.glyphsapp.com/#fontName
    for p in instance.customParameters:
        param, value = p.name, p.value
        if param == "postscriptFontName":
            # Glyphs uses "postscriptFontName", not "postScriptFontName"
            ufo_instance.postScriptFontName = value
        elif param == "fileName":
            fname = value + ".ufo"
            if self.instance_dir is not None:
                fname = self.instance_dir + "/" + fname
            ufo_instance.filename = fname

    # Read either from properties or custom parameter or the font
    ufo_instance.familyName = instance.familyName
    ufo_instance.styleName = instance.name

    fname = (
        instance.customParameters[UFO_FILENAME_CUSTOM_PARAM]
        or instance.customParameters[FULL_FILENAME_KEY]
    )
    if fname is not None:
        if self.instance_dir:
            fname = self.instance_dir + "/" + os.path.basename(fname)
        ufo_instance.filename = fname
    if not ufo_instance.filename:
        instance_dir = self.instance_dir or "instance_ufos"
        ufo_instance.filename = build_ufo_path(
            instance_dir, ufo_instance.familyName, ufo_instance.styleName
        )

    designspace_axis_tags = {a.tag for a in self.designspace.axes}
    location = {}
    for axis_def in get_axis_definitions(self.font):
        # Only write locations along defined axes
        if axis_def.tag in designspace_axis_tags:
            location[axis_def.name] = axis_def.get_design_loc(instance)
    ufo_instance.location = location

    # FIXME: (jany) should be the responsibility of ufo2ft?
    # Anyway, only generate the styleMap names if the Glyphs instance already
    # has a linkStyle set up, or if we're not round-tripping (i.e. generating
    # UFOs for fontmake, the traditional use-case of glyphsLib.)
    if instance.linkStyle or not self.minimize_glyphs_diffs:
        styleMapFamilyName, styleMapStyleName = build_stylemap_names(
            family_name=ufo_instance.familyName,
            style_name=ufo_instance.styleName,
            is_bold=instance.isBold,
            is_italic=instance.isItalic,
            linked_style=instance.linkStyle,
        )
        ufo_instance.styleMapFamilyName = styleMapFamilyName
        ufo_instance.styleMapStyleName = styleMapStyleName

    ufo_instance.name = " ".join(
        (ufo_instance.familyName or "", ufo_instance.styleName or "")
    )

    if self.minimize_glyphs_diffs:
        ufo_instance.lib[EXPORT_KEY] = instance.active
        ufo_instance.lib[WEIGHT_KEY] = instance.weight
        ufo_instance.lib[WIDTH_KEY] = instance.width

        ufo_instance.lib[INSTANCE_INTERPOLATIONS_KEY] = instance.instanceInterpolations
        ufo_instance.lib[MANUAL_INTERPOLATION_KEY] = instance.manualInterpolation

    # Strategy: dump all custom parameters into the InstanceDescriptor.
    # Later, when using `apply_instance_data`, we will dig out those custom
    # parameters using `InstanceDescriptorAsGSInstance` and apply them to the
    # instance UFO with `to_ufo_custom_params`.
    # NOTE: customParameters are not a dict! One key can have several values
    params = []
    for p in instance.customParameters:
        if p.name in (
            "familyName",
            "postscriptFontName",
            "fileName",
            FULL_FILENAME_KEY,
            UFO_FILENAME_CUSTOM_PARAM,
        ):
            # These will be stored in the official descriptor attributes
            continue
        if p.name in ("weightClass", "widthClass"):
            # No need to store these ones because we can recover them by
            # reading the mapping backward, because the mapping is built from
            # where the instances are.
            continue
        params.append((p.name, p.value))
    if params:
        ufo_instance.lib[CUSTOM_PARAMETERS_KEY] = params

    self.designspace.addInstance(ufo_instance)


def _is_instance_included_in_family(self, instance):
    if not self._do_filter_instances_by_family:
        return True
    return instance.familyName == self.family_name


# TODO: function is too complex (35), split it up
def to_glyphs_instances(self):  # noqa: C901
    if self.designspace is None:
        return

    for ufo_instance in self.designspace.instances:
        instance = self.glyphs_module.GSInstance()

        try:
            instance.active = ufo_instance.lib[EXPORT_KEY]
        except KeyError:
            # If not specified, the default is to export all instances
            instance.active = True

        instance.name = ufo_instance.styleName

        for axis_def in get_axis_definitions(self.font):
            design_loc = None
            try:
                design_loc = ufo_instance.location[axis_def.name]
                axis_def.set_design_loc(instance, design_loc)
            except KeyError:
                # The location does not have this axis?
                pass

            if axis_def.tag in ("wght", "wdth"):
                # Retrieve the user location (weightClass/widthClass)
                # Generic way: read the axis mapping backwards.
                user_loc = design_loc
                mapping = None
                for axis in self.designspace.axes:
                    if axis.tag == axis_def.tag:
                        mapping = axis.map
                if mapping:
                    reverse_mapping = [(dl, ul) for ul, dl in mapping]
                    user_loc = interp(reverse_mapping, design_loc)
                if user_loc is not None:
                    axis_def.set_user_loc(instance, user_loc)

        try:
            # Restore the original weight name when there is an ambiguity based
            # on the value, e.g. Thin, ExtraLight, UltraLight all map to 250.
            # No problem with width, because 1:1 mapping in WIDTH_CODES.
            weight = ufo_instance.lib[WEIGHT_KEY]
            # Only use the lib value if:
            # 1. we don't have a weight for the instance already
            # 2. the value from lib is not "stale", i.e. it still maps to
            #    the current userLocation of the instance. This is in case the
            #    user changes the instance location of the instance by hand but
            #    does not update the weight value in lib.
            if (
                not instance.weight
                or WEIGHT_CODES[instance.weight] == WEIGHT_CODES[weight]
            ):
                instance.weight = weight
        except KeyError:
            # FIXME: what now
            pass

        try:
            if not instance.width:
                instance.width = ufo_instance.lib[WIDTH_KEY]
        except KeyError:
            # FIXME: what now
            pass

        if ufo_instance.familyName is not None:
            if ufo_instance.familyName != self.font.familyName:
                instance.familyName = ufo_instance.familyName

        smfn = ufo_instance.styleMapFamilyName
        if smfn is not None:
            if smfn.startswith(ufo_instance.familyName):
                smfn = smfn[len(ufo_instance.familyName) :].strip()
            instance.linkStyle = smfn

        if ufo_instance.styleMapStyleName is not None:
            style = ufo_instance.styleMapStyleName
            instance.isBold = "bold" in style
            instance.isItalic = "italic" in style

        if ufo_instance.postScriptFontName is not None:
            instance.fontName = ufo_instance.postScriptFontName

        try:
            instance.manualInterpolation = ufo_instance.lib[MANUAL_INTERPOLATION_KEY]
        except KeyError:
            pass

        try:
            instance.instanceInterpolations = ufo_instance.lib[
                INSTANCE_INTERPOLATIONS_KEY
            ]
        except KeyError:
            # TODO: (jany) compute instanceInterpolations from the location
            # if instance.manualInterpolation: warn about data loss
            pass

        if CUSTOM_PARAMETERS_KEY in ufo_instance.lib:
            for name, value in ufo_instance.lib[CUSTOM_PARAMETERS_KEY]:
                instance.customParameters.append(GSCustomParameter(name, value))

        if ufo_instance.filename and self.minimize_ufo_diffs:
            instance.customParameters[UFO_FILENAME_CUSTOM_PARAM] = ufo_instance.filename

        # FIXME: (jany) cannot `.append()` because no proxy => no parent
        self.font.instances = self.font.instances + [instance]


class InstanceDescriptorAsGSInstance:
    """Wraps a designspace InstanceDescriptor and makes it behave like a
    GSInstance, just enough to use the descriptor as a source of custom
    parameters for `to_ufo_custom_parameters`
    """

    def __init__(self, descriptor):
        self._descriptor = descriptor

        # Having a simple list is enough because `to_ufo_custom_params` does
        # not use the fake dictionary interface.
        self.customParameters = []
        if CUSTOM_PARAMETERS_KEY in descriptor.lib:
            for name, value in descriptor.lib[CUSTOM_PARAMETERS_KEY]:
                self.customParameters.append(GSCustomParameter(name, value))


def _set_class_from_instance(ufo, designspace, instance, axis_tag):
    # FIXME: (jany) copy-pasted from above, factor into method?
    assert axis_tag in ("wght", "wdth")

    factory = AxisDefinitionFactory()
    for axis in designspace.axes:
        if axis.tag == axis_tag:
            axis_def = factory.get(axis.tag, axis.name)
            mapping = axis.map
            break
    else:
        # axis not found, try use the default axis definition
        axis_def = WEIGHT_AXIS_DEF if axis_tag == "wght" else WIDTH_AXIS_DEF
        mapping = []

    try:
        design_loc = instance.location[axis_def.name]
    except KeyError:
        user_loc = axis_def.default_user_loc
    else:
        if mapping:
            # Retrieve the user location (weightClass/widthClass)
            # by going through the axis mapping in reverse.
            reverse_mapping = sorted({dl: ul for ul, dl in mapping}.items())
            user_loc = interp(reverse_mapping, design_loc)
        else:
            # no mapping means user space location is same as design space
            user_loc = design_loc
    axis_def.set_ufo_user_loc(ufo, user_loc)


def set_weight_class(ufo, designspace, instance):
    """Set ufo.info.openTypeOS2WeightClass according to the user location
    of the designspace instance, as calculated from the axis mapping.
    """
    _set_class_from_instance(ufo, designspace, instance, "wght")


def set_width_class(ufo, designspace, instance):
    """Set ufo.info.openTypeOS2WidthClass according to the user location
    of the designspace instance, as calculated from the axis mapping.
    """
    _set_class_from_instance(ufo, designspace, instance, "wdth")


def apply_instance_data(designspace, include_filenames=None, Font=None):
    """Open UFO instances referenced by designspace, apply Glyphs instance
    data if present, re-save UFOs and return updated UFO Font objects.

    Args:
        designspace: DesignSpaceDocument object or path (str or PathLike) to
            a designspace file.
        include_filenames: optional set of instance filenames (relative to
            the designspace path) to be included. By default all instaces are
            processed.
        Font: a callable(path: str) -> Font, used to load a UFO, such as
            defcon.Font class (default: ufoLib2.Font.open).
    Returns:
        List of opened and updated instance UFOs.
    """
    from fontTools.designspaceLib import DesignSpaceDocument
    from os.path import normcase, normpath

    if Font is None:
        import ufoLib2

        Font = ufoLib2.Font.open

    if hasattr(designspace, "__fspath__"):
        designspace = designspace.__fspath__()
    if isinstance(designspace, str):
        designspace = DesignSpaceDocument.fromfile(designspace)

    basedir = os.path.dirname(designspace.path)
    instance_ufos = []
    if include_filenames is not None:
        include_filenames = {normcase(normpath(p)) for p in include_filenames}

    for designspace_instance in designspace.instances:
        fname = designspace_instance.filename
        assert fname is not None, "instance %r missing required filename" % getattr(
            designspace_instance, "name", designspace_instance
        )
        if include_filenames is not None:
            fname = normcase(normpath(fname))
            if fname not in include_filenames:
                continue

        logger.debug("Applying instance data to %s", fname)
        # fontmake <= 1.4.0 compares the ufo paths returned from this function
        # to the keys of a dict of designspace locations that have been passed
        # through normpath (but not normcase). We do the same.
        ufo = Font(normpath(os.path.join(basedir, fname)))

        apply_instance_data_to_ufo(ufo, designspace_instance, designspace)

        ufo.save()
        instance_ufos.append(ufo)
    return instance_ufos


def apply_instance_data_to_ufo(ufo, instance, designspace):
    """Apply Glyphs instance data to UFO object.

    Args:
        ufo: a defcon-like font object.
        instance: a fontTools.designspaceLib.InstanceDescriptor.
        designspace: a fontTools.designspaceLib.DesignSpaceDocument.
    Returns:
        None.
    """
    if any(axis.tag == "wght" for axis in designspace.axes):
        set_weight_class(ufo, designspace, instance)
    if any(axis.tag == "wdth" for axis in designspace.axes):
        set_width_class(ufo, designspace, instance)

    glyphs_instance = InstanceDescriptorAsGSInstance(instance)
    to_ufo_custom_params(None, ufo, glyphs_instance)
