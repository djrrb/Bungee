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


import logging

from glyphsLib import classes
from glyphsLib.classes import WEIGHT_CODES, WIDTH_CODES
from .constants import GLYPHLIB_PREFIX

# This is a key into GSFont.userData to store axes defined in the designspace
AXES_KEY = GLYPHLIB_PREFIX + "axes"

# From the spec:
# https://docs.microsoft.com/en-gb/typography/opentype/spec/os2#uswidthclass
WIDTH_CLASS_TO_VALUE = {
    1: 50,  # Ultra-condensed
    2: 62.5,  # Extra-condensed
    3: 75,  # Condensed
    4: 87.5,  # Semi-condensed
    5: 100,  # Medium
    6: 112.5,  # Semi-expanded
    7: 125,  # Expanded
    8: 150,  # Extra-expanded
    9: 200,  # Ultra-expanded
}

logger = logging.getLogger(__name__)


def class_to_value(axis, ufo_class):
    """
    >>> class_to_value('wdth', 7)
    125
    """
    if axis == "wght":
        # 600.0 => 600, 250 => 250
        return int(ufo_class)
    elif axis == "wdth":
        return WIDTH_CLASS_TO_VALUE[int(ufo_class)]

    raise NotImplementedError


def _nospace_lookup(dict, key):
    try:
        return dict[key]
    except KeyError:
        # Even though the Glyphs UI strings are supposed to be fixed,
        # some Noto files contain variants of them that have spaces.
        key = "".join(str(key).split())
        return dict[key]


def user_loc_string_to_value(axis_tag, user_loc):
    """Go from Glyphs UI strings to user space location.
    Returns None if the string is invalid.

    >>> user_loc_string_to_value('wght', 'ExtraLight')
    200
    >>> user_loc_string_to_value('wdth', 'SemiCondensed')
    87.5
    >>> user_loc_string_to_value('wdth', 'Clearly Not From Glyphs UI')
    """
    if axis_tag == "wght":
        if isinstance(user_loc, int):
            value = user_loc
        else:
            try:
                value = _nospace_lookup(WEIGHT_CODES, user_loc)
            except KeyError:
                return None
        return class_to_value("wght", value)
    elif axis_tag == "wdth":
        if isinstance(user_loc, int):
            value = user_loc
        else:
            try:
                value = _nospace_lookup(WIDTH_CODES, user_loc)
            except KeyError:
                return None
        return class_to_value("wdth", value)

    # Currently this function should only be called with a width or weight
    raise NotImplementedError


def user_loc_value_to_class(axis_tag, user_loc):
    """Return the OS/2 weight or width class that is closest to the provided
    user location. For weight the user location is between 0 and 1000 and for
    width it is a percentage.

    >>> user_loc_value_to_class('wght', 310)
    310
    >>> user_loc_value_to_class('wdth', 62)
    2
    """
    if axis_tag == "wght":
        return int(user_loc)
    elif axis_tag == "wdth":
        return min(
            sorted(WIDTH_CLASS_TO_VALUE.items()),
            key=lambda item: abs(item[1] - user_loc),
        )[0]

    raise NotImplementedError


def user_loc_value_to_instance_string(axis_tag, user_loc):
    """Return the Glyphs UI string (from the instance dropdown) that is
    closest to the provided user location.

    >>> user_loc_value_to_instance_string('wght', 430)
    'Normal'
    >>> user_loc_value_to_instance_string('wdth', 150)
    'Extra Expanded'
    """
    codes = {}
    if axis_tag == "wght":
        codes = WEIGHT_CODES
    elif axis_tag == "wdth":
        codes = WIDTH_CODES
    else:
        raise NotImplementedError
    class_ = user_loc_value_to_class(axis_tag, user_loc)
    return min(
        sorted((code, class_) for code, class_ in codes.items() if code is not None),
        key=lambda item: abs(item[1] - class_),
    )[0]


