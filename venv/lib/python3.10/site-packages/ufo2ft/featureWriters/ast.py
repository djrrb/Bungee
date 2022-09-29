"""Helpers to build or extract data from feaLib AST objects."""


import collections
import functools
import operator
import re

# we re-export here all the feaLib AST classes so they can be used from
# writer modules with a single `from ufo2ft.featureWriters import ast`
import sys

from fontTools import unicodedata
from fontTools.feaLib import ast

self = sys.modules[__name__]
for name in getattr(ast, "__all__", dir(ast)):
    if isinstance(getattr(ast, name), type):
        setattr(self, name, getattr(ast, name))
del sys, self, name


def getScriptLanguageSystems(feaFile):
    """Return dictionary keyed by Unicode script code containing lists of
    (OT_SCRIPT_TAG, [OT_LANGUAGE_TAG, ...]) tuples (excluding "DFLT").
    """
    languagesByScript = collections.OrderedDict()
    for ls in [
        st for st in feaFile.statements if isinstance(st, ast.LanguageSystemStatement)
    ]:
        if ls.script == "DFLT":
            continue
        languagesByScript.setdefault(ls.script, []).append(ls.language)

    langSysMap = collections.OrderedDict()
    for script, languages in languagesByScript.items():
        sc = unicodedata.ot_tag_to_script(script)
        langSysMap.setdefault(sc, []).append((script, languages))
    return langSysMap


def iterFeatureBlocks(feaFile, tag=None):
    for statement in feaFile.statements:
        if isinstance(statement, ast.FeatureBlock):
            if tag is not None and statement.name != tag:
                continue
            yield statement


def findFeatureTags(feaFile):
    return {f.name for f in iterFeatureBlocks(feaFile)}


def findCommentPattern(feaFile, pattern):
    """
    Yield a tuple of statements, starting with the parent block, followed by
    nested blocks if present, ending with the comment matching a given pattern.
    There is not parent block if the matched comment is a the root level.
    """
    for statement in feaFile.statements:
        if hasattr(statement, "statements"):
            for res in findCommentPattern(statement, pattern):
                yield (statement, *res)
        elif isinstance(statement, ast.Comment):
            if re.match(pattern, str(statement)):
                yield (statement,)


def findTable(feaLib, tag):
    for statement in feaLib.statements:
        if isinstance(statement, ast.TableBlock) and statement.name == tag:
            return statement


def iterClassDefinitions(feaFile, featureTag=None):
    if featureTag is None:
        # start from top-level class definitions
        for s in feaFile.statements:
            if isinstance(s, ast.GlyphClassDefinition):
                yield s
    # then iterate over per-feature class definitions
    for fea in iterFeatureBlocks(feaFile, tag=featureTag):
        for s in fea.statements:
            if isinstance(s, ast.GlyphClassDefinition):
                yield s


LOOKUP_FLAGS = {
    "RightToLeft": 1,
    "IgnoreBaseGlyphs": 2,
    "IgnoreLigatures": 4,
    "IgnoreMarks": 8,
}


def makeLookupFlag(flags=None, markAttachment=None, markFilteringSet=None):
    if isinstance(flags, str):
        value = LOOKUP_FLAGS[flags]
    elif flags is not None:
        value = functools.reduce(operator.or_, [LOOKUP_FLAGS[n] for n in flags], 0)
    else:
        value = 0

    if markAttachment is not None:
        assert isinstance(markAttachment, ast.GlyphClassDefinition)
        markAttachment = ast.GlyphClassName(markAttachment)

    if markFilteringSet is not None:
        assert isinstance(markFilteringSet, ast.GlyphClassDefinition)
        markFilteringSet = ast.GlyphClassName(markFilteringSet)

    return ast.LookupFlagStatement(
        value, markAttachment=markAttachment, markFilteringSet=markFilteringSet
    )


