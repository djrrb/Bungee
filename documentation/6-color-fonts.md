# Bungee Color

Thanks in large part to the popularity of Emoji, several specifications for color fonts have emerged in the past few years. All three are widely supported. 

These fonts were generated with Jens Kutílek’s incredible tool [Robochrome](https://github.com/fontfont/RoboChrome), and mastered with the help of [Roel Nieskens](https://pixelambacht.nl).

## SVG ([Mozilla](https://hacks.mozilla.org/2014/10/svg-colors-in-opentype-fonts/))

This format simply embeds SVG images into the font. It works in recent versions of Firefox.

![Firefox with color](color-svg-firefox.png)

## COLR/CPAL ([Microsoft](https://www.microsoft.com/typography/otspec/colr.htm))

Microsoft’s format layers alternate glyphs on top of each other to create chromatic type. It creates two tables, one that defines how the alternates glyphs are layered, and one that defines color palettes.

## SBIX ([Apple](https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6sbix.html))

Apple’s format embeds PNG data into a special font table. It works in Mac OS X.

![Apple Font Book with color](color-sbix-mac.png)
