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


from collections import OrderedDict, defaultdict
from functools import partial
import logging
import os
import re
from textwrap import dedent
from typing import Any, Dict

from fontTools import designspaceLib
from fontTools.varLib import FEAVAR_FEATURETAG_LIB_KEY

from glyphsLib import classes, glyphdata, util
from .constants import (
    PUBLIC_PREFIX,
    FONT_CUSTOM_PARAM_PREFIX,
    GLYPHLIB_PREFIX,
)
from .axes import WEIGHT_AXIS_DEF, WIDTH_AXIS_DEF, find_base_style, class_to_value

GLYPH_ORDER_KEY = PUBLIC_PREFIX + "glyphOrder"

BRACKET_GLYPH_TEMPLATE = "{glyph_name}.{rev}BRACKET.{location}"
REVERSE_BRACKET_LABEL = "REV_"
BRACKET_GLYPH_RE = re.compile(
    r"(?P<glyph_name>.+)\.(?P<rev>{})?BRACKET\.(?P<location>\d+)$".format(
        REVERSE_BRACKET_LABEL
    )
)
BRACKET_GLYPH_SUFFIX_RE = re.compile(r".*(\..*BRACKET\.\d+)$")


class _LoggerMixin:

    _logger = None

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(
                ".".join([self.__class__.__module__, self.__class__.__name__])
            )
        return self._logger


