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

$backgroundlayers = array(
    'outline' => isset($layers['outline']) ? $layers['outline'] : $styles['outline'], 
    'regular' => isset($layers['inline']) ? $layers['inline'] : $styles['inline'],
);

$orientation = isset($_GET['orientation']) ? $_GET['orientation'] : 'horizontal';
$text = isset($_GET['text']) && is_string($_GET['text']) && strlen($_GET['text']) ? $_GET['text'] : "Hello!";
$size = isset($_GET['size']) && is_numeric($_GET['size']) ? (int)$_GET['size'] : 144;
$ss = !empty($_GET['ss']) ? explode(',', $_GET['ss']) : array();
$block = !empty($_GET['block']) ? dechex($_GET['block']) : false;
$begin = !empty($_GET['begin']) ? dechex($_GET['begin']) : false;
$end = !empty($_GET['end']) ? dechex($_GET['end']) : false;
$format = !empty($_GET['format']) ? $_GET['format'] : 'svg';

$textscale = 1.0;

#stylesets should be sorted numerically, except ss01 last
if ($block) {
    #block shapes always get ss01
    $ss[] = 'ss01';
    $textscale = 0.9;
    $begin = $end = false;
} else if ($begin or $end) {
    $textscale = 0.9;
    $block = false;
}

#cleanup on aisle ss
$ss = array_unique($ss);
sort($ss);
$ss01 = array_search('ss01', $ss);

