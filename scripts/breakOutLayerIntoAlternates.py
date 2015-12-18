# Break out Layers
# Derive layer sources from the master
# This script uses Robofont-specific layer capabilities.

import os
glyphOrderKey = 'public.glyphOrder'

if __name__ == "__main__":
    # get the source
    scriptPath = os.path.split(__file__)[0]
    basePath = os.path.split(scriptPath)[0]
    sourcesPath = os.path.join(basePath, 'sources')
    src = OpenFont(os.path.join(sourcesPath, '1-drawing/Bungee-Regular.ufo'), showUI=False)
    f = src.copy()
    path = os.path.join(sourcesPath, '2-build/temp/Bungee_Color-Regular.ufo')
    f.save(path)

    # define layer names that we want to break out
    layerNames = ['shade', 'foreground', 'inline']

    newGlyphOrder = src.lib[glyphOrderKey]
    for gname in src.lib[glyphOrderKey]:
        if src.has_key(gname):
            g = src[gname]
        else:
            continue
        for i, layerName in enumerate(layerNames):
            suffix = '.alt' + str("%03d" %i)
            l = g.getLayer(layerName)
            n = f.newGlyph(g.name+suffix)
            n.width = l.width
            for c in l:
                n.appendContour(c)
            for d in g.components:
                n.appendComponent(d.baseGlyph+suffix, offset=d.offset, scale=d.scale)
            newGlyphOrder.append(n.name)


    f.features.text = 'include(../../1-drawing/features.fea);'

    f.lib[glyphOrderKey] = newGlyphOrder
    f.save()