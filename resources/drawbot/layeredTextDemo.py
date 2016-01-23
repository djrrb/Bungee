# coding = utf-8

#####################################
# BUNGEE BASIC TYPESETTER!
# -----------------------------------
# A quick and dirty script that renders chromatic text set in the
# Bungee font.
#
# https://github.com/djrrb/Bungee
#
# For a more complex version, see bungeeTypesetter.py.
#
# Run this in DrawBot 3+ (http://www.drawbot.com). 
# The BungeeLayers font family must be installed on your system.
#####################################

# define our variables

# set the text to be written
myText = 'Hello World!'

# define the layers as a list of tuples
# make sure these are in drawing order, from back to front
# the first item in the tuple is the layer name
# the second is a tuple of the RGB value of the layer color
layers = [
    # ('layerName'), (red, green, blue) ),
    ('Shade', (187/255, 230/255, 235/255) ),
    ('Outline', (33/255, 139/255, 149/255) ),
    ('Regular', (111/255, 200/255, 209/255) ), 
    ('Inline', (33/255, 139/255, 149/255) )
    ]

# set the document size
size(2320, 460)

# draw a background
fill(.87, .93, .94)
rect(0, 0, width(), height())

# translate the canvas to create a bottom and left margin
translate(150, 150)

# set the font size
fontSize(250)

# activate some of Bungee’s alternate forms, because why not!?
openTypeFeatures(ss02=True)

# now loop through each layer in the layer list
for layer in layers:
    print layer
    # split the tuple and set the font
    layerName, layerColor = layer
    font('BungeeLayers-%s' % layerName)
    # split the RGB value, and set the fill
    r, g, b = layerColor
    fill(r, g, b)
    # draw the text
    text(myText, (0, 0))
print 'done'