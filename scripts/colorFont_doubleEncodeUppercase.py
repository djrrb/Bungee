from fbits.constants import Constants as C
o = C.UNICODE_UPPER_TO_SINGLE_LOWER
f = CurrentFont()
for g in f:
    gname = g.name
    for u in g.unicodes:
        if o.has_key(u):
            l = o[u]
            g.unicodes = g.unicodes + [l]
            