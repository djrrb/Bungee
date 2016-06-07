# Building Bungee Layouts on the fly with Javascript

Use bungee.js to create a completely styled Bungee layout with a single
element. Various classes on the element determine the appearance.

## Example:

```
<div class="bungee horizontal regular-efbb43 inline-eae2b1 outline-3e0e00 shade-c9060e background-333333 sign-111111 block-square alt-e alt-rounded" style="font-size: 120px">LAUNDROMAT</div>
```

## Required: 
 * `bungee` — this class determines which elements get this magic applied.

## Orientation:
 * `horizontal` or `vertical` — default is horizontal

## Layers: 
 * `layer[-color[-opacity]]`
 * layer: background, sign, shade, outline, regular, inline (from "bottom" to "top")
 * color: any valid HTML color, minus the pound sign. Examples: F00, FF0000, red
 * opacity: number from 0 to 100, specifying % opacity. Default 100% opaque.

## Block shapes:
 * `block-xxx` where xxx is one of the values in [blockChars] below

### Accepted values

 - square (0x2B1B)
 - circle (0x2B24)
 - shield (0xE15D)
 - box-rounded (0xE15E)
 - slant-left (0xE160)
 - slant-right (0xE15F)
 - chevron-left (0xE184)
 - chevron-right (0xE181)
 - chevron-up (0xE182)
 - chevron-down (0xE183)


## Banner mode:
 * `begin-xxx` where xxx is one of the values in [beginChars] below
 * `end-xxx` where xxx is one of the values in [endChars] below

### Accepted values

 - circle (0x25D6, 0x25D7)
 - deco-big (0xE165, 0xE166)
 - deco (0xE169, 0xE16A)
 - crown (0xE16D, 0xE16E)
 - square (0xE171, 0xE172)
 - rounded (0xE175, 0xE176)
 - swallowtail (0xE185, 0xE186)
 - arrow (0xE15A, 0x27A1)
 

## Alternate characters:
 * `alt-xxx` where xxx is one of the values in [stylisticAlternates] below
 
 ### Accepted Values
 - rounded (ss02)
 - round (ss02)
 - e (ss03)
 - i (ss04)
 - l (ss05)
 - amp (ss06)
 - ampersand (ss06)
 - quote (ss07) 
 - apostrophe (ss07)