f = CurrentFont()
for gname in f.selection:
    g = f[gname]
    uc = g.name.capitalize()
    if gname in ['ae', 'ij', 'oe']:
        uc = g.name.upper()
    elif gname == 'dotlessi':
        uc = 'I'
    if f.has_key(uc):
        g.clear()
        g.appendComponent(uc)
        g.width = f[uc].width
print 'done'
