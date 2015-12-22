# expand double encodings

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
    f = CurrentFont()

    d = f.getCharacterMapping()

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