class UFOBuilder(_LoggerMixin):
    """Builder for Glyphs to UFO + designspace."""

    def __init__(
        self,
        font,
        ufo_module=None,
        designspace_module=designspaceLib,
        family_name=None,
        instance_dir=None,
        propagate_anchors=None,
        use_designspace=False,
        minimize_glyphs_diffs=False,
        generate_GDEF=True,
        store_editor_state=True,
        write_skipexportglyphs=False,
        minimal=False,
        glyph_data=None,
    ):
        """Create a builder that goes from Glyphs to UFO + designspace.

        Keyword arguments:
        font -- The GSFont object to transform into UFOs
        ufo_module -- A Python module to use to build UFO objects (you can pass
                      a custom module that has the same classes as ufoLib2 or
                      defcon to get instances of your own classes). Default: ufoLib2
        designspace_module -- A Python module to use to build a Designspace
                              Document. Default is fontTools.designspaceLib.
        family_name -- if provided, the master UFOs will be given this name and
                       only instances with this name will be returned.
        instance_dir -- if provided, instance UFOs will be located in this
                        directory, according to their Designspace filenames.
        propagate_anchors -- set to True or False to explicitly control anchor
                             propagation, the default is to check for
                             "Propagate Anchors" custom parameter.
        use_designspace -- set to True to make optimal use of the designspace:
                           data that is common to all ufos will go there.
        minimize_glyphs_diffs -- set to True to store extra info in UFOs
                                 in order to get smaller diffs between .glyphs
                                 .glyphs files when going glyphs->ufo->glyphs.
        generate_GDEF -- set to False to skip writing a `table GDEF {...}` in
                         the UFO features.
        store_editor_state -- If True, store editor state in the UFO like which
                              glyphs are open in which tabs ("DisplayStrings").
        write_skipexportglyphs -- If True, write the export status of a glyph
                                         into the UFOs' and Designspace's lib instead
                                         of the glyph level lib key
                                         "com.schriftgestaltung.Glyphs.Export".
        glyph_data -- A list of GlyphData.
        """
        self.font = font

        if ufo_module is None:
            import ufoLib2 as ufo_module

        self.ufo_module = ufo_module

        self.designspace_module = designspace_module
        self.instance_dir = instance_dir
        self.use_designspace = use_designspace
        self.minimize_glyphs_diffs = minimize_glyphs_diffs
        self.generate_GDEF = generate_GDEF
        self.store_editor_state = store_editor_state
        self.bracket_layers = []
        self.write_skipexportglyphs = write_skipexportglyphs
        self.minimal = minimal

        if propagate_anchors is None:
            propagate_anchors = font.customParameters["Propagate Anchors"]
            propagate_anchors = bool(propagate_anchors is None or propagate_anchors)
        self.propagate_anchors = propagate_anchors

        # The set of (SourceDescriptor + UFO)s that will be built,
        # indexed by master ID, the same order as masters in the source GSFont.
        self._sources = OrderedDict()

        # Map Glyphs layer IDs to UFO layer names.
        self._layer_map = {}

        # List of exploded color palette layers when building minimal UFOs.
        self._color_palette_layers = []

        # List of color layers when building minimal UFOs.
        self._color_layers = []

        # A cache for mappings of layer IDs to mappings of glyph names to Glyphs layers,
        # for passing into pens as glyph sets.
        self._glyph_sets: Dict[str, Dict[str, classes.GSLayer]] = {}

        # The designSpaceDocument object that will be built.
        # The sources will be built in any case, at the same time that we build
        # the master UFOs, when the user requests them.
        # The axes, instances, rules... will only be built if the designspace
        # document itself is requested by the user.
        self._designspace = self.designspace_module.DesignSpaceDocument()
        self._designspace_is_complete = False

        # If any glyph layer which is associated with a GSFontMaster has the
        # properties "vertWidth" or "vertOrigin" set, Glyphsapp will assume
        # the font is going to be used for vertical typesetting. When
        # Glyphsapp generates these fonts, it will include the vhea, vmtx,
        # VORG tables. VORG will only be included if the font is an otf.
        self.is_vertical = self._is_vertical()

        # check that source was generated with at least stable version 2.3
        # https://github.com/googlefonts/glyphsLib/pull/65#issuecomment-237158140
        if int(font.appVersion) < 895:
            self.logger.warning(
                "This Glyphs source was generated with an outdated version "
                "of Glyphs. The resulting UFOs may be incorrect."
            )

        # check that source does not include the old custom
        # parameter name "Variation Font Origin".  As of sometime prior to
        # Glyphs v2.6.4 (1286) build, the custom parameter name was
        # changed to "Variable Font Origin" from "Variation Font Origin"
        if "Variation Font Origin" in font.customParameters:
            self.logger.warning(
                "This Glyphs source was generated with an outdated version "
                "of Glyphs. Please update the 'Variation Font Origin' "
                "custom parameter to 'Variable Font Origin'. The resulting "
                "UFOs may be incorrect."
            )

        if family_name is None:
            # use the source family name, and include all the instances
            self.family_name = self.font.familyName
            self._do_filter_instances_by_family = False
        else:
            self.family_name = family_name
            # use a custom 'family_name' to name master UFOs, and only build
            # instances with matching 'familyName' custom parameter
            self._do_filter_instances_by_family = True

        if glyph_data:
            from io import BytesIO

            glyphdata_files = []
            for path in glyph_data:
                with open(path, "rb") as fp:
                    glyphdata_files.append(BytesIO(fp.read()))
            self.glyphdata = glyphdata.GlyphData.from_files(*glyphdata_files)
        else:
            self.glyphdata = None

    def _is_vertical(self):
        master_ids = {m.id for m in self.font.masters}
        for glyph in self.font.glyphs:
            for layer in glyph.layers:
                if layer.layerId not in master_ids:
                    continue
                if layer.vertWidth is not None or layer.vertOrigin is not None:
                    return True
        return False

    @property
    def masters(self):
        """Get an iterator over master UFOs that match the given family_name."""
        if self._sources:
            for source in self._sources.values():
                yield source.font
            return

        # TODO(jamesgk) maybe create one font at a time to reduce memory usage
        # TODO: (jany) in the future, return a lazy iterator that builds UFOs
        #     on demand.
        self.to_ufo_font_attributes(self.family_name)

        self.to_ufo_layers()

        for master_id, source in self._sources.items():
            ufo = source.font
            master = self.font.masters[master_id]
            if self.propagate_anchors:
                self.to_ufo_propagate_font_anchors(ufo)
            for layer in list(ufo.layers):
                self.to_ufo_layer_lib(master, ufo, layer)

            # Color layer mapping is stored using layer IDs, we now rewrite it
            # to use the final UFO layer names.
            self.to_ufo_color_layer_names(master, ufo)

            # to_ufo_custom_params may apply "Replace Features" or "Replace Prefix"
            # parameters so it requires UFOs have their features set first; at the
            # same time, to generate a GDEF table we first need to have defined the
            # glyphOrder, exported the glyphs and propagated anchors from components.
            self.to_ufo_master_features(ufo, master)
            self.to_ufo_custom_params(ufo, master)

            self.to_ufo_color_layers(ufo, master)

        if self.write_skipexportglyphs:
            # Sanitize skip list and write it to both Designspace- and UFO-level lib
            # keys. The latter is unnecessary when using e.g. the ufo2ft.compile*FromDS`
            # functions, but the data may take a different path. Writing it everywhere
            # can save on surprises/logic in other software.
            skip_export_glyphs = self._designspace.lib.get("public.skipExportGlyphs")
            if skip_export_glyphs is not None:
                skip_export_glyphs = sorted(set(skip_export_glyphs))
                self._designspace.lib["public.skipExportGlyphs"] = skip_export_glyphs
                for source in self._sources.values():
                    source.font.lib["public.skipExportGlyphs"] = skip_export_glyphs

        self.to_ufo_groups()
        self.to_ufo_kerning()

        for source in self._sources.values():
            yield source.font

    def to_ufo_layers(self):
        # Store set of actually existing master (layer) ids. This helps with
        # catching dangling layer data that Glyphs may ignore, e.g. when
        # copying glyphs from other fonts with, naturally, different master
        # ids. Note: Masters have unique ids according to the Glyphs
        # documentation and can therefore be stored in a set.
        master_layer_ids = {m.id for m in self.font.masters}

        # stores background data from "associated layers"
        supplementary_layer_data = []

        # Generate the main (master) layers first.
        for glyph in self.font.glyphs:
            for layer in glyph.layers.values():
                if layer.associatedMasterId != layer.layerId:
                    # The layer is not the main layer of a master
                    # Store all layers, even the invalid ones, and just skip
                    # them and print a warning below.
                    supplementary_layer_data.append((glyph, layer))
                    continue

                ufo_layer = self.to_ufo_layer(glyph, layer)
                ufo_glyph = ufo_layer.newGlyph(glyph.name)
                self.to_ufo_glyph(ufo_glyph, layer, glyph)

        # And sublayers (brace, bracket, ...) second.
        for glyph, layer in supplementary_layer_data:
            if (
                layer.layerId not in master_layer_ids
                and layer.associatedMasterId not in master_layer_ids
            ):
                if self.minimize_glyphs_diffs:
                    self.logger.warning(
                        '{}, glyph "{}": Layer "{}" is dangling and will be '
                        "skipped. Did you copy a glyph from a different font?"
                        " If so, you should clean up any phantom layers not "
                        "associated with an actual master.".format(
                            self.font.familyName, glyph.name, layer.layerId
                        )
                    )
                continue

            if not layer.name:
                # Empty layer names are invalid according to the UFO spec.
                if self.minimize_glyphs_diffs:
                    self.logger.warning(
                        '{}, glyph "{}": Contains layer without a name which '
                        "will be skipped.".format(self.font.familyName, glyph.name)
                    )
                continue

            # Save processing bracket layers for when designspace() is called, as we
            # have to extract them to free-standing glyphs -- unless the parent glyph is
            # set to non-export (in which case makes no sense to have Designspace rules
            # referencing non existent glyphs).
            if (
                layer._is_bracket_layer()
                and glyph.export
                and ".background" not in layer.name
            ):
                self.bracket_layers.append(layer)
            elif (
                self.minimal
                and layer.layerId not in master_layer_ids
                and not layer._is_brace_layer()
            ):
                continue
            else:
                ufo_layer = self.to_ufo_layer(glyph, layer)
                ufo_glyph = ufo_layer.newGlyph(glyph.name)
                self.to_ufo_glyph(ufo_glyph, layer, layer.parent)

    @property
    def designspace(self):
        """Get a designspace Document instance that links the masters together
        and holds instance data.
        """
        if self._designspace_is_complete:
            return self._designspace

        self._designspace_is_complete = True
        list(self.masters)  # Make sure that the UFOs are built
        self.to_designspace_axes()
        self.to_designspace_sources()
        self.to_designspace_instances()
        self.to_designspace_family_user_data()

        if self.bracket_layers:
            self._apply_bracket_layers()

        # append base style shared by all masters to designspace file name
        base_family = self.family_name or "Unnamed"
        base_style = find_base_style(self.font.masters)
        if base_style:
            base_style = "-" + base_style
        name = (base_family + base_style).replace(" ", "") + ".designspace"
        self.designspace.filename = name

        return self._designspace

    # DEPRECATED
    @property
    def instance_data(self):
        instances = self.font.instances
        if self._do_filter_instances_by_family:
            instances = list(filter_instances_by_family(instances, self.family_name))
        instance_data = {"data": instances, "designspace": self.designspace}

        first_ufo = next(iter(self.masters))

        # the 'Variation Font Origin' is a font-wide custom parameter, thus it is
        # shared by all the master ufos; here we just get it from the first one
        varfont_origin_key = "Variation Font Origin"
        varfont_origin = first_ufo.lib.get(
            FONT_CUSTOM_PARAM_PREFIX + varfont_origin_key
        )
        if varfont_origin:
            instance_data[varfont_origin_key] = varfont_origin
        return instance_data

    def _apply_bracket_layers(self):
        """Extract bracket layers in a GSGlyph into free-standing UFO glyphs with
        Designspace substitution rules.

        As of Glyphs.app 2.6, only single axis bracket layers are supported, we
        assume the axis to be the first axis in the Designspace. Bracket layer
        backgrounds are not round-tripped.

        A glyph can have more than one bracket layer but Designspace
        rule/OpenType variation condition sets apply all substitutions in a rule
        in a range, so we have to potentially sort bracket layers into rule
        buckets. Example: if a glyph "x" has two bracket layers [300] and [600]
        and glyph "a" has bracket layer [300] and the bracket axis tops out at
        1000, we need the following Designspace rules:

        - BRACKET.300.600  # min 300, max 600 on the bracket axis.
          - x -> x.BRACKET.300
        - BRACKET.600.1000
          - x -> x.BRACKET.600
        - BRACKET.300.1000
          - a -> a.BRACKET.300
        """
        if not self._designspace.axes:
            raise ValueError(
                "Cannot apply bracket layers unless at least one axis is defined."
            )
        bracket_axis = self._designspace.axes[0]

        # Determine the axis scale in design space because crossovers/locations are
        # in design space (axis.default/minimum/maximum may be user space).
        if bracket_axis.map:
            axis_scale = [design_location for _, design_location in bracket_axis.map]
            bracket_axis_min = min(axis_scale)
            bracket_axis_max = max(axis_scale)
        else:  # No mapping means user and design space are the same.
            bracket_axis_min = bracket_axis.minimum
            bracket_axis_max = bracket_axis.maximum

        # Organize all bracket layers by glyph name and crossover value, so later we
        # can go through the layers by location and copy them to free-standing glyphs
        bracket_layer_map = defaultdict(partial(defaultdict, list))
        for layer in self.bracket_layers:
            bracket_axis_id, bracket_min, bracket_max = self.validate_bracket_info(
                layer, bracket_axis, bracket_axis_min, bracket_axis_max
            )
            if bracket_min is None and bracket_max is None:
                continue
            glyph_name = layer.parent.name
            bracket_layer_map[glyph_name][(bracket_min, bracket_max)].append(layer)

        # Sort crossovers into rule buckets, one for regular bracket layers (in which
        # the location represents the min value) and one for 'reverse' bracket layers
        # (in which the location is the max value).
        max_rule_bucket = defaultdict(list)
        min_rule_bucket = defaultdict(list)
        for glyph_name, glyph_bracket_layers in sorted(bracket_layer_map.items()):
            min_crossovers = set()
            max_crossovers = set()
            for bracket_min, bracket_max in glyph_bracket_layers.keys():
                if bracket_min is not None:
                    min_crossovers.add(bracket_min)
                elif bracket_max is not None:
                    max_crossovers.add(bracket_max)
            # reverse and non-reverse bracket layers with overlapping ranges are
            # tricky to implement as DS rules. They are relatively unlikely, and
            # can usually be rewritten so that they do not overlap. For laziness/
            # simplicity, where we simply warn that output may not be as expected.
            invalid_locs = [
                (mx, mn)
                for mx, mn in zip(sorted(max_crossovers), sorted(min_crossovers))
                if mx > mn
            ]
            if invalid_locs:
                self.logger.warning(
                    "Bracket layers for glyph '%s' have overlapping ranges: %s",
                    glyph_name,
                    ", ".join("]{}] > [{}]".format(*values) for values in invalid_locs),
                )
            max_crossovers = list(sorted(max_crossovers))
            if bracket_axis_min not in max_crossovers:
                max_crossovers = [bracket_axis_min] + max_crossovers
            for crossover_min, crossover_max in util.pairwise(max_crossovers):
                max_rule_bucket[(int(crossover_min), int(crossover_max))].append(
                    glyph_name
                )
            min_crossovers = list(sorted(min_crossovers))
            if bracket_axis_max not in min_crossovers:
                min_crossovers = min_crossovers + [bracket_axis_max]
            for crossover_min, crossover_max in util.pairwise(min_crossovers):
                min_rule_bucket[(int(crossover_min), int(crossover_max))].append(
                    glyph_name
                )

        # Generate rules for the bracket layers.
        for reverse, rule_bucket in ((True, max_rule_bucket), (False, min_rule_bucket)):
            for (axis_range_min, axis_range_max), glyph_names in sorted(
                rule_bucket.items()
            ):
                rule = _make_designspace_rule(
                    glyph_names,
                    bracket_axis.name,
                    axis_range_min,
                    axis_range_max,
                    reverse,
                )
                self._designspace.addRule(rule)

        # Set feature for rules
        feat = self.font.customParameters["Feature for Feature Variations"]
        if feat == "rclt":
            self._designspace.rulesProcessingLast = True
        elif feat and feat != "rvrn":
            self._designspace.lib[FEAVAR_FEATURETAG_LIB_KEY] = feat

        # Finally, copy bracket layers to their own glyphs.
        self._copy_bracket_layers_to_ufo_glyphs(bracket_layer_map)

        # re-generate the GDEF table since we have added new BRACKET glyphs, which may
        # also need to be included: https://github.com/googlefonts/glyphsLib/issues/578
        if self.generate_GDEF:
            self.regenerate_gdef()

    def validate_bracket_info(
        self, layer, bracket_axis, bracket_axis_min, bracket_axis_max
    ):
        bracket_axis_id, bracket_min, bracket_max = layer._bracket_info()

        if bracket_axis_id != 0:
            raise ValueError("For now, bracket layers can only apply to the first axis")

        # Convert [500<wght<(max)] to [500<wght], etc.
        if bracket_min == bracket_axis_min:
            bracket_min = None
        if bracket_max == bracket_axis_max:
            bracket_max = None

        if bracket_min is not None and bracket_max is not None:
            raise ValueError("Alternate rules with min and max range not yet supported")

        glyph_name = layer.parent.name

        if (
            bracket_min is not None
            and not bracket_axis_min <= bracket_min <= bracket_axis_max
        ) or (
            bracket_max is not None
            and not bracket_axis_min <= bracket_max <= bracket_axis_max
        ):
            raise ValueError(
                "Glyph {glyph_name}: Bracket layer {layer_name} must be within the "
                "design space bounds of the {bracket_axis_name} axis: minimum "
                "{bracket_axis_minimum}, maximum {bracket_axis_maximum}.".format(
                    glyph_name=glyph_name,
                    layer_name=layer.name,
                    bracket_axis_name=bracket_axis.name,
                    bracket_axis_minimum=bracket_axis_min,
                    bracket_axis_maximum=bracket_axis_max,
                )
            )
        return bracket_axis_id, bracket_min, bracket_max

    def _copy_bracket_layers_to_ufo_glyphs(self, bracket_layer_map):
        font = self.font
        master_ids = {m.id for m in font.masters}
        # when a glyph master layer doesn't have an explicitly associated bracket layer
        # for any crosspoint locations, we assume the master layer itself will be
        # used implicitly as bracket layer for that location. See "Switching Only One
        # Master" paragraph in "Alternating Glyph Shapes" tutorial at:
        # https://glyphsapp.com/tutorials/alternating-glyph-shapes
        implicit_bracket_layers = set()
        # collect all bracket glyph names for resolving composite references
        bracket_glyphs = set()

        for glyph_name, glyph_bracket_layers in bracket_layer_map.items():
            glyph = font.glyphs[glyph_name]
            for (
                (bracket_min, bracket_max),
                bracket_layers,
            ) in glyph_bracket_layers.items():

                for missing_master_layer_id in master_ids.difference(
                    bl.associatedMasterId for bl in bracket_layers
                ):
                    master_layer = glyph.layers[missing_master_layer_id]
                    bracket_layers.append(master_layer)
                    implicit_bracket_layers.add(id(master_layer))

                if bracket_max is None:
                    reverse = False
                    location = bracket_min
                else:
                    reverse = True
                    location = bracket_max

                bracket_glyphs.add(_bracket_glyph_name(glyph_name, reverse, location))

        for glyph_name, glyph_bracket_layers in bracket_layer_map.items():
            for (bracket_min, bracket_max), layers in glyph_bracket_layers.items():
                if bracket_max is None:
                    reverse = False
                    location = bracket_min
                else:
                    reverse = True
                    location = bracket_max

                for layer in layers:
                    layer_id = layer.associatedMasterId or layer.layerId
                    ufo_font = self._sources[layer_id].font
                    ufo_layer = ufo_font.layers.defaultLayer
                    ufo_glyph_name = _bracket_glyph_name(glyph_name, reverse, location)
                    ufo_glyph = ufo_layer.newGlyph(ufo_glyph_name)
                    self.to_ufo_glyph(ufo_glyph, layer, layer.parent)
                    ufo_glyph.unicodes = []  # Avoid cmap interference
                    # implicit bracket layers have no distinct name, they are simply
                    # references to master layers; the empty string is a signal when
                    # roundtripping back to Glyphs to skip the duplicate layers.
                    ufo_glyph.lib[GLYPHLIB_PREFIX + "_originalLayerName"] = (
                        "" if id(layer) in implicit_bracket_layers else layer.name
                    )
                    # swap components if base glyph contains matching bracket layers.
                    for comp in ufo_glyph.components:
                        bracket_comp_name = _bracket_glyph_name(
                            comp.baseGlyph, reverse, location
                        )
                        if bracket_comp_name in bracket_glyphs:
                            comp.baseGlyph = bracket_comp_name
                    # Update kerning groups and pairs, bracket glyphs inherit the
                    # parent's kerning.
                    _expand_kerning_to_brackets(glyph_name, ufo_glyph_name, ufo_font)

    # Implementation is split into one file per feature
    from .anchors import to_ufo_propagate_font_anchors, to_ufo_glyph_anchors
    from .annotations import to_ufo_annotations
    from .axes import to_designspace_axes
    from .background_image import to_ufo_background_image
    from .blue_values import to_ufo_blue_values
    from .color_layers import to_ufo_color_layers
    from .common import to_ufo_time
    from .components import to_ufo_components, to_ufo_smart_component_axes
    from .custom_params import to_ufo_custom_params
    from .features import regenerate_gdef, to_ufo_master_features
    from .font import to_ufo_font_attributes
    from .groups import to_ufo_groups
    from .guidelines import to_ufo_guidelines
    from .hints import to_ufo_hints
    from .instances import to_designspace_instances
    from .kerning import to_ufo_kerning
    from .layers import to_ufo_layer, to_ufo_background_layer, to_ufo_color_layer_names
    from .masters import to_ufo_master_attributes
    from .names import to_ufo_names
    from .paths import to_ufo_paths
    from .sources import to_designspace_sources
    from .glyph import (
        to_ufo_glyph,
        to_ufo_glyph_background,
        to_ufo_glyph_height_and_vertical_origin,
    )
    from .user_data import (
        to_designspace_family_user_data,
        to_ufo_family_user_data,
        to_ufo_master_user_data,
        to_ufo_glyph_user_data,
        to_ufo_layer_lib,
        to_ufo_layer_user_data,
        to_ufo_node_user_data,
    )


