# Break out Layers
# Derive layer sources from the master
# This script uses Robofont-specific layer capabilities.

import os

if __name__ == "__main__":

    # get the sources
    scriptPath = os.path.split(os.path.split(__file__)[0])[0]
    basePath = os.path.split(scriptPath)[0]
    sourcesPath = os.path.join(basePath, 'sources')
    src1 = OpenFont(os.path.join(sourcesPath, '1-drawing/Bungee-Regular.ufo'), showUI=False)
    src2 = OpenFont(os.path.join(sourcesPath, '1-drawing/Bungee_Rotated-Regular.ufo'), showUI=False)
    
    basicName = 'Bungee'
    advancedName = 'Bungee Layers'
    verticalName = 'Bungee Layers Vertical'
    rotateName = 'Bungee Layers Rotated'

    # define the styles we want to build
    buildStyles = [

        
             ##################
             
            {
                'familyName': advancedName,
                'styleName': 'Regular',
                'source': src1,
                'layers': ['foreground'],
                'tracking': 0,
            },     
            {
                'familyName': advancedName,
                'styleName': 'Inline',
                'source': src1,
                'layers': ['inline'],
                'tracking': 0,
            },     
            {
                'familyName': advancedName,
                'styleName': 'Outline',
                'source': src1,
                'layers': ['outline'],
                'tracking': 0,
            },
            {
                'familyName': advancedName,
                'styleName': 'Shade',
                'source': src1,
                'layers': ['shade'],
                'tracking': 0,
            },    
            
        ]


    buildStyles_rotated = [

        
             ##################
             
            {
                'familyName': rotateName,
                'styleName': 'Regular',
                'source': src2,
                'layers': ['foreground'],
                'tracking': 0,
                'features': 'vertical',
            },     
            {
                'familyName': rotateName,
                'styleName': 'Inline',
                'source': src2,
                'layers': ['inline'],
                'tracking': 0,
                'features': 'vertical',
            },     
            {
                'familyName': rotateName,
                'styleName': 'Outline',
                'source': src2,
                'layers': ['outline'],
                'tracking': 0,
                'features': 'vertical',
            },
            {
                'familyName': rotateName,
                'styleName': 'Shade',
                'source': src2,
                'layers': ['shade'],
                'tracking': 0,
                'features': 'vertical',
            },    
            
        ]


    buildStyles_basic = [
        
            {
                'familyName': basicName,
                'styleName': 'Hairline',
                'source': src1,
                'layers': ['inline'],
                'tracking': 0,
            },
            {
                'familyName': basicName,
                'styleName': 'Inline',
                'source': src1,
                'layers': ['foreground', 'inline'],
                'tracking': 0,
            },
            {
                'familyName': basicName,
                'styleName': 'Outline',
                'source': src1,
                'layers': ['outline', 'foreground', 'inline'],
                'tracking': 0,
            }, 
            {
                'familyName': basicName,
                'styleName': 'Shade',
                'source': src1,
                'layers': ['shade', 'foreground', 'inline'],
                'tracking': 150,
            },

        ]
        
    for styleMap in buildStyles + buildStyles_basic + buildStyles_rotated:
        
        # make a copy of the UFO
        familyName = styleMap['familyName'] 
        styleName = styleMap['styleName']
        src = styleMap['source']
        f = src.copy()
        path = os.path.join(sourcesPath, '2-build/temp/%s-%s.ufo' % (familyName.replace(' ', '_'), styleName.replace(' ', '_')))
        f.save(path)
        # change the font info
        f.info.familyName = familyName
        f.info.styleName = styleName
        if styleMap.get('features') == 'vertical':
            f.features.text = 'include(../../1-drawing/features_vertical.fea);'
        else:
            f.features.text = 'include(../../1-drawing/features.fea);'

        # get rid of excess layers
        for l in f.layerOrder:
            f.removeLayer(l)
            f.save()
        # for each glyph, clear contours and replace them with those in the named layer. Leave components alone.
        for g in f:
            # remove scrap glyphs
            if 'scrap' in g.name:
                f.removeGlyph(g.name)
                continue
            # clear the glyph
            g.clearContours()
            # get the layer glyph
            for i, layerName in enumerate(styleMap['layers']):
                if layerName == 'foreground':
                    l = src[g.name].copy()
                else:
                    l = src[g.name].getLayer(layerName).copy()
                # remove overlap and reposition
                l.removeOverlap()
                l.move((styleMap['tracking']/2, 0))
                g.width += styleMap['tracking']
                # alternate path direction
                if i % 2:
                    l.correctDirection(True)
                else:
                    l.correctDirection()
                # add the contour
                for c in l:
                    g.appendContour(c)
        f.save()
    print 'done'