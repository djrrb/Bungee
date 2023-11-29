#!/bin/sh

set -x  # echo commands

mkdir -p build/fontbakery/

result=0

for folder in Bungee_Basic Bungee_Layers Bungee_Rotated Bungee_Color
do
    for ttf in build/fonts/$folder/*.ttf
    do
        fontbakery check-googlefonts \
            -x com.google.fonts/check/alt_caron \
            -x com.google.fonts/check/contour_count \
            -x com.google.fonts/check/glyphsets/shape_languages \
            -x com.google.fonts/check/vertical_metrics_regressions \
            --html build/fontbakery/$(basename $ttf .ttf).html \
            $ttf
        if [ $? -ne 0 ]; then
            result=$((result+1))
        fi
    done
done

exit $result