def to_designspace_axes(self):
    if not self.font.masters:
        return
    regular_master = get_regular_master(self.font)
    assert isinstance(regular_master, classes.GSFontMaster)

    custom_mapping = self.font.customParameters["Axis Mappings"]

    for axis_def in get_axis_definitions(self.font):
        axis = self.designspace.newAxisDescriptor()
        axis.tag = axis_def.tag
        axis.name = axis_def.name
        # TODO add support for localised axis.labelNames when Glyphs.app does

        # Make sure here that if there is an Axes parameter, we actually really
        # keep axes that are defined in it, even if they do nothing. This
        # prevents an edge case where you have a single master at the default
        # location that ends in with a Designspace with no axes, as they were
        # all filtered out by the `if` statement at the bottom.
        axis_wanted = False
        if any(
            a.get("Tag") == axis.tag for a in self.font.customParameters["Axes"] or []
        ):
            axis_wanted = True

        # See https://github.com/googlefonts/glyphsLib/issues/568
        if custom_mapping:
            if axis.tag in custom_mapping:
                mapping = {float(k): v for k, v in custom_mapping[axis.tag].items()}
                regularDesignLoc = axis_def.get_design_loc(regular_master)
                reverse_mapping = [(dl, ul) for ul, dl in sorted(mapping.items())]
                regularUserLoc = interp(reverse_mapping, regularDesignLoc)
            else:
                logger.debug(
                    f"Skipping {axis.tag} since it hasn't been defined "
                    "in the Axis Mapping."
                )
                continue
        # See https://github.com/googlefonts/glyphsLib/issues/280
        elif font_uses_axis_locations(self.font):
            # Build the mapping from the "Axis Location" of the masters
            # TODO: (jany) use Virtual Masters as well?
            mapping = {}
            for master in self.font.masters:
                designLoc = axis_def.get_design_loc(master)
                userLoc = axis_def.get_user_loc(master)
                if userLoc in mapping and mapping[userLoc] != designLoc:
                    logger.warning(
                        "Axis location (%s) was redefined by '%s'", userLoc, master.name
                    )
                mapping[userLoc] = designLoc

            regularDesignLoc = axis_def.get_design_loc(regular_master)
            regularUserLoc = axis_def.get_user_loc(regular_master)
        else:
            # Build the mapping from the instances because they have both
            # a user location and a design location.
            instance_mapping = {}
            for instance in self.font.instances:
                if is_instance_active(instance) or self.minimize_glyphs_diffs:
                    designLoc = axis_def.get_design_loc(instance)
                    userLoc = axis_def.get_user_loc(instance)
                    if (
                        userLoc in instance_mapping
                        and instance_mapping[userLoc] != designLoc
                    ):
                        logger.warning(
                            "Instance user-space location (%s) redefined by " "'%s'",
                            userLoc,
                            instance.name,
                        )
                    instance_mapping[userLoc] = designLoc

            master_mapping = {}
            for master in self.font.masters:
                # Glyphs masters don't have a user location
                userLoc = designLoc = axis_def.get_design_loc(master)
                master_mapping[userLoc] = designLoc

            # Prefer the instance-based mapping
            mapping = instance_mapping or master_mapping

            regularDesignLoc = axis_def.get_design_loc(regular_master)
            # Glyphs masters don't have a user location, so we compute it by
            # looking at the axis mapping in reverse.
            reverse_mapping = [(dl, ul) for ul, dl in sorted(mapping.items())]
            regularUserLoc = interp(reverse_mapping, regularDesignLoc)
            # TODO make sure that the default is in mapping?

        minimum = min(mapping)
        maximum = max(mapping)
        default = min(maximum, max(minimum, regularUserLoc))  # clamp

        is_identity_map = all(uloc == dloc for uloc, dloc in mapping.items())
        if (
            minimum < maximum
            or minimum != axis_def.default_user_loc
            or not is_identity_map
            or axis_wanted
        ):
            if not is_identity_map:
                axis.map = sorted(mapping.items())
            axis.minimum = minimum
            axis.maximum = maximum
            axis.default = default
            self.designspace.addAxis(axis)

    # If there are no interesting axes, but only a single master at default location
    # along all 3 predefined axes, all with identity user:design mapping, we end up
    # with an empty list of axes, which is invalid. Thus as last resort we emit a
    # do-nothing Weight axis (the default axis when no "Axes" custom parameter is
    # defined) where default==min==max==400.
    # https://github.com/googlefonts/fontmake/issues/644
    if not self.designspace.axes:
        self.designspace.addAxisDescriptor(
            name=WEIGHT_AXIS_DEF.name,
            tag=WEIGHT_AXIS_DEF.tag,
            minimum=WEIGHT_AXIS_DEF.default_user_loc,
            default=WEIGHT_AXIS_DEF.default_user_loc,
            maximum=WEIGHT_AXIS_DEF.default_user_loc,
        )


