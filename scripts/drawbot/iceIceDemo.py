# coding = utf-8

# Must have BungeeLayers-Ice installed!

layers = [
    # ('layerName'), (fill r, g, b), (stroke r, g, b) ),
    ('BungeeLayers-Shade', (50/255, 50/255, 103/255), None ),
    ('BungeeLayers-Regular', (239/255, 64/255, 54/255), None ), 
    ('BungeeLayers-Inline', (247/255, 173/255, 173/255), None ),
    ('BungeeLayersBeta-Ice', (240/255, 240/255, 240/255),  (50/255, 50/255, 103/255)),
    ]

myText = 'ABCDEFG\nHIJKLM\nNOPQRST\nUVWXYZ'

size(11*72, 8.5*72)

# set the font size
mySize = 106
fontSize(mySize)
lineHeight(mySize)
tracking(100/1000*mySize)

# draw a background

linearGradient(
    (width()/2, 0),                         # startPoint
    (width()/2, height()),                         # endPoint
    [(.85, .85, .85), (.7, .7, .7)],  # colors
    [0, 1]                          # locations
    )

rect(0, 0, width(), height())

translate(50, 50)


# now loop through each layer in the layer list
for layer in layers:
    save()
    # split the tuple and set the font
    layerName, layerColor, strokeColor = layer
    font(layerName)
    if strokeColor:
        r, g, b = strokeColor
        stroke(r, g, b)
        strokeWidth(mySize / 100)
    # split the RGB value, and set the fill
    r, g, b = layerColor
    fill(r, g, b)
    # draw the text
    textBox(myText, (0, 0, 700, 500), align='center')
    restore()
translate(0, -mySize)
print 'done'