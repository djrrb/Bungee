f = CurrentFont()

def vName(gname):
    if '.' in gname:
        return gname + '_v'
    else:
        return gname + '.v'
        

dest = AllFonts()[1]
for g in f:
    vname = vName(g.name)
    if dest.has_key(vname):
        topMargin = g.leftMargin
        bottomMargin = g.rightMargin
        
        vg = dest[vname]
        
        if vg.box:
            top = vg.box[3] + topMargin
            bottom = vg.box[1] - bottomMargin
        
        
        
            m = vg.getLayer('metrics')
            m.clear()
            sbPen = m.getPen()
            sbPen.moveTo((0, bottom))
            sbPen.lineTo((0, top))
            sbPen.lineTo((vg.width, top))
            sbPen.lineTo((vg.width, bottom))
            sbPen.closePath()
    else:
        print vname
print 'done'
    