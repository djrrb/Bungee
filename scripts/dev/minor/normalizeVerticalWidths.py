f = CurrentFont()
for gname in f.glyphOrder:
    g = f[gname]
    if g.width != 1000:
        w = g.width
        widthAdjust = int(1000 - w)
        leftAdjust = int(round(widthAdjust/2))
        print "pos %s <%s %s %s %s>;" % (g.name, leftAdjust, 0, widthAdjust, 0)