def _bracket_glyph_name(glyph_name, reverse, location):
    return BRACKET_GLYPH_TEMPLATE.format(
        glyph_name=glyph_name,
        rev=REVERSE_BRACKET_LABEL if reverse else "",
        location=location,
    )


def _make_designspace_rule(glyph_names, axis_name, range_min, range_max, reverse=False):
    rule_name = f"BRACKET.{range_min}.{range_max}"
    rule = designspaceLib.RuleDescriptor()
    rule.name = rule_name
    rule.conditionSets.append(
        [{"name": axis_name, "minimum": range_min, "maximum": range_max}]
    )
    location = range_max if reverse else range_min
    for glyph_name in glyph_names:
        sub_glyph_name = _bracket_glyph_name(glyph_name, reverse, location)
        rule.subs.append((glyph_name, sub_glyph_name))
    return rule


def _expand_kerning_to_brackets(
    glyph_name: str, ufo_glyph_name: str, ufo_font: Any
) -> None:
    """Ensures that bracket glyphs inherit their parents' kerning."""

    for group, names in ufo_font.groups.items():
        if not group.startswith(("public.kern1.", "public.kern2.")):
            continue
        name_set = set(names)
        if glyph_name in name_set and ufo_glyph_name not in name_set:
            names.append(ufo_glyph_name)

    bracket_kerning = {}
    for (first, second), value in ufo_font.kerning.items():
        first_match = first == glyph_name
        second_match = second == glyph_name
        if first_match and second_match:
            bracket_kerning[(ufo_glyph_name, ufo_glyph_name)] = value
        elif first_match:
            bracket_kerning[(ufo_glyph_name, second)] = value
        elif second_match:
            bracket_kerning[(first, ufo_glyph_name)] = value
    ufo_font.kerning.update(bracket_kerning)


