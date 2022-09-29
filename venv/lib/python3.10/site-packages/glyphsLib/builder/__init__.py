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

from .builders import UFOBuilder, GlyphsBuilder

logger = logging.getLogger(__name__)


def to_ufos(
    font,
    include_instances=False,
    family_name=None,
    propagate_anchors=None,
    ufo_module=None,
    minimize_glyphs_diffs=False,
    generate_GDEF=True,
    store_editor_state=True,
    write_skipexportglyphs=False,
    minimal=False,
    glyph_data=None,
):
    """Take a GSFont object and convert it into one UFO per master.

    Takes in data as Glyphs.app-compatible classes, as documented at
    https://docu.glyphsapp.com/

    If include_instances is True, also returns the parsed instance data.

    If family_name is provided, the master UFOs will be given this name and
    only instances with this name will be returned.

    If generate_GDEF is True, write a `table GDEF {...}` statement in the
    UFO's features.fea, containing GlyphClassDef and LigatureCaretByPos.

    If minimal is True, it is assumed that the UFOs will only be used in
    font production, and unnecessary steps (e.g. converting background layers)
    will be skipped.
    """
    builder = UFOBuilder(
        font,
        ufo_module=ufo_module,
        family_name=family_name,
        propagate_anchors=propagate_anchors,
        minimize_glyphs_diffs=minimize_glyphs_diffs,
        generate_GDEF=generate_GDEF,
        store_editor_state=store_editor_state,
        write_skipexportglyphs=write_skipexportglyphs,
        minimal=minimal,
        glyph_data=glyph_data,
    )

    result = list(builder.masters)

    if include_instances:
        return result, builder.instance_data
    return result


def to_designspace(
    font,
    family_name=None,
    instance_dir=None,
    propagate_anchors=None,
    ufo_module=None,
    minimize_glyphs_diffs=False,
    generate_GDEF=True,
    store_editor_state=True,
    write_skipexportglyphs=False,
    minimal=False,
    glyph_data=None,
):
    """Take a GSFont object and convert it into a Designspace Document + UFOS.
    The UFOs are available as the attribute `font` of each SourceDescriptor of
    the DesignspaceDocument:

        ufos = [source.font for source in designspace.sources]

    The designspace and the UFOs are not written anywhere by default, they
    are all in-memory. If you want to write them to the disk, consider using
    the `filename` attribute of the DesignspaceDocument and of its
    SourceDescriptor as possible file names.

    Takes in data as Glyphs.app-compatible classes, as documented at
    https://docu.glyphsapp.com/

    If include_instances is True, also returns the parsed instance data.

    If family_name is provided, the master UFOs will be given this name and
    only instances with this name will be returned.

    If generate_GDEF is True, write a `table GDEF {...}` statement in the
    UFO's features.fea, containing GlyphClassDef and LigatureCaretByPos.
    """
    builder = UFOBuilder(
        font,
        ufo_module=ufo_module,
        family_name=family_name,
        instance_dir=instance_dir,
        propagate_anchors=propagate_anchors,
        use_designspace=True,
        minimize_glyphs_diffs=minimize_glyphs_diffs,
        generate_GDEF=generate_GDEF,
        store_editor_state=store_editor_state,
        write_skipexportglyphs=write_skipexportglyphs,
        minimal=minimal,
        glyph_data=glyph_data,
    )
    return builder.designspace


def to_glyphs(
    ufos_or_designspace,
    glyphs_module=classes,
    ufo_module=None,
    minimize_ufo_diffs=False,
):
    """
    Take a list of UFOs or a single DesignspaceDocument with attached UFOs
    and converts it into a GSFont object.

    The GSFont object is in-memory, it's up to the user to write it to the disk
    if needed.

    This should be the inverse function of `to_ufos` and `to_designspace`,
    so we should have to_glyphs(to_ufos(font)) == font
    and also to_glyphs(to_designspace(font)) == font
    """
    if hasattr(ufos_or_designspace, "sources"):
        builder = GlyphsBuilder(
            designspace=ufos_or_designspace,
            glyphs_module=glyphs_module,
            ufo_module=ufo_module,
            minimize_ufo_diffs=minimize_ufo_diffs,
        )
    else:
        builder = GlyphsBuilder(
            ufos=ufos_or_designspace,
            glyphs_module=glyphs_module,
            ufo_module=ufo_module,
            minimize_ufo_diffs=minimize_ufo_diffs,
        )
    return builder.font
