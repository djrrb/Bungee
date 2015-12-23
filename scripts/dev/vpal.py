
f = CurrentFont() # Bungee-Regular
src = AllFonts()[1] # BungeeRotated-Regular

print 'feature vpal {'

for g in f:
    if g.selected:
        gname = g.name        
        if f.has_key(gname):
            xplacement = 0
            yplacement = 0
            xadvance = 0
            yadvance = 0
        
            if g.box:
                yTopMargin = g.getParent().info.ascender - g.box[3]
            else:
                yTopMargin = 0
            yadvance =  int(src[gname].width - 1000)
            yplacement = int(yTopMargin - src[gname].leftMargin)
    
            print '\tpos %s <%s %s %s %s>;' % (g.name, xplacement, yplacement, xadvance, yadvance)
    
print '} vpal;'