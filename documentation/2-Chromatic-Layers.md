# Using chromatic layers

## In design apps

No design apps have native support for chromatic layers.

1. In one text box, set a line of matching text for each layer. Using the *Bungee Layers* font, style each line, starting with the backmost layer (Shade) and ending with the frontmost (Inline).

<img src="images/design-layers-1.png" alt="Step 1" width="650" />

2. Add colors to each line.

<img src="images/design-layers-2.png" alt="Step 2" width="650" />

3. When you are finished, select all of the text, and set the leading/linespacing to 0.

<img src="images/design-layers-3.png" alt="Step 3" width="650" />

4. To edit the text, do a find and replace, or increase the leading.

Instead of zeroing out the leading, you can also set each layer in a separate text block, but it takes additional work to manage their alignment and arrangement in the z axis.

## On the web

Bungee.js is a bit of javascript that will duplicate text in overlaid <div>s, giving the appearance of layered text without cluttering your markup.

	<script type="text/javascript" src="bungee.js">
	<div id="bungee">Layered text!</div>

Warning: This solution requires loading multiple fonts, which will increase bandwidth usage and download times. 

## As an image

When only single letters or small bits of text are required, use a SVG with alternate text specified.

	<svg src="images/layeredText.svg" alt="Layered text" />

## Color font formats

The *Bungee Color* family contains experimental fonts in the various color font formats out there, including SVG (Adobe/Mozilla), COLR/CPAL (Microsoft) and sbix (Apple).

These fonts were built with Jens Kutilek’s <a href="https://github.com/fontfont/RoboChrome">RoboChrome</a>.
