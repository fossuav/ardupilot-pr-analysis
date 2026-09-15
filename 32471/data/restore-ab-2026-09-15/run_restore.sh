#!/bin/bash
# usage: run_restore.sh specfile
# each spec line: <test> <tag> [ENV=VAL ...]
# runs one autotest per line through the shared SITL lock, copying the flight log to $OUT/<tag>.BIN
WT=${WT:-.}
LOCK=${SITL_LOCK:-/tmp/sitl.lock}
OUT=${PROBE_OUT:-./restore_ab_logs}
BL=${BUILDLOGS:-./buildlogs}
mkdir -p $OUT
cd $WT || exit 1
while read -r test tag envs; do
  [ -z "$test" ] && continue
  case "$test" in \#*) continue;; esac
  if [ -f "$OUT/$tag.BIN" ]; then
    echo "$(date +%T) skip $tag (done)" >> $OUT/driver.log
    continue
  fi
  speed=""
  [ "$test" = "RestoreAcroProbe" ] && speed="--speedup=10"
  while true; do
    flock -E 99 -w 540 $LOCK env BUILDLOGS=$BL PROBE_OUT=$OUT PROBE_TAG=$tag $envs \
      python3 Tools/autotest/autotest.py --no-clean $speed test.Copter.$test > $OUT/$tag.log 2>&1
    rc=$?
    [ $rc -eq 99 ] || break
    echo "$(date +%T) lock timeout, retry $tag" >> $OUT/driver.log
  done
  echo "$(date +%T) $tag rc=$rc $(grep -aE '>>>> (PASSED|FAILED) STEP' $OUT/$tag.log | tail -n 1)" >> $OUT/driver.log
done < "$1"
echo "$(date +%T) done $1" >> $OUT/driver.log
