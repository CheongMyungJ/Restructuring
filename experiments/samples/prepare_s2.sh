#!/bin/bash
# Prepare S2 (Cosmos+ OpenSSD GreedyFTL 3.0.0 firmware, GPLv3) + its PDF documents.
# usage: prepare_s2.sh <out_dir>     -> <out_dir>/{legacy,materials,hidden/qa.json}
set -e
OUT=${1:?out dir}; HERE=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d); git clone -q --depth 1 https://github.com/Cosmos-OpenSSD/Cosmos-plus-OpenSSD.git $TMP/c
mkdir -p $OUT/legacy $OUT/materials $OUT/hidden
cp -r $TMP/c/source/software/GreedyFTL-3.0.0/* $OUT/legacy/
cp $TMP/c/doc/*.pdf $OUT/materials/
cp $HERE/s2_cosmos/hidden/qa.json $OUT/hidden/
rm -rf $TMP
echo "S2 ready: $(find $OUT/legacy -name '*.[ch]' | xargs cat | wc -l) lines of C"
