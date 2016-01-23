<?php
namespace CLC\Bungee;

# Create an SVG rendering of layered type set in Bungee
# DJR: http://djr.com/
# Code © 2015 Chris Lewis <info@chrislewis.codes>. All rights reserved.

define('DEBUG', isset($_GET['debug']));

if (!function_exists('uniord')) {
    # from http://stackoverflow.com/a/18499265
    function uniord($char) {
        return ltrim(bin2hex(mb_convert_encoding($char, "UTF-32BE")), "0");
    }
}

$styles = array(
    'shade' => '513620', 
    'outline' => 'b2c021', 
    'regular' => 'ffffff', 
    'inline' => '7e1414'
);

$layers = array();
foreach ($styles as $style => $color) {
    if (isset($_GET['layers'][$style])) {
        $layers[$style] = $_GET['layers'][$style];
    }
}

if (empty($layers)) {
    $layers = $styles;
}

$orientation = isset($_GET['orientation']) ? $_GET['orientation'] : 'horizontal';
$text = mb_strtoupper(isset($_GET['text']) && is_string($_GET['text']) && strlen($_GET['text']) ? $_GET['text'] : "Hello!");
$size = isset($_GET['size']) && is_numeric($_GET['size']) ? (int)$_GET['size'] : 144;
$ss = !empty($_GET['ss']) ? explode(',', $_GET['ss']) : array();

#stylesets should be sorted numerically, except ss01 last
$ss = array_unique($ss);
sort($ss);
$ss01 = array_search('ss01', $ss);

if ($ss01 !== false) {
    #ss01 always needs to be at the end
    unset($ss[$ss01]);

    #but it is applied by default in the vertical fonts
    if ($orientation !== 'vertical') {
        $ss[] = 'ss01';
    }
}

#calculate size
$padding = round($size*0.1 + 18);
$height = round($size + $padding*2);
//width will be determined by text length

#what characters do we actually need?
$subset = array();
for ($i=0, $l=mb_strlen($text); $i<$l; $i++) {
    $subset[uniord(mb_substr($text, $i, 1))] = true;
}
$subset = array_keys($subset);

#load up alternates and figure out character mappings
$allalts = json_decode(file_get_contents('bungee_gsub.json'), true);

#figure out character mappings
$myalts = array();
foreach ($subset as $orighex) {
    if ($orighex === "notdef") {
        continue;
    }

    $replacement = hexdec($orighex);
    foreach ($ss as $styleset) {
        if (isset($allalts[$styleset][$replacement])) {
            #update value and keep going
            $replacement = $allalts[$styleset][$replacement];
        }
    }
    $myalts[$orighex] = dechex($replacement);
}

#update subset to use alternates
$subset = array_fill_keys(array_values($myalts), true);

$kerns = array();

# Font definitions

$charwidths = array();
$em = 1000;
$baseline = 0;

ob_start();

print "<defs>";

foreach ($layers as $style => $color) {
    $font = file_get_contents("fonts/BungeeLayers" . ($orientation==='vertical' ? 'Rotated' : '') . "-" . ucfirst($style) . ".svg");
    preg_match_all('/<(font-face|glyph|missing-glyph|hkern)\b(.*?)>/u', $font, $matches, PREG_SET_ORDER);
    foreach ($matches as $m) {
        $tag = $m[1];

        preg_match_all('/(\S+)="(.*?)"/u', $m[2], $amatch, PREG_PATTERN_ORDER);
        $attr = array_combine($amatch[1], $amatch[2]);

        switch ($tag) {
            case 'font-face':
                if (isset($attr['units-per-em'])) {
                    $em = (int)$attr['units-per-em'];
                }
                if (isset($attr['descent'])) {
                    $baseline = -$attr['descent'];
                }
                break;
                
            case 'missing-glyph':
                if (!empty($attr['d'])) {
                    print "<path id='$style-notdef' d='{$attr['d']}' />";
                }
                $charwidths[$style]['notdef'] = (int)$attr['horiz-adv-x'];
                break;
            
            case 'glyph':
                if (!isset($attr['unicode'])) {
                    break;
                }

                $id = uniord(html_entity_decode($attr['unicode']));

                if (isset($subset[$id])) {
                    if (isset($attr['d'])) {
                        print "<path id='$style-$id' d='{$attr['d']}' />";
                    }
                    $charwidths[$style][$id] = (int)$attr['horiz-adv-x'];
                }
                break;
            
            case 'hkern': 
                $firsts = explode(',', $attr['u1']);
                $seconds = explode(',', $attr['u2']);
                $kern = -$attr['k'];
                foreach ($firsts as $u1) {
                    if ($u1 === '') {
                        $u1 = ',';
                    }
                    $u1 = html_entity_decode($u1);
                    $u1 = uniord($u1);
                    foreach ($seconds as $u2) {
                        if ($u2 === '') {
                            $u2 = ',';
                        }
                        $u2 = html_entity_decode($u2);
                        $u2 = uniord($u2);
                        if (isset($subset[$u1]) and isset($subset[$u2])) {
                            $kerns[$u1][$u2] = $kern;
                        }
                    }
                }
                break;
        }
    }
}

$scale = $size / $em;

print "</defs>";

$svgdefs = ob_get_clean();

ob_start();

print "<!-- Text: $text (" . mb_strlen($text) . " bytes) -->";

if ($orientation === 'vertical') {
    print "<g transform='rotate(90) translate(0,-$height)'>";
}

# Text layers output
$prev = null;
foreach ($layers as $style => $color) {
    $x = $padding;
    $y = $height-$padding-$baseline*$scale;
    for ($i=0,$l=mb_strlen($text); $i<$l; $i++) {
        $id = uniord(mb_substr($text, $i, 1));
        if (isset($myalts[$id])) {
            $id = $myalts[$id];
        }
        if (!isset($charwidths[$style][$id])) {
            $id = 'notdef';
        }
        if (isset($kerns[$prev][$id])) {
            $x += $kerns[$prev][$id]*$scale;
        }
        print "<use transform='translate($x $y) scale($scale -$scale)' xlink:href='#{$style}-$id' style='stroke:none;fill:#$color' />";
        $x += $charwidths[$style][$id]*$scale;
        $prev = $id;
    }
}

#now we have all the information we need to calculate the final dimensions
$width = round($x + $padding);

if ($orientation === 'vertical') {
    print "</g>";
    $temp = $width;
    $width = $height;
    $height = $temp;
}

$svgcontent = ob_get_clean();


ob_start();

print "<?xml version='1.0' encoding='utf-8' ?>";
print '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">';
print "<svg version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='$width' height='$height'>";

print $svgdefs; unset($svgdefs);

#border
#print "<rect x='0' y='0' width='$width' height='$height' stroke='black' fill='transparent'/>";

print $svgcontent; unset($svgcontent);

print "</svg>";

$output = ob_get_clean();

if (DEBUG) {
    header("Content-type: text/plain; charset=utf-8");
    $output = str_replace("><", ">\n<", $output);
} else {
    header("Content-type: image/svg+xml");
}

header("Content-length: " . strlen($output));
print $output;
exit(0);
