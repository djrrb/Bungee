from compositor.caseConversionMaps import upperToSingleLower
f = CurrentFont()
for g in f:
    gname = g.name
    for u in g.unicodes:
        if upperToSingleLower.has_key(u):
            l = upperToSingleLower[u]
            g.unicodes = g.unicodes + [l]
            