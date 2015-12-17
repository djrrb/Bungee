source = CurrentFont()

for  g in source:
    g.decompose()

for sg in source:
        for layername in source.layerOrder:
            if layername != 'foreground':
                g = sg.getLayer(layername)
            topMargin = g.leftMargin
            advanceHeight = g.width
        
            sourceHeight = False
            sourceWidth = False
            if g.box:
                sourceHeight = g.box[3] - g.box[1]
                sourceWidth =  g.box[2] - g.box[0]
        
            # draw rotating box
            sbPen = g.getPen()
            sbPen.moveTo((0, g.getParent().info.descender))
            sbPen.lineTo((0, g.getParent().info.ascender))
            sbPen.lineTo((g.width, g.getParent().info.ascender))
            sbPen.lineTo((g.width, g.getParent().info.descender))
            sbPen.closePath()
    
            # rotate
            halfWidth = g.width / 2
            halfHeight = ( g.getParent().info.ascender - g.getParent().info.descender ) / 2 + g.getParent().info.descender
            g.rotate(90, (halfWidth, halfHeight))
    

            g.rightMargin = g.leftMargin
        
            #remove rotating box
            if len(g.contours) >= 1:
                print g.name, 'removing contour'
                g.removeContour(g[len(g.contours)-1])
        
