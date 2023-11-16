#!/bin/sh

set -e  # make sure to abort on error
set -x  # echo commands


python scripts/assembleSources.py
python scripts/assembleRotatedSources.py
python scripts/assembleColorSources.py


for folder in Bungee_Basic Bungee_Layers Bungee_Rotated Bungee_Color
do
    for ufo in build/$folder/*.ufo
    do
        fontmake -o ttf \
            --overlaps-backend pathops \
            --output-dir build/fonts/$folder \
            --no-production-names \
            -f \
            -u $ufo
    done
    for ttf in build/fonts/$folder/*.ttf
    do
        gftools fix-nonhinting $ttf $ttf
    done
    # Remove leftovers from gftools fix-nonhinting
    rm build/fonts/$folder/*backup-fonttools*.ttf
done


# Add SVG table to COLRv1 font
maximum_color --keep_glyph_names build/fonts/Bungee_Color/BungeeSpice-Regular.ttf
mv build/Font.ttf build/fonts/Bungee_Color/BungeeSpice-Regular.ttf
