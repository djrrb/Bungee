# Break out Layers
# Derive layer sources from the master
# This script uses Robofont-specific layer capabilities.

import os

def getVerticalName(gname):
    if '.' in gname:
        baseName, suffix = gname.split('.')
        suffixes = suffix.split('_')
    else:
        baseName = gname
        suffixes = []
    if 'v' in suffixes:
        return gname
    else:
        suffixes.append('v')
        return baseName + '.' + '_'.join(suffixes)

def getHorizontalName(gname):
    if '.' in gname:
        baseName, suffix = gname.split('.')
        suffixes = suffix.split('_')
    else:
        baseName = gname
        suffixes = []
    if 'v' in suffixes:
        suffixes.pop(suffixes.index('v'))
        if suffixes:
            return baseName + '.' + '_'.join(suffixes)
        else:
            return baseName
    else:
        return gname

def renameGlyphAndReferences(fromName, toName, f):
    f[fromName].name = toName
    for g in f:
        for d in g.components:
            if d.baseGlyph == fromName:
                d.baseGlyph = toName
    for groupName, groupGlyphs in f.groups.items():
        if fromName in groupGlyphs:
            f.groups[groupName][groupGlyphs.index(fromName)] = toName
    for pair, value in f.kerning.items():
        l, r = pair
        if l == fromName or r == fromName:
            del f.kerning[pair]
            if l == fromName:
                l = toName
            if r == fromName:
                r = toName
            f.kerning[(l, r)] = value
            
def removeGlyphAndDecomposeReferences(gname, f):
    for g in f:
        for d in g.components:
            if d.baseGlyph == gname:
                d.decompose()
    f.removeGlyph(gname)
    
def breakdownComponents(g):
    f = g.getParent()
    for d in g.components:
        baseGlyph = f[d.baseGlyph]
        xoffset, yoffset = d.offset
        g.removeComponent(d)
        for c in baseGlyph.copy():
            c.move((xoffset, yoffset))
            g.appendContour(c)
        for bgd in baseGlyph.components:
            x = bgd.offset[0] + xoffset
            y = bgd.offset[1] + yoffset
            g.appendComponent(bgd.baseGlyph, (x, y))

if __name__ == "__main__":
    # get the source
    scriptPath = os.path.split(__file__)[0]
    basePath = os.path.split(scriptPath)[0]
    sourcesPath = os.path.join(basePath, 'sources')
    src = OpenFont(os.path.join(sourcesPath, '1-drawing/Bungee-Regular.ufo'), showUI=False)

    f = src.copy()
    path = os.path.join(sourcesPath, '2-build/Bungee_Vertical-Regular.ufo')
    f.save(path)
    f.info.familyName = 'Bungee Vertical'
    
    replaceMap = {}
    
    for g in f:
        vName = getVerticalName(g.name)
        hName = getHorizontalName(g.name)
        print g.name, hName, vName
        if 'scrap' in g.name:
            f.removeGlyph(g.name)
            continue
        if g.name == hName and f.has_key(vName):
            replaceMap[vName] = hName
        
    print replaceMap
    
    # break down components so that they don't reference themselves
    for vName, hName in replaceMap.items():
        breakdownComponents(f[vName])
    
    for vName, hName in replaceMap.items():
        unicodes = f[vName].unicodes + f[hName].unicodes
        renameGlyphAndReferences(hName, hName+'_____', f)
        renameGlyphAndReferences(vName, hName, f)
        f[hName].unicodes = unicodes
        
    for vName, hName in replaceMap.items():
        removeGlyphAndDecomposeReferences(hName+'_____', f)
    
    for g in f:
        if g.width not in [f.info.unitsPerEm, f.info.unitsPerEm/2]:
            widthDiff = f.info.unitsPerEm - g.width
            move = int(widthDiff/2)
            for c in g:
                c.move((move, 0))
            g.width = f.info.unitsPerEm
            
    for gname in ['a', 'agrave', 'aacute', 'acircumflex', 'atilde', 'adieresis', 'aring', 'amacron', 'abreve', 'aogonek', 'b', 'c', 'ccedilla', 'cacute', 'ccircumflex', 'cdotaccent', 'ccaron', 'd', 'dcaron', 'e', 'egrave', 'eacute', 'ecircumflex', 'edieresis', 'emacron', 'ebreve', 'edotaccent', 'eogonek', 'ecaron', 'f', 'g', 'gcircumflex', 'gbreve', 'gdotaccent', 'gcommaaccent', 'h', 'hcircumflex', 'i', 'igrave', 'iacute', 'icircumflex', 'idieresis', 'itilde', 'imacron', 'ibreve', 'iogonek', 'j', 'jcircumflex', 'k', 'kcommaaccent', 'l', 'lacute', 'lcommaaccent', 'lcaron', 'm', 'n', 'ntilde', 'nacute', 'ncommaaccent', 'ncaron', 'o', 'ograve', 'oacute', 'ocircumflex', 'otilde', 'odieresis', 'omacron', 'obreve', 'ohungarumlaut', 'p', 'q', 'r', 'racute', 'rcommaaccent', 'rcaron', 's', 'sacute', 'scircumflex', 'scedilla', 'scaron', 'scommaaccent', 't', 'tcommaaccent', 'tcaron', 'u', 'ugrave', 'uacute', 'ucircumflex', 'udieresis', 'utilde', 'umacron', 'ubreve', 'uring', 'uhungarumlaut', 'uogonek', 'v', 'w', 'wcircumflex', 'wgrave', 'wacute', 'wdieresis', 'x', 'y', 'yacute', 'ydieresis', 'ycircumflex', 'ygrave', 'z', 'zacute', 'zdotaccent', 'zcaron', 'germandbls', 'ae', 'eth', 'oslash', 'thorn', 'dcroat', 'hbar', 'dotlessi', 'ij', 'ldot', 'lslash', 'eng', 'oe', 'tbar']:
        g = f[gname]
        g.clear()
        srcName = g.name.capitalize()
        # this is hacky, but...
        if srcName == 'Oe':
            srcName = 'OE'
        elif srcName == 'Ae':
            srcName = 'AE'
        elif srcName == 'Dotlessi':
            srcName = 'I'
        elif srcName == 'Ij':
            srcName = 'IJ'
        g.clear()
        g.appendComponent(srcName)
        g.width = f[srcName].width
    f.save()
print 'done'