if ($ss01 !== false) {
    #ss01 always needs to be at the end
    unset($ss[$ss01]);

    #ss01 not needed in vertical mode
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
if ($block) { 
    $subset[$block] = true; 
}
if ($begin) {
    $subset[$begin] = true;
}
if ($end) {
    $subset[$end] = true;
}
if ($begin or $end) {
    $subset[uniord("█")] = true; //block shape!
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

$em2px = $size / $em;
$text2px = $em2px * $textscale;

ob_start();

print "<defs>";

foreach ($layers as $style => $color) {
    $font = file_get_contents("css/fonts/BungeeLayers" . ($orientation==='vertical' ? 'Rotated' : '') . "-" . ucfirst($style) . ".svg");
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

print "</defs>";

$svgdefs = ob_get_clean();

ob_start();

print "<!-- Text: " . str_replace('--', '- -', str_replace('--', '- -', $text)) . " (" . mb_strlen($text) . " bytes) -->";

if ($orientation === 'vertical') {
    print "<g transform='rotate(90) translate(0,-$height)'>";
}

# blocks
$blockwidth = 0;
if ($block) {
    $blockwidth = $charwidths[array_shift(array_keys($layers))][$block];
    foreach ($backgroundlayers as $style => $color) {
        if (!isset($charwidths[$style][$block])) {
            continue;
        }
        $x = $padding;
        $y = $height-$padding-$baseline*$em2px;
        for ($i=0,$l=mb_strlen($text); $i<$l; $i++) {
            print "<use transform='translate($x $y) scale($em2px -$em2px)' xlink:href='#{$style}-$block' style='stroke:none;fill:#$color' />";
            $x += $charwidths[$style][$block]*$em2px;
        }
    }
}

# Text layers output
ob_start(); 

$prev = null;
$shadenudge = isset($layers['shade']) ? 0.04 * $size*$textscale : 0.0;
$textwidth = 0;
foreach ($layers as $style => $color) {
    $x = $padding;
    if ($block) {
        if ($orientation === 'vertical') {
            //$x += $blockwidth*$em2px*0.14 + $size*(0.72)*(1-$textscale)/2;
        } else {
            $x += $blockwidth*$em2px*0.109375 + $size*(1-$textscale)/2;
        }
    }
    $y = $height-$padding - $baseline*$em2px - $size*(0.72)*(1-$textscale)/2;
    $x += $shadenudge * ($orientation === 'vertical' ? -1 : 1);
    $y -= $shadenudge;
    for ($i=0,$l=mb_strlen($text); $i<$l; $i++) {
        $id = uniord(mb_substr($text, $i, 1));
        if (isset($myalts[$id])) {
            $id = $myalts[$id];
        }
        if (!isset($charwidths[$style][$id])) {
            $id = 'notdef';
        }
        if (!$block and isset($kerns[$prev][$id])) {
            $x += $kerns[$prev][$id]*$em2px;
        }

        $ss01fudge = 0;
        if ($orientation === 'vertical' and $block) {
            #this fakes the modified ss01 sidebearings to do simple vertical centering
            $ss01fudge = ($blockwidth*$em2px - $charwidths[$style][$id]*$text2px)/2;
            $x += $ss01fudge;
        }
        print "<use transform='translate($x $y) scale($text2px -$text2px)' xlink:href='#{$style}-$id' style='stroke:none;fill:#$color' />";
        $x += $block ? $blockwidth*$em2px - $ss01fudge : $charwidths[$style][$id]*$text2px;
        $prev = $id;
    }

    $textwidth = $x - $padding;
}

$textcontent = ob_get_clean();

#banner!
$bannerwidth = 0;
$beginwidth = 0;
if ($begin or $end) {
    if ($begin) {
        $beginwidth = $charwidths[array_shift(array_keys($layers))][$begin];
    }
    foreach ($backgroundlayers as $style => $color) {
        $x = $padding;
        $y = $height-$padding-$baseline*$em2px;
        if ($begin) {
            print "<use transform='translate($x $y) scale($em2px -$em2px)' xlink:href='#{$style}-$begin' style='stroke:none;fill:#$color' />";
            $x += $charwidths[$style][$begin]*$em2px;
        }
        $id = uniord("█");
        #squeeze blocks into slightly smaller space
        $blockwidth = $charwidths[$style][$id]*$em2px;
        $remainder = fmod($textwidth, $blockwidth);
        if ($remainder) {
            $numberofblocks = ceil($textwidth / $blockwidth);
            $advancewidth = (($numberofblocks-2)*$blockwidth + $remainder) / ($numberofblocks-1); //work shown upon request
        } else {
            $numberofblocks = $textwidth/$blockwidth;
            $advancewidth = $blockwidth;
        }
        for ($i=0; $i<$numberofblocks; $i++) {
            print "<use transform='translate($x $y) scale($em2px -$em2px)' xlink:href='#{$style}-$id' style='stroke:none;fill:#$color' />";
            $x += $advancewidth;
        }
        $x += $blockwidth - $advancewidth;
        if ($end) {
            print "<use transform='translate($x $y) scale($em2px -$em2px)' xlink:href='#{$style}-$end' style='stroke:none;fill:#$color' />";
            $x += $charwidths[$style][$end]*$em2px;
        }
        $bannerwidth = $x - $padding;
    }
}

#now we have all the information we need to calculate the final dimensions
$width = round(max($textwidth, $bannerwidth) + 2*$padding);

if ($begin) {
    print "<g transform='translate(" . ($beginwidth*$em2px) . " 0)'>";
}
print $textcontent;
if ($begin) {
    print "</g>";
}

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

$tempdir = sys_get_temp_dir();
$outfile = $tempfile = tempnam($tempdir, 'bungee-svg-');
file_put_contents($tempfile, $output);
unset($output);

function convert($args) {
    $cmd = '/usr/local/bin/inkscape';
    foreach ($args as $k => $v) {
        $cmd .= " {$k} " . escapeshellarg($v);
    }
    exec($cmd, $output, $err);
}

switch ($format) {
    case 'pdf':
        header("Content-type: application/pdf");
        $outfile = tempnam($tempdir, 'bungee-pdf-');
        convert(array('-f' => $tempfile, '-A' => $outfile));
        break;
    case 'png':
        header("Content-type: image/png");
        $outfile = tempnam($tempdir, 'bungee-png-');
        convert(array('-f' => $tempfile, '-e' => $outfile, '-d' => 180));
        break;
    default: //svg
        $format = 'svg';
        if (DEBUG) {
            header("Content-type: text/plain; charset=utf-8");
            $output = str_replace("><", ">\n<", $output);
        } else {
            header("Content-type: image/svg+xml");
        }
}

$safetext = "Bungee-" . preg_replace('/[^\w-]+/u', '-', $text);

if (DEBUG) {
    header("Cache-control: no-cache");
} else {
    header("Cache-control: max-age=3600");
}

clearstatcache();

header("Content-disposition: inline; filename=$safetext.$format");
header("Content-length: " . filesize($outfile));

readfile($outfile);

unlink($tempfile);
if ($tempfile !== $outfile) {
    unlink($outfile);
}

exit(0);
