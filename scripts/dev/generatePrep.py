# expand double encodings

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
            

if __name__ == "__main__":
    scriptPath = os.path.split(__file__)[0]
    devPath = os.path.split(scriptPath)[0]
    basePath = os.path.split(devPath)[0] 
    tempPath = os.path.join(basePath, 'sources/2-build/temp')

    paths = []
    for root, dirs, files in os.walk(tempPath):
        for filename in dirs:
            basePath, ext = os.path.splitext(filename)
            if ext in ['.ufo']:
                paths.append(os.path.join(root, filename))
    print tempPath, paths, os.path.exists(tempPath)

    for path in paths:
        f = OpenFont(path, showUI=False)
        d = f.getCharacterMapping()
        
        # duplicate double encoded glyphs
        for g in f:
            if len(g.unicodes) > 1:
                for i, u in enumerate(g.unicodes):
                    if i == 0:
                        g.unicodes = [u]
                    else:
                        newGname = 'uni' + str(dec2hex(u))
    
                        if d.has_key(u):
                            print 'OVERLAP', u, g.name
                        else:
                            newg = f.newGlyph(newGname)
                            newg.appendComponent(g.name)
                            newg.width = g.width
                            newg.unicodes = [u]
                            newg.mark = (1, 0, 0, 1)
        
        # decompose and remove overlap when contours are combined with components
        for g in f:
            if g.components and g.contours:
                g.decompose()
                g.removeOverlap()

        # decompose and remove overlap in select glyphs where components overlap each other
        for gname in ['Aogonek', 'Aogonek.salt', 'Aogonek.v', 'Aogonek.salt_v', 'Ccedilla', 'Ccedilla.v', 'Eogonek.salt', 'Eogonek.salt_v', 'Eogonek', 'Eogonek.v', 'Iogonek', 'Iogonek.salt', 'Iogonek.v', 'Iogonek.salt_v', 'Ohorn', 'Scedilla', 'Scedilla.v', 'Uhorn', 'Uogonek', 'Uogonek.v']:
            if f.has_key(gname):
                f[gname].decompose()
                f[gname].removeOverlap()
      
        # remove scrap glyphs  
        for g in f:
            if '.scrap' in g.name:
                f.removeGlyph(g.name)
        
        f.save()
    print 'done'