f = CurrentFont()
for gname in f.selection:
    g = f[gname]
    foreground = g.copy()
    g.clearContours()
    for i, layerName in enumerate(['inline']):
        if layerName == 'foreground':
            l = foreground
        else:
            l = g.getLayer(layerName)
        lc = l.copy()
        lc.removeOverlap()
        if i % 2:
            lc.correctDirection(True)
        else:
            lc.correctDirection()
        g.appendGlyph(lc)
        
        

print 'done'