#!/bin/bash
# usage: run_rig.sh BINARY TAG [ENV=VAL ...]; one UnevenGroundProbe run through the shared SITL lock.
# WORKTREE is a checkout with probe.diff applied and built for sitl; the binary is copied into it.
WT=${WORKTREE:?set WORKTREE to the probe checkout}
OUT=${PROBE_OUT_DIR:?set PROBE_OUT_DIR}
LOCK=${SITL_LOCK:-/tmp/sitl.lock}
BIN=$1; TAG=$2; shift 2
exec 9>"$LOCK"; flock 9
cd "$WT" || exit 2
cp -f "$BIN" build/sitl/bin/arducopter
env PROBE_OUT=$OUT PROBE_TAG=$TAG "$@" timeout 1500 python3 Tools/autotest/autotest.py --no-clean --speedup=10 \
    test.Copter.UnevenGroundProbe > $OUT/$TAG.log 2>&1
echo "$TAG rc=$? $(grep -aE '>>>> (PASSED|FAILED) STEP' $OUT/$TAG.log | tail -n 1)"
# cases: PROBE_CASE=flat|rise|fall; PROBE_ALT=6 for the fall off a slope from 6 m;
# PROBE_ORIGIN_DALT=-30 for the origin 30 m low; PROBE_TERRAIN=0 for no terrain data
