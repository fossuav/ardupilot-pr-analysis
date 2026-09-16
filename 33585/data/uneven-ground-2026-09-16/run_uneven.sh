#!/bin/bash
# usage: run_uneven.sh tag [ENV=VAL ...]; one UnevenGroundProbe run through the shared SITL lock
WT=${WORKTREE:?set WORKTREE to the probe checkout}
LOCK=${SITL_LOCK:-/tmp/sitl.lock}
OUT=${PROBE_OUT_DIR:?set PROBE_OUT_DIR}
tag=$1; shift
cd $WT || exit 1
[ -f "$OUT/$tag.BIN" ] && { echo "$tag already done"; exit 0; }
while true; do
  flock -E 99 -w 540 $LOCK timeout -k 30 900 env BUILDLOGS=${BUILDLOGS:-./buildlogs} PROBE_OUT=$OUT PROBE_TAG=$tag "$@" \
    python3 Tools/autotest/autotest.py --no-clean --speedup=10 test.Copter.UnevenGroundProbe > $OUT/$tag.log 2>&1
  rc=$?
  [ $rc -eq 99 ] || break
  echo "$(date +%T) lock timeout, retry $tag"
done
echo "$(date +%T) $tag rc=$rc $(grep -aE '>>>> (PASSED|FAILED) STEP' $OUT/$tag.log | tail -n 1)"
