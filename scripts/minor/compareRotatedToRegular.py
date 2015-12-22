f = CurrentFont()
src = AllFonts()[1]

for g in f:
    if src.has_key(g.name):
        srcg = src[g.name]
        g.leftMargin = srcg.leftMargin
        g.rightMargin = srcg.rightMargin
        if g.width != srcg.width:
            print g.name, g.width, srcg.width
        else:
            print g.name, 'match!'
    else:
        print '\t\tmissing', g.name
print 'done'