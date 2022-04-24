# Generate OTF files from UFO directories using ufo2ft

from defcon import Font
from ufo2ft import compileOTF
import itertools

ufo_files = ["../sources/1-drawing/Bungee-Regular.ufo",
             "../sources/1-drawing/Bungee_Rotated-Regular.ufo",
             "../sources/2-build/Bungee_Basic/Bungee-Hairline.ufo",
             "../sources/2-build/Bungee_Basic/Bungee-Inline.ufo",
             "../sources/2-build/Bungee_Basic/Bungee-Outline.ufo",
             "../sources/2-build/Bungee_Basic/Bungee-Shade.ufo",
             "../sources/2-build/Bungee_Color/Bungee_Color-Regular.ufo",
             "../sources/2-build/Bungee_Layers/Bungee_Layers-Inline.ufo",
             "../sources/2-build/Bungee_Layers/Bungee_Layers-Outline.ufo",
             "../sources/2-build/Bungee_Layers/Bungee_Layers-Regular.ufo",
             "../sources/2-build/Bungee_Layers/Bungee_Layers-Shade.ufo",
             "../sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Inline.ufo",
             "../sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Outline.ufo",
             "../sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Regular.ufo",
             "../sources/2-build/Bungee_Layers_Rotated/Bungee_Layers_Rotated-Shade.ufo"]

otf_files = ["../fonts/Bungee_Desktop/Bungee/Bungee-Regular.otf",
             "../fonts/Bungee_Desktop/BungeeLayersRotated/BungeeLayersRotated-Regular.otf",
             "../fonts/Bungee_Desktop/Bungee/Bungee-Hairline.otf",
             "../fonts/Bungee_Desktop/Bungee/Bungee-Inline.otf",
             "../fonts/Bungee_Desktop/Bungee/Bungee-Outline.otf",
             "../fonts/Bungee_Desktop/Bungee/Bungee-Shade.otf",
             "../fonts/Bungee_Color/Bungee_Color-Regular.otf",
             "../fonts/Bungee_Desktop/BungeeLayers/Bungee_Layers-Inline.otf",
             "../fonts/Bungee_Desktop/BungeeLayers/Bungee_Layers-Outline.otf",
             "../fonts/Bungee_Desktop/BungeeLayers/Bungee_Layers-Regular.otf",
             "../fonts/Bungee_Desktop/BungeeLayers/Bungee_Layers-Shade.otf",
             "../fonts/Bungee_Desktop/BungeeLayersRotated/Bungee_Layers_Rotated-Inline.otf",
             "../fonts/Bungee_Desktop/BungeeLayersRotated/Bungee_Layers_Rotated-Outline.otf",
             "../fonts/Bungee_Desktop/BungeeLayersRotated/Bungee_Layers_Rotated-Regular.otf",
             "../fonts/Bungee_Desktop/BungeeLayersRotated/Bungee_Layers_Rotated-Shade.otf"]

for (ufo_name, otf_name) in zip(ufo_files, otf_files): 
  ufo = Font(ufo_name)
  otf = compileOTF(ufo)
  otf.save(otf_name)
