#!/bin/bash
#======================================================================
# (Re)generate hidden/fixtures/*/expected by running the LEGACY application
# with PRODUCTION JAVA_OPTS through the harness.
#
#   tools/record_expected.sh [legacy_dir] [--fixtures 01_x,...]
#======================================================================
set -e
HIDDEN=$(cd "$(dirname "$0")/.." && pwd)
APP=${1:-$HIDDEN/../legacy}
shift || true
PROD_OPTS="-Duser.timezone=Asia/Seoul -Dtlog.dup.policy=LAST"
WORK=$(mktemp -d /tmp/tlog_record.XXXXXX)

set +e
python3 "$HIDDEN/harness/harness.py" "$APP" --java-opts "$PROD_OPTS" --work "$WORK" \
        --out "$WORK/record.json" "$@" > "$WORK/record.log" 2>&1
set -e

python3 - "$WORK/record.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
bad = [f["name"] for f in r["fixtures"] if f.get("errors")]
if r.get("build", {}).get("rc", 0) not in (0, None) or bad:
    sys.exit("record: infrastructure errors in %s (build=%s)" % (bad, r.get("build")))
PY

for fx in "$HIDDEN"/fixtures/*/; do
    name=$(basename "$fx")
    if [ -d "$WORK/$name/actual" ]; then
        rm -rf "$fx/expected"
        cp -r "$WORK/$name/actual" "$fx/expected"
        echo "recorded $name"
    fi
done
echo "work dir: $WORK"
