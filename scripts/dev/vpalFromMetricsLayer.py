
f = CurrentFont() # Bungee-Regular

print 'feature vpal {'

for gname in f.glyphOrder:
    g = f[gname]
    metricsLayer = g.getLayer('metrics')
    
    xplacement = 0
    yplacement = 0
    xadvance = 0
    yadvance = 0
    
    if metricsLayer.box:
        metricsLayerHeight = metricsLayer.box[3] - metricsLayer.box[1]

        
        if g.box:
            yTopMargin = f.info.ascender - g.box[3]
        else:
            yTopMargin = 0
        yadvance =  int(metricsLayerHeight - 1000)
        yplacement = int(yTopMargin- (metricsLayer.box[3]-g.box[3]))

        print '\tpos %s <%s %s %s %s>;' % (g.name, xplacement, yplacement, xadvance, yadvance)



    

print '} vpal;'