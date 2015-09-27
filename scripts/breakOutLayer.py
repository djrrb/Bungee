# Break out Layers
# Derive layer sources from the master
# This script uses Robofont-specific layer capabilities.

import os

if __name__ == "__main__":
    # get the source
    scriptPath = os.path.split(__file__)[0]
    basePath = os.path.split(scriptPath)[0]
    sourcesPath = os.path.join(basePath, 'sources')
    src = OpenFont(os.path.join(sourcesPath, '1-drawing/Bungee-Regular.ufo'), showUI=False)

    # define layer names that we want to break out
    layerNames = ['inline', 'outline', 'shade']

    for layerName in layerNames:
        # make a copy of the UFO
        f = src.copy()
        path = os.path.join(sourcesPath, '2-build/Bungee-%s.ufo' % layerName.capitalize())
        f.save(path)
        # for each glyph, clear contours and replace them with those in the named layer. Leave components alone.
        for g in f:
            g.clearContours()
            l = g.getLayer(layerName)
            for c in l:
                g.appendContour(c)
        f.save()