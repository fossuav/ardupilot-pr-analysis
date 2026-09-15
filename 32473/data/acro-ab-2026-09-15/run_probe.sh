#!/bin/bash
# usage: run_probe.sh cond:variant:pre ...
cd ${WORKTREE:-.}
LOCK=${SITL_LOCK:-/tmp/sitl.lock}
OUT=${BUILDLOGS:-./buildlogs}/probe
for spec in "$@"; do
  IFS=: read cond var pre <<< "$spec"
  log=$OUT/run_${cond}_inh${var}.log
  while true; do
    flock -E 99 -w 540 $LOCK env BUILDLOGS=${BUILDLOGS:-./buildlogs} PROBE_OUT=$OUT PROBE_COND=$cond ACRO_INH=$var PROBE_PRE=${pre:-30} \
      python3 Tools/autotest/autotest.py --no-clean --speedup=8 test.Copter.AcroBiasProbe > $log 2>&1
    rc=$?
    [ $rc -eq 99 ] || break
    echo "lock timeout, retry $spec" >> $OUT/driver.log
  done
  echo "$spec rc=$rc $(grep -E 'PROBE LOG|FAILED|PASSED' $log | tail -n 3 | tr '\n' ' ')" >> $OUT/driver.log
done
