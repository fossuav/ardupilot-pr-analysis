#!/bin/bash
# usage: run_fl.sh <tag> [ENV=VAL ...]
# one FlowLandProbe run through the shared SITL lock, 900 s hard timeout
S=${SCRATCH:?set SCRATCH to a scratch directory}
OUT=$S/flow_landing/logs
LOCK=${SITL_LOCK:-$S/sitl.lock}
BL=${BUILDLOGS:-$S/buildlogs}
WT=${WT:?set WT to the ArduPilot worktree}
mkdir -p $OUT
tag=$1; shift
cd $WT || exit 1
while true; do
  flock -E 99 -w 540 $LOCK timeout 900 env BUILDLOGS=$BL PROBE_OUT=$OUT PROBE_TAG=$tag "$@" \
    python3 Tools/autotest/autotest.py --no-clean ${AUTOTEST_ARGS} test.Copter.FlowLandProbe > $OUT/$tag.log 2>&1
  rc=$?
  [ $rc -eq 99 ] || break
  echo "$(date +%T) lock timeout, retry $tag" >> $OUT/driver.log
done
res=$(grep -a "PROBE RESULT" $OUT/$tag.log | tail -n 1)
echo "$(date +%T) $tag rc=$rc $res" | tee -a $OUT/driver.log
pkill -f "$WT/build/sitl/bin/arducopter" 2>/dev/null
exit 0