def font_uses_axis_locations(font):
    # It's possible for fonts to have the 'Axes' parameter but to NOT specify
    # the master locations using 'Axis Location', in which case we have to
    # resort to using instances or other old tricks to get the mapping.
    # https://github.com/googlefonts/glyphsLib/issues/409
    # https://github.com/googlefonts/glyphsLib/issues/411
    return font.axes and all(
        master.customParameters["Axis Location"] for master in font.masters
    )


def to_glyphs_axes(self):
    axes_parameter = []
    for axis in self.designspace.axes:
        if axis.tag == "wght":
            axes_parameter.append(
                classes.GSAxis(name=axis.name or "Weight", tag="wght")
            )
        elif axis.tag == "wdth":
            axes_parameter.append(classes.GSAxis(name=axis.name or "Width", tag="wdth"))
        else:
            axes_parameter.append(classes.GSAxis(name=axis.name, tag=axis.tag))

    if axes_parameter and not _is_subset_of_default_axes(axes_parameter):
        self.font.axes = axes_parameter

    if any(_has_meaningful_map(a, self.designspace) for a in self.designspace.axes):
        mapping = {
            axis.tag: {str(k): v for k, v in axis.map} for axis in self.designspace.axes
        }
        self.font.customParameters["Axis Mappings"] = mapping


