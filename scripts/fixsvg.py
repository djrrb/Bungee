#! /usr/bin/env python

from __future__ import print_function, division, absolute_import
from fontTools.misc.py23 import *
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
import xml.etree.ElementTree as ET
import sys

if len(sys.argv) != 3:
  print("usage: fixsvg.py fontfile-in.ttf fontfile-out.ttf")
  sys.exit(1)
sourceFont = sys.argv[1]
destinationFont = sys.argv[2]
font = TTFont(sourceFont)

ET.register_namespace("","http://www.w3.org/2000/svg")

# Optimise and fix SVG:
# - Get rid of XML declaration and <!DOCTYPE> stuff
# - Remove transform on SVG element
# - Inject <g> with a transform
for svg in font['SVG '].docList:
  try:
    svgDocument = ET.fromstring(svg[0])
  except:
    print("Broken SVG: " + svg[0])
    continue

  # Strip transform from <svg>, put on <g> instead
  if 'transform' in svgDocument.keys():
    del svgDocument.attrib['transform']

    # Create a new group tag to apply the transform to
    transformWrapper = ET.Element('g', {'transform': 'scale(1,-1)'})
    # Copy all SVG root children to the new group
    for child in svgDocument:
        transformWrapper.append(child)

    # Copy all attributes
    svgAttributes = svgDocument.items()
    svgDocument.clear()
    for name, value in svgAttributes:
        svgDocument.set(name, value)

    # Append the new group.
    svgDocument.append(transformWrapper)

  # Stick new SVG document back in font
  svg[0] = ET.tostring(svgDocument)

font.save(destinationFont)