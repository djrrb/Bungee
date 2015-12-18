f = CurrentFont()
src = AllFonts()[1]
f.kerning.clear()
f.groups.clear()

for groupName, groupGlyphs in src.groups.items():
    f.groups[groupName] = groupGlyphs

f.kerning.update(src.kerning.asDict())
