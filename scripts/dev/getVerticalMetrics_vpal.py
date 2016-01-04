
src = OpenFont(u"/Users/david/Dropbox/Typefaces/Bungee/sources/1-drawing/bungee-regular.ufo", showUI=False)
f = CurrentFont()

print 'feature vpal {'

for gname in f.glyphOrder:
    g = f[gname]
    metricsLayer = src[g.name].getLayer('metrics')

    xplacement = 0
    yplacement = 0
    xadvance = 0
    yadvance = 0
    
    if metricsLayer.box:
        metricsLayerHeight = metricsLayer.box[3] - metricsLayer.box[1]

        
        if g.box:
            yTopMargin = f.info.ascender - metricsLayer.box[3]
        else:
            yTopMargin = 0
        if g.box:
            yTopSidebearing = metricsLayer.box[3]-g.box[3]
        else:
            yTopSidebearing = 0
        yadvance =  int(metricsLayerHeight - 1000)
        yplacement = int(yTopMargin - yTopSidebearing)

        print '\tpos %s <%s %s %s %s>; # %s %s' % (g.name, xplacement, yplacement, xadvance, yadvance, yTopMargin, yTopSidebearing)



    

print '} vpal;'