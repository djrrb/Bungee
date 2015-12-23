
# Using vertical text

Bungee’s vertical features are implemented via three OpenType features:

* *vert*: Vertical Forms.

Replace default horizontal forms with glyphs drawn for vertical setting. These glyphs are monowidth in appearance, and their widths are adjusted to foster better vertical alignment. The hyphen and other basic punctuation are rotated 90°.

* *vpal*: Vertical Positioning and Layout.

Reset the vertical sidebearings and advance heights for the glyphs. This feature enables Bungee to have proportional vertical spacing, with shorter glyphs occupying less vertical space than taller ones.

* *vkrn*: Vertical Kerning.

Adjust the vertical spacing of individual glyph pairs so that they are more evenly spaced.

## In apps with the vertical type tool

Several professional design applications have separate vertical text tools, which will implement all of the necessary OpenType features and provide a nice interface for setting vertical text.

<img src="images/design-vertical-text.png" alt="Vertical Type tool in Adobe Illustrator" width="650" />

In most apps, the Character palette provides options for vertical tracking and kerning.

Desktop apps that natively support vertical text include:

* Adobe Photoshop
* Adobe Illustrator
* Apple TextEdit

## In apps with rotated text 

In apps that do not have native vertical text tools, the *Bungee Layers Rotated* family allows you to simulate vertical type. 

These fonts have Bungee’s vertical forms, spacing, and kerning baked in to the default forms, and all characters are rotated 90° counterclockwise. 

Set the text. 

<img src="images/design-vertical-1.png" alt="Rotated vertical text, step 1" width="650" />

Change the font family to *Bungee Layers Rotated*.

<img src="images/design-vertical-2.png" alt="Rotated vertical text, step 2" width="650" />

Finally, rotate the text block 90° counterclockwise. 

<img src="images/design-vertical-3.png" alt="Rotated vertical text, step 3" width="650" />

Voilà! Pseudo-vertical text.

Apps that do not support vertical text include:

* Google Docs
* Microsoft Word
* Apple Pages
* Adobe InDesign

## On the web with writing-mode

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
	
## On the web with rotated text
	
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


* Previous: [Chromatic layers](2-chromatic-layers.md)
* Next: [Stylistic alternates](4-stylistic-alternates.md)