def makeGlyphClassDefinitions(groups, feaFile=None, stripPrefix=""):
    """Given a groups dictionary ({str: list[str]}), create feaLib
    GlyphClassDefinition objects for each group.
    Return a dict keyed by the original group name.

    If `stripPrefix` (str) is provided and a group name starts with it,
    the string will be stripped from the beginning of the class name.
    """
    classDefs = {}
    if feaFile is not None:
        classNames = {cdef.name for cdef in iterClassDefinitions(feaFile)}
    else:
        classNames = set()
    lengthPrefix = len(stripPrefix)
    for groupName, members in sorted(groups.items()):
        originalGroupName = groupName
        if stripPrefix and groupName.startswith(stripPrefix):
            groupName = groupName[lengthPrefix:]
        className = makeFeaClassName(groupName, classNames)
        classNames.add(className)
        classDef = makeGlyphClassDefinition(className, members)
        classDefs[originalGroupName] = classDef
    return classDefs


def makeGlyphClassDefinition(className, members):
    glyphNames = [ast.GlyphName(g) for g in members]
    glyphClass = ast.GlyphClass(glyphNames)
    classDef = ast.GlyphClassDefinition(className, glyphClass)
    return classDef


def makeFeaClassName(name, existingClassNames=None):
    """Make a glyph class name which is legal to use in feature text.

    Ensures the name only includes characters in "A-Za-z0-9._", and
    isn't already defined.
    """
    name = re.sub(r"[^A-Za-z0-9._]", r"", name)
    if existingClassNames is None:
        return name
    i = 1
    origName = name
    while name in existingClassNames:
        name = "%s_%d" % (origName, i)
        i += 1
    return name


def addLookupReferences(
    feature, lookups, script=None, languages=None, exclude_dflt=False
):
    """Add references to named lookups to the feature's statements.
    If `script` (str) and `languages` (sequence of str) are provided,
    only register the lookup for the given script and languages,
    optionally with `exclude_dflt` directive.
    Otherwise add a global reference which will be registered for all
    the scripts and languages in the feature file's `languagesystems`
    statements.
    """
    assert lookups
    if not script:
        for lookup in lookups:
            feature.statements.append(ast.LookupReferenceStatement(lookup))
        return

    feature.statements.append(ast.ScriptStatement(script))
    if exclude_dflt:
        for language in languages or ("dflt",):
            feature.statements.append(
                ast.LanguageStatement(language, include_default=False)
            )
            for lookup in lookups:
                feature.statements.append(ast.LookupReferenceStatement(lookup))
    else:
        feature.statements.append(ast.LanguageStatement("dflt", include_default=True))
        for lookup in lookups:
            feature.statements.append(ast.LookupReferenceStatement(lookup))
        for language in languages or ():
            if language == "dflt":
                continue
            feature.statements.append(
                ast.LanguageStatement(language, include_default=True)
            )


_GDEFGlyphClasses = collections.namedtuple(
    "_GDEFGlyphClasses", "base ligature mark component"
)


def getGDEFGlyphClasses(feaLib):
    """Return GDEF GlyphClassDef base/mark/ligature/component glyphs, or
    None if no GDEF table is defined in the feature file.
    """
    for s in feaLib.statements:
        if isinstance(s, ast.TableBlock) and s.name == "GDEF":
            for st in s.statements:
                if isinstance(st, ast.GlyphClassDefStatement):
                    return _GDEFGlyphClasses(
                        frozenset(st.baseGlyphs.glyphSet())
                        if st.baseGlyphs is not None
                        else frozenset(),
                        frozenset(st.ligatureGlyphs.glyphSet())
                        if st.ligatureGlyphs is not None
                        else frozenset(),
                        frozenset(st.markGlyphs.glyphSet())
                        if st.markGlyphs is not None
                        else frozenset(),
                        frozenset(st.componentGlyphs.glyphSet())
                        if st.componentGlyphs is not None
                        else frozenset(),
                    )
    return _GDEFGlyphClasses(None, None, None, None)
