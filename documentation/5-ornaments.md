# Ornaments

Bungee comes with a large set of arrows, pointing fists, and background shapes that are inspired by the shapes and decorations on old commercial signs.

Unicode values are assigned to ornaments when they are available; otherwise, codepoints in the Private Use Area area are used. In design apps, ornaments can be easily accessed via the Glyphs palette. See the (HTML demonstrations)[/examples] for examples of them in use.

Note that not all ornaments are available in Bungee’s Inline and Shade layers.

## Arrows and Indexes

Bungee contains a variety of straight and bent arrows in all directions, as well as four styles of pointing hands (two solid, two outlined).

<img src="images/design-ornaments-arrows.png" alt="Arrows and indexes." width="400" />

## Banners

To create continuous banners of any size, use Bungee’s various beginning and ending banner elements, connected by as many Full Blocks (█, U+2588) as you need.

<img src="images/design-ornaments-banners.png" alt="Banners." width="650" />

For example, here is a directional sign out of a half circle, two full blocks, and an arrowhead:

<img src="images/design-ornaments-layer.png" alt="Ornaments as layers." width="650" />

If you center-align the entire text block, you will not have to worry as much about making the layers line up. You can use horizontal scaling, tracking, or CSS letter-spacing to make minor adjustments to the length of the banner.

<img src="images/design-ornaments-scale.png" alt="Horizontal scaling in Illustrator." width="600" />

## Blocks

Bungee’s block shapes are designed to encircle a single letter. These blocks are wider and taller than the letters, occupying exactly 1.28× the height and width of the em. 

In order to use blockformat the letter layers to space correctly with the block shapes.

<img src="images/design-ornaments-block-2.png" alt="Block shapes." width="650" />

Use either OpenType **Stylistic Set 11** (Horizontal block spacing) or OpenType **Stylistic Set 12** (Vertical block spacing) to respace all characters so they are centered on the block width.

<img src="images/design-ornaments-blocks.2.png" alt="Block shapes." width="650" />

When OpenType features are not available, you can add 280 units of tracking to the alphabetical layers to make them align with the default spacing of the block shapes.

<img src="images/design-ornaments-blocks.png" alt="Using block shapes." width="650" />

If you wish to have more space around the letterforms, simply set that layer at a smaller font size than the blocks, add tracking, and reposition it accordingly. For example, centering and scaling the font 90% will involve 142 units of tracking and a 36-unit vertical shift.


* Previous: [Stylistic alternates](4-stylistic-alternates.md)
* Next: [Editing Bungee](6-editing-bungee.md)
