from fbits.toolbox.font import FontTX
from fbits.toolbox.glyph import GlyphTX

source = CurrentFont()
dest = AllFonts()[1]
for g in source:
    newName = GlyphTX.name.appendSuffixElement(g.name, 'v')
    if dest.has_key(newName):
        FontTX.glyphs.renameGlyphAndReferences(g.name, newName, source)
    else:
        pass
for groupName, groupGlyphs in source.groups.items():
    newName = groupName+'_vkrn'
    source.groups[newName] = groupGlyphs
    FontTX.kerning.renameReference(groupName, newName, source.kerning)
    del source.groups[groupName]

kernList = []
for pair, value in dest.kerning.items():
    kernList.append((pair, value))
dest.lib['com.fontbureau.verticalKerning'] = kernList
dest.lib['com.fontbureau.verticalGroups'] = dict(dest.groups)