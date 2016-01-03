# coding = utf-8

#####################################
# BUNGEE BASIC TYPESETTER!
# -----------------------------------
# A quick and dirty script that renders vertical text set in the
# Bungee font.
#
# https://github.com/djrrb/Bungee
#
# For a more complex version, see bungeeTypesetter.py.
#
# Run this in DrawBot 3+ (http://www.drawbot.com). 
# The Bungee font family must be installed on your system.
#####################################

# define our variables

# set the text to be written
myText = 'Restaurant'

# set the document size
size(390, 2350)

openTypeFeatures(ss01=True)
# rotate the canvas 90° CCW
rotate(-90)
# translate the text box the height of the document
# this way, we begin in the upper-left corner rather than
# the lower left.
translate(-height(), 0)

# add a margin
translate(100, 100)

# set the font and font size
font('BungeeLayersRotated-Regular', 250)

# set the text
text(myText, (0, 0))

# draw an inline layer for fun!
fill(1)
font('BungeeLayersRotated-Inline')
text(myText, (0, 0))

print 'done'