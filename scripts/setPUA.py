import os, sys

def dec2hex(n, uni = 1):
        hex = "%X" % n
        if uni == 1:
            while len(hex) <= 3:
                hex = '0' + str(hex)
        return hex

def hex2dec(s):
        try:
            return int(s, 16)
        except:
            pass
            


exceptions = ['.notdef',
'nbspace',
'Tcedilla',
'tcedilla',
'macroncmb',
'commaaccentcmb',
'fi',
'fl',
'one.sups',
'two.sups',
'three.sups',
'four.sups',
'acute.vert',
'grave.vert',
'brevehookabove',
'circumflexacute',
'circumflexhookabove',
'breveacute',
'circumflextilde',
'brevegrave',
'brevetilde',
'circumflexgrave']

f = CurrentFont()
for g in f:
    if g.unicodes == [hex2dec('E100')]:
        g.unicodes = []

u = hex2dec('E100')

for gname in f.glyphOrder:
    g = f[gname]
    if f.has_key(gname) and not g.unicodes and gname not in exceptions:
        print gname, dec2hex(u)
        g.unicodes = [u]
        u+=1