f = CurrentFont()
for g in f:
    if '.alt001' in g.name:
        print g.name
        sourceName = g.name.replace('.alt001', '')
        g.clearContours()
        g.clearComponents()
        g.appendComponent(sourceName)