class AxisDefinition:
    """Centralize the code that deals with axis locations, user location versus
    design location, associated OS/2 table codes, etc.
    """

    def __init__(
        self,
        tag,
        name,
        design_loc_key,
        default_design_loc=0.0,
        user_loc_key=None,
        user_loc_param=None,
        default_user_loc=0.0,
    ):
        self.tag = tag
        self.name = name
        self.design_loc_key = design_loc_key
        self.default_design_loc = default_design_loc
        self.user_loc_key = user_loc_key
        self.user_loc_param = user_loc_param
        self.default_user_loc = default_user_loc

    def get_design_loc(self, glyphs_master_or_instance):
        """Get the design location (aka interpolation value) of a Glyphs
        master or instance along this axis. For example for the weight
        axis it could be the thickness of a stem, for the width a percentage
        of extension with respect to the normal width.
        """
        return glyphs_master_or_instance._get_axis_value(self.design_loc_key)

    def set_design_loc(self, master_or_instance, value):
        """Set the design location of a Glyphs master or instance."""
        master_or_instance._set_axis_value(self.design_loc_key, value)

    def get_user_loc(self, master_or_instance):
        """Get the user location of a Glyphs master or instance.
        Masters in Glyphs can have a user location in the "Axis Location"
        custom parameter.

        The user location is what the user sees on the slider in his
        variable-font-enabled UI. For weight it is a value between 0 and 1000,
        400 being Regular and 700 Bold.

        For width it's a percentage of extension with respect to the normal
        width, 100 being normal, 200 Ultra-expanded = twice as wide.
        It may or may not match the design location.
        """
        user_loc = self.default_user_loc

        if self.tag != "wght":
            # The user location is by default the same as the design location.
            user_loc = self.get_design_loc(master_or_instance)

        # Try to guess the user location by looking at the OS/2 weightClass
        # and widthClass. If a weightClass is found, it translates directly
        # to a user location in 0..1000. If a widthClass is found, it
        # translate to a percentage of extension according to the spec, see
        # the mapping named `WIDTH_CLASS_TO_VALUE` at the top.
        if self.user_loc_key is not None and hasattr(
            master_or_instance, self.user_loc_key
        ):
            # Instances have special ways to specify a user location.
            # Only weight and with have a custom user location via a key.
            # The `user_loc_key` gives a "location code" = Glyphs UI string
            user_loc_str = getattr(master_or_instance, self.user_loc_key)
            new_user_loc = user_loc_string_to_value(self.tag, user_loc_str)
            if new_user_loc is not None:
                user_loc = new_user_loc

        # The custom param takes over the key if it exists
        # e.g. for weight:
        #       key = "weight" -> "Bold" -> 700
        # but param = "weightClass" -> 600       => 600 wins
        if self.user_loc_param is not None:
            class_ = master_or_instance.customParameters[self.user_loc_param]
            if class_ is not None:
                user_loc = class_to_value(self.tag, class_)

        # Masters have a customParameter that specifies a user location
        # along custom axes. If this is present it takes precedence over
        # everything else.
        loc_param = master_or_instance.customParameters["Axis Location"]
        try:
            for location in loc_param:
                if location.get("Axis") == self.name:
                    user_loc = int(location["Location"])
        except (TypeError, KeyError):
            pass

        return user_loc

    def set_user_loc(self, master_or_instance, value):
        """Set the user location of a Glyphs master or instance."""
        if hasattr(master_or_instance, "instanceInterpolations"):
            # The following code is only valid for instances.
            # Masters also the keys `weight` and `width` but they should not be
            # used, they are deprecated and should only be used to store
            # (parts of) the master's name, but not its location.

            # Try to set the key if possible, i.e. if there is a key, and
            # if there exists a code that can represent the given value, e.g.
            # for "weight": 600 can be represented by SemiBold so we use that,
            # but for 550 there is no code so we will have to set the custom
            # parameter as well.
            if self.user_loc_key is not None and hasattr(
                master_or_instance, self.user_loc_key
            ):
                code = user_loc_value_to_instance_string(self.tag, value)
                value_for_code = user_loc_string_to_value(self.tag, code)
                setattr(master_or_instance, self.user_loc_key, code)
                if self.user_loc_param is not None and value != value_for_code:
                    try:
                        class_ = user_loc_value_to_class(self.tag, value)
                        master_or_instance.customParameters[
                            self.user_loc_param
                        ] = class_
                    except NotImplementedError:
                        # user_loc_value_to_class only works for weight & width
                        pass
            return

        # For masters, set directly the custom parameter (old way)
        # and also the Axis Location (new way).
        # Only masters can have an 'Axis Location' parameter.
        if self.user_loc_param is not None:
            try:
                class_ = user_loc_value_to_class(self.tag, value)
                master_or_instance.customParameters[self.user_loc_param] = class_
            except NotImplementedError:
                pass

        loc_param = master_or_instance.customParameters["Axis Location"]
        if loc_param is None:
            loc_param = []
            master_or_instance.customParameters["Axis Location"] = loc_param
        location = None
        for loc in loc_param:
            if loc.get("Axis") == self.name:
                location = loc
        if location is None:
            loc_param.append({"Axis": self.name, "Location": value})
        else:
            location["Location"] = value

    def set_user_loc_code(self, instance, code):
        assert isinstance(instance, classes.GSInstance)
        # The previous method `set_user_loc` will not roundtrip every
        # time, for example for value = 600, both "DemiBold" and "SemiBold"
        # would work, so we provide this other method to set a specific code.
        if self.user_loc_key is not None:
            setattr(instance, self.user_loc_key, code)

    def set_ufo_user_loc(self, ufo, value):
        if self.tag not in ("wght", "wdth"):
            raise NotImplementedError
        class_ = user_loc_value_to_class(self.tag, value)
        ufo_key = (
            "openTypeOS2WeightClass" if self.tag == "wght" else "openTypeOS2WidthClass"
        )
        setattr(ufo.info, ufo_key, class_)


class AxisDefinitionFactory:
    """Creates a set of axis definitions, making sure to recognize default axes
    (weight and width) and also keeping track of indices of custom axes.

    From looking at a Glyphs file with only one custom axis, it looks like
    when there is an "Axes" customParameter, the axis design locations are
    stored in `weightValue` for the first axis (regardless of whether it is
    a weight axis, `widthValue` for the second axis, etc.
    """

    def __init__(self):
        self.axis_index = -1

    def get(self, tag=None, name="Custom"):
        self.axis_index += 1
        design_loc_key = self._design_loc_key()
        if tag is None:
            if self.axis_index == 0:
                tag = "XXXX"
            else:
                tag = "XXX%d" % self.axis_index

        if tag == "wght":
            return AxisDefinition(
                tag, name, design_loc_key, 100.0, "weight", "weightClass", 400.0
            )
        if tag == "wdth":
            return AxisDefinition(
                tag, name, design_loc_key, 100.0, "width", "widthClass", 100.0
            )
        return AxisDefinition(tag, name, design_loc_key, 0.0, None, None, 0.0)

    def _design_loc_key(self):
        return self.axis_index


defaults_factory = AxisDefinitionFactory()

