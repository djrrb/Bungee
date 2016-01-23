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

    'palette1':
        {
            'inline': 'f6620f',
            'regular': 'DA1426',
            'outline': 'f6620f', #ff9494
            'shade': '081B1E',
            'sign': '102A32',
            'background': '153640'
        },

    'palette2':
        {
            'inline': '92C9D2',
            'regular': '26839E',
            'outline': '235C6B',
            'shade': 'E6E6E6',
            'shadeTwo': 'EFEFEF',
            'background': 'FFFFFF'
        },
    'palette3':
        {
            'inline': 'FD8C6D',
            'regular': 'FF1A28',
            'outline': 'B91600',
            'shade': 'ebcc30',
            'sign': 'FFD433',
            'background': 'FBEB7D'
        },
        
        
    'palette4':
        {
            'inline': 'FFCCCC',
            'regular': 'EE0000',
            'outline': 'FFFFFF',
            'shade': 'EFEFEF',
            'sign': 'FFFFFF',
            'background': 'FFFFFF'
        },

    'palette5':
        {
            'inline': 'F6EBCB',
            'regular': 'CABB6B',
            'outline': '823722',
            'shade': '57201e',
            'sign': '691E14',
            'background': '330000'
        },
        
    }

layerOrder = ['inline', 'regular', 'outline', 'shadeTwo', 'shade', 'sign', 'background']

textLayers = layerOrder[:5]
textLayers.reverse()

default = 'palette1'


varList = []
for layer in layerOrder:
    varList.append({
         'ui': 'ColorWell', 
         'name': 'temp_'+layer, 
         'args': 
             dict(
                 color=makeColor(palettes[default].get(layer))
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
names = names[:4] + ['__dynamic__'] + names[4:]


dimension = 300*3+50*4 # three columns, four margins
size(dimension, dimension)

# image background
fill(.5)
rect(0, 0, width(), height()) 

block = unichr(11035)

save()

translate(50, 50)

for i, paletteName in enumerate(names):
    sample = 'HHH'
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
    
    if (i+1) % 3 == 0:
        translate(-700, 350)
    else:
        translate(350, 0)

restore()
