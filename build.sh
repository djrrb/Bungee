#!/bin/sh

set -e  # make sure to abort on error
set -x  # echo commands


python scripts/assembleSources.py
python scripts/assembleRotatedSources.py


for folder in Bungee_Basic Bungee_Layers Bungee_Rotated
do
    for ufo in build/$folder/*.ufo
    do
        fontmake -o ttf \
            --overlaps-backend pathops \
            --output-dir build/fonts/$folder \
            --no-production-names \
            -u $ufo
    done
done
