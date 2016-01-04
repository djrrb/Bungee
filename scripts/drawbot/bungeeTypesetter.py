# coding = utf-8

#####################################
# BUNGEE INTERACTIVE TYPESETTER!
# -----------------------------------
# A script that showcases some of the chromatic and 
# vertical typesetting features of the Bungee font.
#
# https://github.com/djrrb/Bungee
#
# Run this in DrawBot 3+ (http://www.drawbot.com). 
# The BungeeLayers and BungeeLayersRotated font families
# must be installed on your system.
#####################################

from AppKit import NSColor
if __name__ == "__main__":

    # define a color palette
    palette1 = [
        NSColor.colorWithCalibratedRed_green_blue_alpha_(250/255, 207/255, 207/255, 1), # 0, inline
        NSColor.colorWithCalibratedRed_green_blue_alpha_(238/255, 58/255, 55/255, 1),   # 1, regular 
        NSColor.colorWithCalibratedRed_green_blue_alpha_(197/255, 26/255, 40/255, 1), # 2, outline
        NSColor.colorWithCalibratedRed_green_blue_alpha_(159/255, 28/255, 32/255, 1), # 3, shade
        NSColor.colorWithCalibratedRed_green_blue_alpha_(70/255, 20/255, 20/255, 1), # 4, background
        NSColor.colorWithCalibratedRed_green_blue_alpha_(135/255, 20/255, 20/255, 1) # 5, sign
    ]
    palette = palette1

    # unicode or private use area values for banners
    bannerBegin = [9686, 57690, 57701, 57705, 57709, 57717, 57725, 57733, 57713]
    bannerEnd = [9687, 10145, 57702, 57706, 57710, 57718, 57726, 57734, 57714]
    blockShapes = [11035, 11044, 57693, 57694, 57695, 57696, 57729, 57730, 57731, 57732]

    # set the tracking (we could have an interactive slider for this, but for now 
    # we'll hard code it since it's problematic)
    Tracking = 0

    # cache the global variables
    globalVars = globals()

    # Use the DrawBot Variable() funtion to create a simple vanilla interface.
    
    Variable([
    # Is the text horizontal or vertical.
    dict(
        name='Vertical', 
        ui='CheckBox', 
        args=dict(
            value=False
            )
        ),
    # Text to type
    dict(
        name='myText', 
        ui='EditText', 
        args=dict(
            text='Bungee'
            )
        ),
    # Layers
    dict(
        name='Inline Layer', 
        ui='CheckBox', 
        args=dict(
            value=True
            )
        ),
    dict(
        name='Regular Layer', 
        ui='CheckBox', 
        args=dict(
            value=True
            )
        ),
    dict(
        name='Outline Layer', 
        ui='CheckBox', 
        args=dict(
            value=True
            )
        ),
    dict(
        name='Shade Layer', 
        ui='CheckBox', 
        args=dict(
            value=True
            )
        ),
    # Ornament settings
    dict(
        name='Banner Begin', 
        ui='Slider', 
        args=dict(
            minValue=0,
            value=0,
            maxValue=len(bannerBegin),
            tickMarkCount=len(bannerBegin)+1,
            stopOnTickMarks=True
            )
        ),
    dict(
        name='Banner End', 
        ui='Slider', 
        args=dict(
            minValue=0,
            value=0,
            maxValue=len(bannerEnd),
            tickMarkCount=len(bannerEnd)+1, 
            stopOnTickMarks=True
            )
        ),
    dict(
        name='Block Shapes', 
        ui='Slider', 
        args=dict(
            minValue=0,
            value=0,
            maxValue=len(blockShapes),
            tickMarkCount=len(blockShapes)+1, 
            stopOnTickMarks=True
            )
        ),
    # Colors
    dict(
        name='Inline Color', 
        ui='ColorWell', 
        args=dict(color=palette[0])
        ),
    dict(
        name='Regular Color', 
        ui='ColorWell', 
        args=dict(color=palette[1])
        ),
    dict(
        name='Outline Color', 
        ui='ColorWell', 
        args=dict(color=palette[2])
        ),
    dict(
        name='Shade Color', 
        ui='ColorWell', 
        args=dict(color=palette[3])
        ),
    dict(
        name='Sign Color', 
        ui='ColorWell', 
        args=dict(color=palette[5])
        ),
    dict(
        name='Background', 
        ui='ColorWell', 
        args=dict(color=palette[4])
        ),
        
    # tracking    
    # dict(
    #     name='Tracking', 
    #     ui='Slider', 
    #     args=dict(
    #         minValue=-100,
    #         maxValue=500,
    #         value=0
    #         )
    #     ),
    
    # Alternates
    # dict(
    #     name='Vertical Forms', 
    #     ui='CheckBox', 
    #     args=dict(
    #         value=False
    #         )
    #     ),
    dict(
        name='Round Forms', 
        ui='CheckBox', 
        args=dict(
            value=False
            )
        ),
    dict(
        name='Round E', 
        ui='CheckBox', 
        args=dict(
            value=False
            )
        ),
    dict(
        name='Serifless I', 
        ui='CheckBox', 
        args=dict(
            value=False
            )
        ),
    dict(
        name='Serifless L', 
        ui='CheckBox', 
        args=dict(
            value=False
            )
        ),        
        
    ], globalVars)

    # figure out from the interface if we'll be drawing the text vertically
    isVertical = False
    if globalVars['Vertical']:
        isVertical = True

    # figure out if we'll be drawing banner or block shapes
    doBanner = False
    doBlockShapes = False
    if globalVars['Block Shapes'] and not globalVars['Banner Begin'] and not globalVars['Banner End']:
        doBlockShapes = True
    elif ( globalVars['Banner Begin'] or globalVars['Banner End'] ) and not globalVars['Block Shapes']:
        doBanner = True
    


    # define margins
    topMargin = 50
    bottomMargin = 50
    leftMargin = 50
    rightMargin = 50
    
    # whether inline should appear in banner and block shapes or not
    # again, could have a button for this, but don't want to make the
    # interface unnecessarily complicated
    drawInlineShapes = False
    
    # define orientation-specific values, such as page size and font family.
    
    # Since DrawBot doesn't have a native vertical typesetter
    # we will use the BungeeLayersRotated fonts and rotate the
    # text block 90° CCW. 
    
    # This means that the variable names 'height' and 'width'
    # are about to get confusing.
    
    if isVertical:
        size(300, 1000)
        boxWidth = height() - topMargin - bottomMargin
        boxHeight = width() - leftMargin - rightMargin
        fontFamily = 'BungeeLayersRotated'
    else:
        size(1000, 300)
        boxWidth = width() - leftMargin - rightMargin
        boxHeight = height() - topMargin - bottomMargin
        fontFamily = 'BungeeLayers'

    # draw the background
    fill(globalVars['Background'])
    rect(0, 0, width(), height())

    # before we draw the text, take some measurements
    # this will help decide how big the text should be
    # and how to position it
    
    # set font attributes
    openTypeFeatures(
        #ss01=globalVars['Vertical Forms'], 
        ss02=globalVars['Round Forms'], 
        ss03=globalVars['Round E'], 
        ss04=globalVars['Serifless I'], 
        ss05=globalVars['Serifless L']
        )
        
    if doBanner or doBlockShapes:
        openTypeFeatures(ss01=False)

    # set the font family, and size to 250, just for measurement purposes
    font(fontFamily+'-Regular', 250)
    lineHeight(250*.72)
    trackingValue = Tracking/1000*250
    tracking(trackingValue)
    
    # if there is no text, add a space so we don't hit an traceback
    if myText == '':
        myText = ' '
        print 'Enter some text!'
    
    # measure the text
    myTextWidth, myTextHeight = textSize(myText)
    myTextWidth -= trackingValue
    
    # measureText is the text we will measure for the total dimensions. For now, it is the same as myText.
    measureText = myText

    # if we have a banner, calculate the dimensions of the background
    if doBanner:
        # define banner middle, beginning, and ending defaults
        bgTextBase = u'█'
        bgTextBefore = unichr(57713)
        bgTextAfter = unichr(57714)
        # get customized beginnings and endings from the UI
        if globalVars['Banner Begin']:
            bgTextBefore = unichr(bannerBegin[int(globalVars['Banner Begin'])-1])
        if globalVars['Banner End']:
            bgTextAfter = unichr(bannerEnd[int(globalVars['Banner End'])-1])
        # guesstimate the number of full blocks (bgTextBase) that should appear between the banner ends
        blocks = int(round(myTextWidth/240))
        # put it all together and measure
        bgText = bgTextBefore + bgTextBase * blocks + bgTextAfter
        totalWidth, totalHeight = textSize(bgText)
        totalWidth -= trackingValue
        measureText = bgText
        
    # if we have block shapes, calculate the dimensions
    elif doBlockShapes:
        bgText = unichr(blockShapes[int(globalVars['Block Shapes'])-1]) * len(myText)
        totalWidth, totalHeight = textSize(bgText)
        measureText = bgText
        
    # otherwise, the total dimensions are the same as the dimensions of the text
    else:
        totalWidth, totalHeight = myTextWidth, myTextHeight
    
    # cross multiply to determine the font size that fills the width

    #    textWidth            boxWidth
    # ----------------  =  ---------------
    # textHeight (250)       fontSize!!
    
    mySize = ( 250 * boxWidth ) / totalWidth
    
    # set a ceiling for the font size so it does not exceed the image height
    if mySize > boxHeight:
        mySize = boxHeight
    
    # set the font size and remeasure the text
    fontSize(mySize)
    trackingValue = Tracking/1000*mySize
    tracking(trackingValue)
    lineHeight(mySize*.72)
    
    # recalculate the text dimensions
    if mySize != 250:
        totalWidth, totalHeight = textSize(measureText)
        totalWidth -= trackingValue
        myTextWidth, myTextHeight = textSize(myText)
        myTextWidth -= trackingValue

    # now we figure out how to position the text
    # the offset is equal to half the difference of the box's width and the total width
    # perform the offset, and if the text is vertical, rotate it 90° CCW
    xoffset = (boxWidth-totalWidth) / 2
    yoffset = (boxHeight-totalHeight) / 2
    if isVertical:
        translate(leftMargin+yoffset, bottomMargin+totalWidth+xoffset)
        save()
        rotate(-90)
    else:
        translate(leftMargin+xoffset, bottomMargin+yoffset)
        save()
        
    # if there is a banner or block shape, draw that first
    if doBanner or doBlockShapes:
        save()
        if globalVars['Outline Layer']:
            font(fontFamily+'-Outline')
            fill(globalVars['Outline Color'])
            text(bgText, (0, 0))
        if globalVars['Regular Layer'] or True:
            font(fontFamily+'-Regular')
            fill(globalVars['Sign Color'])
            text(bgText, (0, 0))
        if drawInlineShapes:
            if globalVars['Inline Layer']:
                font(fontFamily+'-Inline')
                fill(globalVars['Inline Color'])
                text(bgText, (0, 0))
        restore()
        
        # the block shapes are especially finnicky.
        # if we are dealing with them, make some modifications to the text that follows:
        # - turn vertical alternates are turned ON
        # - scale the text down by 90%
        # - add tracking (usually 280, but in this case 420 because of the 90% scale)
        # - recalculate offsets based on the new text size
        if doBlockShapes:
            scaleValue = .9
            addTracking = 420
            originalMyTextHeight = myTextHeight
            mySize *= scaleValue
            fontSize(mySize)
            lineHeight(mySize)
            openTypeFeatures(ss01=True)
            trackingValue = trackingValue + addTracking/1000*mySize
            tracking(trackingValue)
            myTextWidth, myTextHeight = textSize(myText)
            myTextWidth -= trackingValue
            translate(0, (myTextHeight - originalMyTextHeight)/4)
            myTextWidth -= trackingValue/1000*mySize

    # now translate to the position where we can draw the text
    translate(-(myTextWidth-totalWidth)/2, 0)
    
    # if the shade layer is active, offset the text 1/3 of the size of the shade to optically center it
    shadeOffset = 0
    if globalVars['Shade Layer']:
        shadeOffset = ( mySize * .12 ) / 3
    if globalVars['Vertical']:
        translate(-shadeOffset, shadeOffset)
    else:
        translate(shadeOffset, shadeOffset)
    
    # Finally, it is time to draw the text!
    # Start with the back layer and move forward.
    if globalVars['Shade Layer']:
        font(fontFamily+'-Shade')
        fill(globalVars['Shade Color'])
        text(myText, (0, 0))
    if globalVars['Outline Layer']:
        font(fontFamily+'-Outline')
        fill(globalVars['Outline Color'])
        text(myText, (0, 0))
    if globalVars['Regular Layer']:
        font(fontFamily+'-Regular')
        fill(globalVars['Regular Color'])
        text(myText, (0, 0))
    if globalVars['Inline Layer']:
        font(fontFamily+'-Inline')
        fill(globalVars['Inline Color'])
        text(myText, (0, 0))
    restore()