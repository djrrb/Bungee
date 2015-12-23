# Bungee design guide

This document demonstrates how to use some of Bungee's more interesting features, such as its [chromatic layers](#using-chromatic-layers---), [vertical forms](#using-vertical-text------), [stylistic alternates](#stylistic-alternates---------------------), and [ornaments](#ornaments------------).


## Family structure

Bungee contains several different font sets that allow access to the chromatic layers and vertical forms. 

The basic *Bungee* family includes Regular and Hairline weights, as well as three composite layerings: Inline, Outline, and Shade.

*Bungee Layers* contains each layer in a separate font, which all share the same metrics. These fonts can be used in combination to create chromatic text by using layered textboxes in a website or advanced design app.

*Bungee Layers Rotated* implements Bungee’s vertical forms by default, with all characters rotated 90° counterclockwise. These fonts can be set in a textbox rotated 90° clockwise to simulate vertical type, and have a limited character set.

*Bungee Color* contains experiments with the various color font formats out there, including SVG, COLR/CPAL and sbix. None of these formats are widely supported (yet!), so your milage may vary. These fonts are built with Jens Kutilek’s <a href="https://github.com/fontfont/RoboChrome">RoboChrome</a>.


## Using chromatic layers

### In design apps

No design apps have native support for chromatic layers.

1. In one text box, set a line of matching text for each layer. Using the *Bungee Layers* font, style each line, starting with the backmost layer (Shade) and ending with the frontmost (Inline).

<img src="images/design-layers-1.png" alt="Step 1" width="650" />

2. Add colors to each line.

<img src="images/design-layers-2.png" alt="Step 2" width="650" />

3. When you are finished, select all of the text, and set the leading/linespacing to 0.

<img src="images/design-layers-3.png" alt="Step 3" width="650" />

4. To edit the text, do a find and replace, or increase the leading.

Instead of zeroing out the leading, you can also set each layer in a separate text block, but it takes additional work to manage their alignment and arrangement in the z axis.

### On the web

Bungee.js is a bit of javascript that will duplicate text in overlaid <div>s, giving the appearance of layered text without cluttering your markup.

	<script type="text/javascript" src="bungee.js">
	<div id="bungee">Layered text!</div>

Warning: This solution requires loading multiple fonts, which will increase bandwidth usage and download times. 

### As an image

When only single letters or small bits of text are required, use a SVG with alternate text specified.

	<svg src="images/layeredText.svg" alt="Layered text" />

### Color font formats

The *Bungee Color* family contains experimental fonts in the various color font formats out there, including SVG (Adobe/Mozilla), COLR/CPAL (Microsoft) and sbix (Apple).

These fonts were built with Jens Kutilek’s <a href="https://github.com/fontfont/RoboChrome">RoboChrome</a>.


## Using vertical text

Bungee’s vertical features are implemented via three OpenType features:

* *vert*: Vertical Forms.

Replace default horizontal forms with glyphs drawn for vertical setting. These glyphs are monowidth in appearance, and their widths are adjusted to foster better vertical alignment. The hyphen and other basic punctuation are rotated 90°.

* *vpal*: Vertical Positioning and Layout.

Reset the vertical sidebearings and advance heights for the glyphs. This feature enables Bungee to have proportional vertical spacing, with shorter glyphs occupying less vertical space than taller ones.

* *vkrn*: Vertical Kerning.

Adjust the vertical spacing of individual glyph pairs so that they are more evenly spaced.

### In apps with the vertical type tool

Several professional design applications have separate vertical text tools, which will implement all of the necessary OpenType features and provide a nice interface for setting vertical text.

<img src="images/design-vertical-text.png" alt="Vertical Type tool in Adobe Illustrator" width="650" />

In most apps, the Character palette provides options for vertical tracking and kerning.

Desktop apps that natively support vertical text include:

* Adobe Photoshop
* Adobe Illustrator
* Apple TextEdit

### In apps with rotated text 

In apps that do not have native vertical text tools, the *Bungee Layers Rotated* family allows you to simulate vertical type. 

These fonts have Bungee’s vertical forms, spacing, and kerning baked in to the default forms, and all characters are rotated 90° counterclockwise. 

1. Set the text. 

<img src="images/design-vertical-1.png" alt="Rotated vertical text, step 1" width="650" />

2. Change the font family to *Bungee Layers Rotated*.

<img src="images/design-vertical-2.png" alt="Rotated vertical text, step 2" width="650" />

3. Rotate the text block 90° counterclockwise. 

<img src="images/design-vertical-3.png" alt="Rotated vertical text, step 3" width="650" />

Voilà! Pseudo-vertical text.

Apps that do not support vertical text include:

* Google Docs
* Microsoft Word
* Apple Pages
* Adobe InDesign

### On the web with writing-mode

