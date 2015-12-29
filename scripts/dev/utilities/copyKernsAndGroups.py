src = OpenFont(u"/Users/david/Dropbox/Typefaces/Bungee/sources/1-drawing/Bungee-Regular.ufo", showUI=False)

for path in [u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Hairline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Inline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Outline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Shade.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Color/Bungee_Color-Regular.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Inline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Outline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Regular.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Shade.ufo"]:
    f = OpenFont(path, showUI=False)
    f.kerning.clear()
    f.kerning.update(src.kerning.asDict())
    f.groups.clear()
    for groupName, groupGlyphs in src.groups.items():
        f.groups[groupName] = groupGlyphs
    if f.has_key('K.salt2'):
        f.removeGlyph('K.salt2')
    f.save()
    
        