# Building Bungee Layouts on the fly with Javascript

Use bungee.js to create a completely styled Bungee layout with a single
element. Various classes on the element determine the appearance.

## Example:

```
<div class="bungee horizontal regular-efbb43 inline-eae2b1 outline-3e0e00 shade-c9060e background-333333 sign-111111 block-square alt-e alt-rounded" style="font-size: 120px">LAUNDROMAT</div>
```

## Required: 
 * "bungee" — this class determines which elements get this magic applied.

## Orientation:
 * "horizontal" or "vertical" — default is horizontal

## Layers: 
 * "layer[-color[-opacity]]"
 * layer: background, sign, shade, outline, regular, inline (from "bottom" to "top")
 * color: any valid HTML color, minus the pound sign. Examples: F00, FF0000, red
 * opacity: number from 0 to 100, specifying % opacity. Default 100% opaque.

## Block shapes:
 * "block-xxx" where xxx is one of the values in [blockChars] below

## Banner mode:
 * "begin-xxx" where xxx is one of the values in [beginChars] below
 * "end-xxx" where xxx is one of the values in [endChars] below

## Alternate characters:
 * "alt-xxx" where xxx is one of the values in [stylisticAlternates] below