# Break out Layers
# Derive layer sources from the master
# This script uses Robofont-specific layer capabilities.

import os

if __name__ == "__main__":

    # get the sources
    scriptPath = os.path.split(__file__)[0]
    basePath = os.path.split(scriptPath)[0]
    sourcesPath = os.path.join(basePath, 'sources')
    src1 = OpenFont(os.path.join(sourcesPath, '1-drawing/Bungee-Regular.ufo'), showUI=False)
    src2 = OpenFont(os.path.join(sourcesPath, '2-build/Bungee_Vertical-Regular.ufo'), showUI=False)
    
    basicName = 'Bungee Basic'
    advancedName = 'Bungee'
    verticalName = 'Bungee Vertical'
    rotateName = 'Bungee Rotate'

    # define the styles we want to build
    buildStyles = [
            
            {
                'familyName': basicName,
                'styleName': 'Regular',
                'source': src1,
                'layers': ['foreground'],
                'tracking': 0,
            },     
            {
                'familyName': basicName,
                'styleName': 'Inline',
                'source': src1,
                'layers': ['inline'],
                'tracking': 0,
            },     
            {
                'familyName': basicName,
                'styleName': 'Outline',
                'source': src1,
                'layers': ['outline'],
                'tracking': 0,
            },
            {
                'familyName': basicName,
                'styleName': 'Shade',
                'source': src1,
                'layers': ['shade'],
                'tracking': 0,
            },    
        
             ##################
             
            {
                'familyName': verticalName,
                'styleName': 'Regular',
                'source': src2,
                'layers': ['foreground'],
                'tracking': 0,
            },     
            {
                'familyName': verticalName,
                'styleName': 'Inline',
                'source': src2,
                'layers': ['inline'],
                'tracking': 0,
            },     
            {
                'familyName': verticalName,
                'styleName': 'Outline',
                'source': src2,
                'layers': ['outline'],
                'tracking': 0,
            },
            {
                'familyName': verticalName,
                'styleName': 'Shade',
                'source': src2,
                'layers': ['shade'],
                'tracking': 0,
            },    
            
            ##################
            {
                'familyName': basicName,
                'styleName': 'Regular',
                'source': src1,
                'layers': ['foreground'],
                'tracking': 0,
            },
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

    buildStyles = [
        
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
        
    for styleMap in buildStyles:
        
        # make a copy of the UFO
        familyName = styleMap['familyName'] 
        styleName = styleMap['styleName']
        src = styleMap['source']
        f = src.copy()
        path = os.path.join(sourcesPath, '2-build/%s-%s.ufo' % (familyName.replace(' ', '_'), styleName.replace(' ', '_')))
        f.save(path)
        # change the font info
        f.info.familyName = familyName
        f.info.styleName = styleName
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
                elif layerName == 'cameo':
                    l = src['uni2B24.salt'].copy()
                    l.move((-140, 0))
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