The proper way to implement vertical text is via the CSS **writing-mode** and **text-orientation** selector, as well as implementing. This will work in recent versions of IE, Firefox, and Chrome, but not in older browsers or Safari.

	<style type="text/css">
		.vertical {
			/* change writing mode to vertical */
			-ms-writing-mode: tb-rl;
			-webkit-writing-mode: vertical-rl;
			-moz-writing-mode: vertical-rl;
			-ms-writing-mode: vertical-rl;
			writing-mode: vertical-rl;
			/* use upright orientation */
			-webkit-text-orientation: upright;
			-moz-text-orientation: upright;
			-ms-text-orientation: upright;
			text-orientation: upright;
			/* implement spacing and kerning */
			-moz-font-feature-settings: "vkrn", "vpal";
			-webkit-font-feature-settings: "vkrn", "vpal";
			font-feature-settings: "vkrn", "vpal";
	</style>

	<div class="vertical">Bungee</div>
	
Learn more about vertical writing modes at http://generatedcontent.org/post/45384206019/writing-modes.
	
### On the web with rotated text
	
Alternatively, *Bungee Layers Rotated* fonts and a rotated div to simulate the effect. This will require you
to reposition the div using margins or absolute positioning.

		.rotated {
			font-family: "BungeeLayersRotated";
			-webkit-transform: rotate(90deg);
			-moz-transform: rotate(90deg);
			-o-transform: rotate(90deg);
			-ms-transform: rotate(90deg);
			transform: rotate(90deg);
		}
		
		<div class="rotated">Bungee</div>


## Stylistic alternates

As a display font, Bungee is only intended for small bits of text, sometimes even single letters or words. Since an individual letter can play such a big part of a Bungee composition, Bungee comes with alternates that can help you fine-tune the look and feel of your text. 

Bungee’s stylistic alternates can be accessed using OpenType Stylistic Sets (ss01-ss20), or via the Glyphs palette in design apps.

* Stylistic Set 01: Round Forms.

Replace diagonal forms of A, M, N, W, X, and Y with deco-inspired alternates with round shapes and vertical sides. 

<img src="images/design-alternates-round-forms.png" alt="Round forms" height="200" />


Each of these letters can also be implemented separately using the following stylistic sets:
	
	* Stylistic Set 05: Round A.
	* Stylistic Set 06: Round M.
	* Stylistic Set 07: Round N.
	* Stylistic Set 08: Round W.
	* Stylistic Set 09: Round X.
	* Stylistic Set 10: Round Y.
	
* Stylistic Set 02: Serifless I.

Replace wide, serifed I with an unserifed alternate. This is a very narrow character that may result in less-than-ideal vertical setting.

<img src="images/design-alternates-i.png" alt="Serifless I" height="200" />

For all you Hawaiians out there, there’s also a special serifless II ligature!

* Stylistic Set 03: Round E.

Replace forms of E with an decorative alternate with a rounded left side.

<img src="images/design-alternates-e.png" alt="Round E" height="200" />
	
* Stylistic Set 04: Alternate Ampersand.

Replace the default ‘ET’ ampersand with an alternate that resembles a stylized ‘E’ with a vertical stroke.
	
<img src="images/design-alternates-ampersand.png" alt="Alternate ampersand" height="200" />
	
* Stylistic Set 12: Small Quotes.

Replace the curly apostrophe and matching left quote with smaller, less obtrusive versions.

<img src="images/design-alternates-apostrophe.png" alt="Small quotes" height="200" />

* Stylistic Set 18: John Downer Recommendations.

Signpainter John Downer recommends against vertical type that includes problematic characters like I, M, and W, which are unusually narrow or wide. This feature disables those characters.

<img src="images/design-alternates-downer.png" style="width: 3em" alt="Downer" width="200"/>

* Stylistic Set 20: Vertical forms.

Activate Bungee’s vertical forms (identical to the *vert* feature). These forms are better accessed through the vertical text features described above, but this stylistic set can be handy when such tools are not available, or when monowidth letters are required in a non-vertical setting.

<img src="images/design-alternates-vertical.png" alt="Vertical forms" height="200" />

### Minor opentype features

In addition to its stylistic alternates, Bungee also contains several OpenType Stylistic Sets for easy access to certain characters or alternate forms.

* Stylistic Set 11: Sequential IJ.
* Stylistic Set 13: Indexes (pointing hands).
* Stylistic Set 14: Alternate Indexes.
* Stylistic Set 15: Outlined Indexes.
* Stylistic Set 19: Primes.


## Ornaments

In addition to its arrows and pointing indexes, Bungee has a nice set of ornaments that you can use to assemble additional chromatic layers.

Some ornaments are designed to connect seamlessly to other ornaments, which you can use to create continuous banners. If you center-align the entire text block, you will not have to worry as much about making the layers line up.

For example, you can compose a directional sign out of a half circle, two square blocks, and an arrowhead.

<img src="images/design-ornaments-layer.png" alt="Ornaments as layers." width="650" />

In design apps, ornaments can be easily accessed via the Glyph palette.

<img src="images/design-ornaments-glyph-palette.png" alt="Glyph palette in Illustrator." width="600" />

You can use horizontal scaling and tracking/letter-spacing to make minor adjustments to the positions.

<img src="images/design-ornaments-scale.png" alt="Horizontal scaling in Illustrator." width="600" />

Other ornaments can be set independently to encircle a single letter. Use these shapes behind Bungee’s vertical forms (accessible via the glyph palette, under Stylistic Set 20), since they are all approximately the same width. 

<img src="images/design-ornaments-independent-2.png" alt="Independent ornaments." width="650" />

Add *280 units* to the alphabetical layers to make them line up with the independent ornaments.

<img src="images/design-ornaments-independent.png" alt="Using independent ornaments." width="650" />

Note that not all ornaments are available in Bungee’s Inline and Shade layers.