WEIGHT_AXIS_DEF = defaults_factory.get("wght", "Weight")
WIDTH_AXIS_DEF = defaults_factory.get("wdth", "Width")
CUSTOM_AXIS_DEF = defaults_factory.get("XXXX", "Custom")
DEFAULT_AXES_DEFS = (WEIGHT_AXIS_DEF, WIDTH_AXIS_DEF, CUSTOM_AXIS_DEF)


# Adapted from PR https://github.com/googlefonts/glyphsLib/pull/306
def get_axis_definitions(font):
    axesParameter = font.customParameters["Axes"]
    if axesParameter is None:
        return DEFAULT_AXES_DEFS

    factory = AxisDefinitionFactory()
    return [factory.get(axis.get("Tag"), axis["Name"]) for axis in axesParameter]


def _is_subset_of_default_axes(axes_parameter):
    if len(axes_parameter) > 3:
        return False
    for axis, axis_def in zip(axes_parameter, DEFAULT_AXES_DEFS):
        if axis.name != axis_def.name:
            return False
        if axis.axisTag != axis_def.tag:
            return False
    return True


def _has_meaningful_map(axis, designspace):
    if not axis.map:
        return False
    for k, v in axis.map:
        if k != v:
            return True
    # We have an identity map. We could elide it, but...
    # sometimes we use an identity map to force a particular
    # range even though the sources don't fill that range.
    min_axis = None
    max_axis = None
    for source in designspace.sources:
        loc = source.location.get(axis.name)
        if loc is None:
            continue
        if min_axis is None:
            min_axis = loc
        else:
            min_axis = min(loc, min_axis)
        if max_axis is None:
            max_axis = loc
        else:
            max_axis = max(loc, max_axis)
    if min_axis != axis.map[0][0] or max_axis != axis.map[-1][0]:
        return True
    return False


def get_regular_master(font):
    """Find the "regular" master among the GSFontMasters.

    Tries to find the master with the passed 'regularName'.
    If there is no such master or if regularName is None,
    tries to find a base style shared between all masters
    (defaulting to "Regular"), and then tries to find a master
    with that style name. If there is no master with that name,
    returns the first master in the list.
    """
    if not font.masters:
        return None
    # The current glyphs source specification supports the custom
    # parameter name "Variable Font Origin".  This may have been
    # named "Variation Font Origin" in the past.
    # We support the current name with a fallback to the previous name
    # if not found in the GSFont.customParameters dict
    if "Variable Font Origin" in font.customParameters:
        regular_id = font.customParameters["Variable Font Origin"]
        if regular_id:
            for master in font.masters:
                if master.id == regular_id:
                    return master
    elif "Variation Font Origin" in font.customParameters:
        regular_name = font.customParameters["Variation Font Origin"]
        if regular_name:
            for master in font.masters:
                if master.name == regular_name:
                    return master
    base_style = find_base_style(font.masters)
    if not base_style:
        base_style = "Regular"
    for master in font.masters:
        if master.name == base_style:
            return master
    # Second try: maybe the base style has regular in it as well
    for master in font.masters:
        name_without_regular = " ".join(
            n for n in master.name.split(" ") if n != "Regular"
        )
        if name_without_regular == base_style:
            return master
    return font.masters[0]


def find_base_style(masters):
    """Find a base style shared between all masters.
    Return empty string if none is found.
    """
    if not masters:
        return ""
    base_style = (masters[0].name or "").split()
    for master in masters:
        style = master.name.split()
        base_style = [s for s in style if s in base_style]
    base_style = " ".join(base_style)
    return base_style


def is_instance_active(instance):
    # Glyphs.app recognizes both "exports=0" and "active=0" as a flag
    # to mark instances as inactive. Inactive instances should get ignored.
    # https://github.com/googlefonts/glyphsLib/issues/129
    return instance.exports and getattr(instance, "active", True)


def interp(mapping, x):
    """Compute the piecewise linear interpolation given by mapping for input x.

    >>> interp(((1, 1), (2, 4)), 1.5)
    2.5
    """
    mapping = sorted(mapping)
    if len(mapping) == 1:
        xa, ya = mapping[0]
        if xa == x:
            return ya
        return x
    for (xa, ya), (xb, yb) in zip(mapping[:-1], mapping[1:]):
        if xa <= x <= xb:
            return ya + float(x - xa) / (xb - xa) * (yb - ya)
    return x
