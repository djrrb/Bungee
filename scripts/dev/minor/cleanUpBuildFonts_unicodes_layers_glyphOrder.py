src = CurrentFont()




for path in [u"/Users/david/Dropbox/Typefaces/Bungee/sources/1-drawing/Bungee_Rotated-Regular.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Hairline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Inline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Outline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Basic/Bungee-Shade.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Inline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Outline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Regular.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers/Bungee_Layers-Shade.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Inline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Outline.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Regular.ufo", u"/Users/david/Dropbox/Typefaces/Bungee/sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Shade.ufo"]:
    f = OpenFont(path)
    f.glyphOrder = src.glyphOrder
    for i in range(4):
        for layerName in f.layerOrder:
            f.removeLayer(layerName)
    for g in f:
        if src.has_key(g.name):
            g.unicodes = src[g.name].unicodes
    f.save()
    f.close()
print 'done'
        