import struct
from AppKit import NSColor

def makeColor(hexValue, a=1):
    if not hexValue:
        return None
    if hexValue[0] == '#':
        hexValue = hexValue[1:]
    r, g, b = struct.unpack('BBB',hexValue.decode('hex'))
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r/255, g/255, b/255, a)
    
def makeHex(c):
    r, g, b, a = c.getRed_green_blue_alpha_(None, None, None, None)
    rgb = r*255, g*255, b*255
    return '%02x%02x%02x' % rgb

palettes = {

    'palette01':
        {
            'inline': 'EE0000',
            'regular': 'FEFEFE',
            'outline': 'EE0000',
            'shade': 'EE0000',
            'sign': 'FEFEFE',
            'signOutline': 'EE0000',
            'background': 'FEFEFE'
        },
    'palette02':
        {
            'inline': '92C9D2',
            'regular': '26839E',
            'outline': '235C6B',
            'shade': 'E6E6E6',
            #'shadeTwo': 'EFEFEF',
            'background': 'FFFFFF'
        },
    'palette03':
        {
            'inline': 'f6620f',
            'regular': 'FF1A28',
            'outline': 'B91600',
            'shade': 'ebcc30',
            'sign': 'FFD433',
            'background': 'FBEB7D'
        },

    'palette04':
        {
            'inline': 'f6620f',
            'regular': 'DA1426',
            'outline': 'f6620f', #ff9494
            'shade': '081B1E',
            'sign': '102A32',
            'background': '153640'
        },

    'palette05':
        {
            'inline': 'F6EBCB',
            'regular': 'CABB6B',
            'outline': '823722',
            'shade': '3b1315',
            'sign': '541c17',
            'background': '330000'
        },
        
        
    'palette06':
        {
            'inline': 'F6EBCB',
            'regular': '26839E',
            'outline': '102A32', #?
            'shade': '144A56',
            'sign': '102A32',
            'background': '102A32'
        },
        
    'palette07':
        {
            'inline': 'F6EBCB',
            'regular': 'DB4226',
            'outline': 'F6EBCB',
            'shade': None,
            'sign': '762017',
            'signOutline': 'F6EBCB',
            'background': '1A0000'
        },


    'palette08':
        {
            'inline': 'EBDEC0',
            'regular': 'F7F4ED',
            'outline': None,
            'shade': None,
            'sign': '432D2C',
            'signOutline': 'EBDEC0',
            'background': '5B3939'
        },
        
     'palette10': # law offices
        {
            'inline': 'f0cb89',
            'regular': 'e9b955',
            'outline': None,
            'shade': '333300',
            'sign': None,
            'signOutline': None,
            'background': '484b35'
        },


     'palette11': #
        {
            'inline': 'ff5140',
            'regular': 'ffda99',
            'outline': 'ff5140',
            'shade': '211b1b',
            'sign': '26243a',
            'signOutline': None,
            'background': '26243a'
        },


     'palette12': #
        {
            'inline': 'dfeaec',
            'regular': 'd84f3a',
            'outline': 'c14e3c',
            'shade': '070510',
            #'shadeTwo': '660000'
            'sign': '0b3b3f',
            'signOutline': None,
            'background': '0b3b3f'
        },  
        
     'palette13': #
        {
            'inline': '936d1a',
            'regular': 'c7a850',
            'outline': '251b26',
            #'shade': '251b26',
            #'shadeTwo': '660000'
            'sign': '0b2f2b',
            'signOutline': None,
            'background': '0e403f'
        },   
          
     
     'palette14': #
        {
            'inline': 'eae2b1',
            'regular': 'efbb43',
            'outline': '3e0e00',
            'shade': 'c9060e',
            #'shadeTwo': '660000'
            'sign': '222222',
            'signOutline': None,
            'background': '333333'
        },
        

     'palette15': #
        {
            'inline': 'eaf9fc',
            'regular': '98adc2',
            'outline': 'b1c1d0',
            'shade': '4e667e',
            #'shadeTwo': '660000'
            'sign': '8499ae',
            'signOutline': None,
            'background': '98adc2'
        },
        
        
     'palette17': #
        {
            'inline': '5d1d2a',
            'regular': 'a42e47',
            #'outline': 'db584b',
            'shade': 'aa9347',
            #'shadeTwo': '660000'
            'sign': None,
            'signOutline': None,
            'background': 'c9af63'
        },
        
     'palette16': #
        {
            'inline': 'cccccc',
            'regular': 'e7e9db',
            #'outline': 'c31a03',
            'shade': '090400',
            #'shadeTwo': '660000'
            'sign': 'c31a03',
            'signOutline': None,
            'background': 'a02911'
        },
        
        
    
        
        
    }

{'outline': 'a6b8f0', 'shade': '6b3726', 'sign': '833d1e', 'regular': '084fc6', 'background': '44251a', 'inline': '0b25aa'}


layerOrder = ['inline', 'regular', 'outline', 'shadeTwo', 'shade', 'sign', 'background']

textLayers = layerOrder[:5]
textLayers.reverse()

default = {

            'inline': '666666',
            'regular': '999999',
            'outline': '888888',
            'shade': 'AAAAAA',
            'sign': 'BBBBBB',
            'background': 'BBBBBB'

    }

varList = []
for layer in layerOrder:
    varList.append({
         'ui': 'ColorWell', 
         'name': 'temp_'+layer, 
         'args': 
             dict(
                 color=makeColor(default.get(layer))
                 )
             })

temp = None
Variable(varList, globals() )

p={}

for layer in layerOrder:
    try:
        h = makeHex(globals()['temp_'+layer])
        p[layer] = h
    except:
        pass

print p

names = sorted(palettes.keys())
names = ['__dynamic__'] + names


cols = 4

rows = 4

dimension = 300*cols+50*(cols+1) # three columns, four margins
size(dimension, dimension*2)

# image background
fill(.5)
rect(0, 0, width(), height()) 

block = unichr(11035)

save()

translate(50, 50)



for i, paletteName in enumerate(names):
    sample = 'HRS'
    #import random
    #sample = random.choice(list('abcdefghijklmnopqrstuvwxyz'))
    
    # select palette by name or use special __dynamic__ palette
    if paletteName == '__dynamic__':
        palette = p
    else:
        palette = palettes[paletteName]

    fontSize(200)
    lineHeight(200)
    
    save()
    if palette.get('background'):
        fill(makeColor(palette['background']))
        rect(0, 0, 300, 300)
    
    c = BezierPath()
    c.moveTo((0, 0))
    c.lineTo((0, 300))
    c.lineTo((300, 300))
    c.lineTo((300, 0))
    c.closePath()
    clipPath(c)

    translate(21, 75)
    
    if palette.get('signOutline'):
        font('BungeeLayers-Outline')
        fill(makeColor(palette['signOutline']))
        text(block, (0, 0))

    if palette.get('sign'):
        font('BungeeLayers-Regular')
        fill(makeColor(palette['sign']))
        text(block, (0, 0))
        #tracking(28*2)
        #openTypeFeatures(ss01=True)
        #sample = 'HI'
    
    translate(-100, 0)
    
    for textLayer in textLayers:    
        if palette.get(textLayer):    
            font('BungeeLayers-%s' % textLayer[0].upper()+textLayer[1:])
            fill(makeColor(palette[textLayer]))
            text(sample, (0, 0))
    
    restore()
    
    if (i+1) % cols == 0:
        translate(-350*(cols-1), 350)
    else:
        translate(350, 0)

restore()
