def 
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
