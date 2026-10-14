#!/bin/bash
# Prepare S1 (NFL NAND flash layer) from the open-source dhara repository (ISC license), de-branded.
# usage: prepare_s1.sh <out_dir>     -> <out_dir>/{legacy,materials,hidden}
set -e
OUT=${1:?out dir}; HERE=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d); git clone -q https://github.com/dlbeer/dhara.git $TMP/dhara; git -C $TMP/dhara checkout -q 1b166e4
mkdir -p $OUT/legacy/nfl $OUT/legacy/tests $OUT/materials $OUT/hidden
python3 - "$TMP/dhara" "$OUT" <<'PY'
import re, sys, os
src, out = sys.argv[1], sys.argv[2]
def tr(p, d):
    t = open(os.path.join(src, p), encoding='utf-8').read()
    t = re.sub(r'\A/\* Dhara - NAND flash management layer.*?\*/\n\n?', '/* NFL - NAND flash layer (firmware storage core) */\n\n', t, flags=re.S)
    for a, b in [('dhara_', 'nfl_'), ('DHARA_', 'NFL_'), ('dhara/', 'nfl/'), ('Dhara', 'NFL'), ('dhara', 'nfl')]:
        t = t.replace(a, b)
    t = t.replace("(buf[0] == 'D') &&\n\t       (buf[1] == 'h') &&\n\t       (buf[2] == 'a')", "(buf[0] == 'N') &&\n\t       (buf[1] == 'f') &&\n\t       (buf[2] == 'L')")
    t = t.replace("buf[0] = 'D';\n\tbuf[1] = 'h';\n\tbuf[2] = 'a';", "buf[0] = 'N';\n\tbuf[1] = 'f';\n\tbuf[2] = 'L';")
    t = re.sub(r'.*(Daniel Beer|dlbeer|github).*\n', '', t, flags=re.I)
    os.makedirs(os.path.dirname(os.path.join(out, d)), exist_ok=True)
    open(os.path.join(out, d), 'w', encoding='utf-8').write(t)
for f in os.listdir(os.path.join(src, 'dhara')):
    tr('dhara/' + f, 'legacy/nfl/' + f)
for f in ['sim.c', 'sim.h', 'util.c', 'util.h', 'jtutil.c', 'jtutil.h', 'journal.c', 'recovery.c', 'jfill.c', 'map.c', 'epoch_roll.c', 'nand.c', 'error.c']:
    tr('tests/' + f, 'legacy/tests/' + f)
tr('README', 'legacy/README')
tr('map_internals.txt', 'materials/map_internals.txt')
PY
cp $HERE/s1_nandftl/Makefile.legacy $OUT/legacy/Makefile
cp -r $HERE/s1_nandftl/hidden/* $OUT/hidden/
mkdir -p $OUT/hidden/legacy_ref && cp -r $OUT/legacy/nfl $OUT/hidden/legacy_ref/
make -s -C $OUT/legacy test
python3 $OUT/hidden/run_hidden_tests.py $OUT/legacy
rm -rf $TMP
