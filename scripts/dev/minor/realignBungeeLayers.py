g = CurrentGlyph()
print g.box[0], g.box[3]
shade = g.getLayer('outline')
print shade.box[0], shade.box[3]

xoffset = g.box[0] - shade.box[0] - 10
yoffset = g.box[3] - shade.box[3] + 10
print xoffset, yoffset

for layername in g.getParent().layerOrder:
    if layername != 'foreground':
        layer = g.getLayer(layername)
        layer.move((xoffset, yoffset))
print 'done'