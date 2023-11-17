#!/bin/sh

set -e  # make sure to abort on error
set -x  # echo commands

mkdir -p build/fontbakery/

for folder in Bungee_Basic Bungee_Layers Bungee_Rotated Bungee_Color
do
    for ttf in build/fonts/$folder/*.ttf
    do
		fontbakery check-googlefonts \
			-x com.google.fonts/check/alt_caron \
			-x com.google.fonts/check/contour_count \
			-x com.google.fonts/check/vertical_metrics_regressions \
			--html build/fontbakery/$(basename $ttf .ttf).html \
			$ttf
    done
done
