f = CurrentFont()

target = 1280


for gname in f.glyphOrder:
    g = f[gname]
    metrics = g.getLayer('metrics')
    
    leftAdjust = 0
    topAdjust = 0
    widthAdjust = 0
    heightAdjust = 0
    
    if metrics.box:
       w = metrics.box[3] - metrics.box[1]
       heightAdjust = int(target - w)
       topAdjust = -int(round(heightAdjust/2))
    #else:
    #   heightAdjust = 280
    #   topAdjust = 140
    
    #if g.width != target:
    #    w = g.width
    #    widthAdjust = int(target - w)
    #    leftAdjust = int(round(widthAdjust/2))
        
    if leftAdjust or topAdjust or widthAdjust or heightAdjust:
        print "\tpos %s <%s %s %s %s>;" % (g.name, leftAdjust, topAdjust, widthAdjust, heightAdjust)
    #else:
        #print '\t#all good for', g.name