def filter_instances_by_family(instances, family_name=None):
    """Yield instances whose 'familyName' custom parameter is
    equal to 'family_name'.
    """
    return (i for i in instances if i.familyName == family_name)


class GlyphsBuilder(_LoggerMixin):
    """Builder for UFO + designspace to Glyphs."""

    def __init__(
        self,
        ufos=None,
        designspace=None,
        glyphs_module=classes,
        ufo_module=None,
        minimize_ufo_diffs=False,
    ):
        """Create a builder that goes from UFOs + designspace to Glyphs.

        If you provide:
            * Some UFOs, no designspace: the given UFOs will be combined.
                No instance data will be created, only the weight and width
                axes will be set up (if relevant).
            * A designspace, no UFOs: the UFOs will be loaded according to
                the designspace's sources. Instance and axis data will be
                converted to Glyphs.
            * Both a designspace and some UFOs: not supported for now.
                TODO: (jany) find out whether there is a use-case here?

        Keyword arguments:
        ufos -- The list of UFOs to combine into a GSFont
        designspace -- A MutatorMath Designspace to use for the GSFont
        glyphs_module -- The glyphsLib.classes module to use to build glyphsLib
                         classes (you can pass a custom module with the same
                         classes as the official glyphsLib.classes to get
                         instances of your own classes, or pass the Glyphs.app
                         module that holds the official classes to import UFOs
                         into Glyphs.app)
        ufo_module -- A Python module to use to load UFO objects from DS source paths.
                      You can pass a custom module that has the same classes as ufoLib2
                      or defcon to get instances of your own classes (default: ufoLib2)
        minimize_ufo_diffs -- set to True to store extra info in .glyphs files
                              in order to get smaller diffs between UFOs
                              when going UFOs->glyphs->UFOs
        """
        self.glyphs_module = glyphs_module
        self.minimize_ufo_diffs = minimize_ufo_diffs

        if designspace is not None:
            if ufos:
                raise NotImplementedError
            if ufo_module is None:
                import ufoLib2 as ufo_module

            self.designspace = self._valid_designspace(designspace, ufo_module)
        elif ufos:
            self.designspace = self._fake_designspace(ufos)
        else:
            raise RuntimeError("Please provide a designspace or at least one UFO.")

        if "public.skipExportGlyphs" in self.designspace.lib:
            self.skip_export_glyphs = set(
                self.designspace.lib["public.skipExportGlyphs"]
            )
        else:
            self.skip_export_glyphs = set()

        self._font = None

    @property
    def font(self):
        """Get the GSFont built from the UFOs + designspace."""
        if self._font is not None:
            return self._font

        # Sort UFOS in the original order from the Glyphs file
        sorted_sources = self.to_glyphs_ordered_masters()

        # Convert all full source UFOs to Glyphs masters. Sources with layer names
        # are assumed to be sparse or "brace" layers and are ignored because Glyphs
        # considers them to be special layers and will handle them itself.
        self._font = self.glyphs_module.GSFont()
        self._sources = OrderedDict()  # Same as in UFOBuilder
        for index, source in enumerate(s for s in sorted_sources if not s.layerName):
            master = self.glyphs_module.GSFontMaster()

            # Filter bracket glyphs out of public.glyphOrder.
            if GLYPH_ORDER_KEY in source.font.lib:
                source.font.lib[GLYPH_ORDER_KEY] = [
                    glyph_name
                    for glyph_name in source.font.lib[GLYPH_ORDER_KEY]
                    if not BRACKET_GLYPH_RE.match(glyph_name)
                ]

            self.to_glyphs_font_attributes(source, master, is_initial=(index == 0))
            self.to_glyphs_master_attributes(source, master)
            self._font.masters.insert(len(self._font.masters), master)
            self._sources[master.id] = source

            # First, move free-standing bracket glyphs back to layers to avoid dealing
            # with GSLayer transplantation.
            for glyph_name in list(source.font.keys()):
                m = BRACKET_GLYPH_RE.match(glyph_name)
                if not m:
                    continue
                bracket_glyph = source.font[glyph_name]
                base_glyph, reverse, threshold = m.groups()
                layer_name = bracket_glyph.lib.get(
                    GLYPHLIB_PREFIX + "_originalLayerName",
                    "{}{}]".format("]" if reverse else "[", threshold),
                )
                # _originalLayerName is an empty string for 'implicit' bracket layers;
                # we don't import these since they were copies of master layers.
                if layer_name:
                    if layer_name not in source.font.layers:
                        ufo_layer = source.font.newLayer(layer_name)
                    else:
                        ufo_layer = source.font.layers[layer_name]
                    bracket_glyph_new = ufo_layer.newGlyph(base_glyph)
                    bracket_glyph_new.copyDataFromGlyph(bracket_glyph)

                    # strip '*.BRACKET.123' suffix from the components' glyph names
                    for comp in bracket_glyph_new.components:
                        m = BRACKET_GLYPH_RE.match(comp.baseGlyph)
                        if m:
                            comp.baseGlyph = m.group("glyph_name")

                # Remove all freestanding bracket layer glyphs from all layers.
                for layer in source.font.layers:
                    if glyph_name in layer:
                        del layer[glyph_name]

            for layer in _sorted_backgrounds_last(source.font.layers):
                self.to_glyphs_layer_lib(layer, master)
                for glyph in layer:
                    self.to_glyphs_glyph(glyph, layer, master)

        self.to_glyphs_features()
        self.to_glyphs_groups()
        self.to_glyphs_kerning()

        # Now that all GSGlyph are built, restore the glyph order
        if self.designspace.sources:
            first_ufo = self.designspace.sources[0].font
            if GLYPH_ORDER_KEY in first_ufo.lib:
                glyph_order = first_ufo.lib[GLYPH_ORDER_KEY]
                lookup = {name: i for i, name in enumerate(glyph_order)}
                self.font.glyphs = sorted(
                    self.font.glyphs, key=lambda glyph: lookup.get(glyph.name, 1 << 63)
                )
            # FIXME: (jany) We only do that on the first one. Maybe we should
            # merge the various `public.glyphorder` values?

            # Restore the layer ordering in each glyph
            for glyph in self._font.glyphs:
                self.to_glyphs_layer_order(glyph)

        self.to_glyphs_family_user_data_from_designspace()
        self.to_glyphs_axes()
        self.to_glyphs_sources()
        self.to_glyphs_instances()

        return self._font

    def _valid_designspace(self, designspace, ufo_module):
        """Make sure that the user-provided designspace has loaded fonts and
        that names are the same as those from the UFOs.
        """
        # TODO: (jany) really make a copy to avoid modifying the original object
        copy = designspace
        # Load only full UFO masters, sparse or "brace" layer sources are assumed
        # to point to existing layers within one of the full masters.
        for source in (s for s in copy.sources if not s.layerName):
            if not hasattr(source, "font") or source.font is None:
                if source.path:
                    # FIXME: (jany) consider not changing the caller's objects
                    source.font = util.open_ufo(source.path, ufo_module.Font)
                else:
                    dirname = os.path.dirname(designspace.path)
                    ufo_path = os.path.join(dirname, source.filename)
                    source.font = util.open_ufo(ufo_path, ufo_module.Font)
            if source.location is None:
                source.location = {}
            for name in ("familyName", "styleName"):
                if getattr(source, name) != getattr(source.font.info, name):
                    self.logger.warning(
                        dedent(
                            """\
                    The {name} is different between the UFO and the designspace source:
                        source filename: {filename}
                        source {name}: {source_name}
                        ufo {name}: {ufo_name}

                    The UFO name will be used.
                    """
                        ).format(
                            name=name,
                            filename=source.filename,
                            source_name=getattr(source, name),
                            ufo_name=getattr(source.font.info, name),
                        )
                    )
                    setattr(source, name, getattr(source.font.info, name))
        # An axis without a mapping will see its range information (min and max
        # values) lost when converted to a Glyps.app file. To combat this we
        # add an explicit identity mapping.
        for axis in copy.axes:
            if axis.map:
                continue
            if axis.minimum == axis.maximum:
                axis.map = [(axis.minimum, axis.minimum)]
            else:
                axis.map = [
                    (axis.minimum, axis.minimum),
                    (axis.maximum, axis.maximum),
                ]
        return copy

    def _fake_designspace(self, ufos):
        """Build a fake designspace with the given UFOs as sources, so that all
        builder functions can rely on the presence of a designspace.
        """
        designspace = designspaceLib.DesignSpaceDocument()

        ufo_to_location = defaultdict(dict)

        # Make weight and width axis if relevant
        for info_key, axis_def in zip(
            ("openTypeOS2WeightClass", "openTypeOS2WidthClass"),
            (WEIGHT_AXIS_DEF, WIDTH_AXIS_DEF),
        ):
            axis = designspace.newAxisDescriptor()
            axis.tag = axis_def.tag
            axis.name = axis_def.name
            mapping = []
            for ufo in ufos:
                user_loc = getattr(ufo.info, info_key)
                if user_loc is not None:
                    design_loc = class_to_value(axis_def.tag, user_loc)
                    mapping.append((user_loc, design_loc))
                    ufo_to_location[id(ufo)][axis_def.name] = design_loc

            mapping = sorted(set(mapping))
            if len(mapping) > 1:
                axis.map = mapping
                axis.minimum = min([user_loc for user_loc, _ in mapping])
                axis.maximum = max([user_loc for user_loc, _ in mapping])
                axis.default = min(
                    axis.maximum, max(axis.minimum, axis_def.default_user_loc)
                )
                designspace.addAxis(axis)

        for ufo in ufos:
            source = designspace.newSourceDescriptor()
            source.font = ufo
            source.familyName = ufo.info.familyName
            source.styleName = ufo.info.styleName
            # source.name = '%s %s' % (source.familyName, source.styleName)
            source.path = ufo.path
            source.location = ufo_to_location[id(ufo)]
            designspace.addSource(source)

        # UFO-level skip list lib keys are usually ignored, except when we don't have a
        # Designspace file to start from. If they exist in the UFOs, promote them to a
        # Designspace-level lib key. However, to avoid accidents, expect the list to
        # exist in none or be the same in all UFOs.
        if any("public.skipExportGlyphs" in ufo.lib for ufo in ufos):
            skip_export_glyphs = {
                frozenset(ufo.lib.get("public.skipExportGlyphs", [])) for ufo in ufos
            }
            if len(skip_export_glyphs) == 1:
                designspace.lib["public.skipExportGlyphs"] = sorted(
                    next(iter(skip_export_glyphs))
                )
            else:
                raise ValueError(
                    "The `public.skipExportGlyphs` list of all UFOs must either not "
                    "exist or be the same in every UFO."
                )

        return designspace

    # Implementation is split into one file per feature
    from .anchors import to_glyphs_glyph_anchors
    from .annotations import to_glyphs_annotations
    from .axes import to_glyphs_axes
    from .background_image import to_glyphs_background_image
    from .blue_values import to_glyphs_blue_values
    from .components import to_glyphs_components, to_glyphs_smart_component_axes
    from .custom_params import to_glyphs_custom_params
    from .features import to_glyphs_features
    from .font import to_glyphs_font_attributes, to_glyphs_ordered_masters
    from .glyph import to_glyphs_glyph, to_glyphs_glyph_height_and_vertical_origin
    from .groups import to_glyphs_groups
    from .guidelines import to_glyphs_guidelines
    from .hints import to_glyphs_hints
    from .instances import to_glyphs_instances
    from .kerning import to_glyphs_kerning
    from .layers import to_glyphs_layer, to_glyphs_layer_order
    from .masters import to_glyphs_master_attributes
    from .names import to_glyphs_family_names, to_glyphs_master_names
    from .paths import to_glyphs_paths
    from .sources import to_glyphs_sources
    from .user_data import (
        to_glyphs_family_user_data_from_designspace,
        to_glyphs_family_user_data_from_ufo,
        to_glyphs_master_user_data,
        to_glyphs_glyph_user_data,
        to_glyphs_layer_lib,
        to_glyphs_layer_user_data,
        to_glyphs_node_user_data,
    )


def _sorted_backgrounds_last(ufo_layers):
    # Stable sort that groups all foregrounds first and all backgrounds last
    return sorted(
        ufo_layers, key=lambda layer: 1 if layer.name.endswith(".background") else 0
    )
