#!/bin/bash
# Soak Copter.EKF3RangeFinderOnGround and print the per-leg numbers.
#
# Usage: soak.sh <iterations> <ardupilot-checkout> <outdir>
#
# One iteration is about 11 s of wall clock for 10.3 minutes of sim time.
# Build first: ./waf configure --board sitl && ./waf copter
set -u
N=${1:-20}
TREE=${2:-.}
OUT=${3:-./soak-out}
mkdir -p "$OUT"

for i in $(seq 1 "$N"); do
    (cd "$TREE" && python3 Tools/autotest/autotest.py \
        test.Copter.EKF3RangeFinderOnGround) > "$OUT/run_$i.log" 2>&1
    echo "iter $i EXIT=$?"
done

printf "\n%-5s %-8s %-14s %-14s %-8s %-14s %s\n" \
    iter leg1 leg2 leg3 leg4 leg5 result
for f in $(ls -v "$OUT"/run_*.log); do
    i=$(basename "$f" .log | sed 's/run_//')
    l1=$(grep -o "EKF height while armed on the ground: [-0-9.]*m" "$f" |
             head -1 | grep -o "[-0-9.]*m$")
    mapfile -t climbs < <(grep -o "climbed [0-9.]*m, EKF estimated [-0-9.]*m" "$f" |
                              sed 's/climbed //; s/m, EKF estimated /\//; s/m$//')
    l4=$(grep -o "lowest EKF terrain offset [-0-9.]*m" "$f" |
             head -1 | grep -o "[-0-9.]*m$")
    if grep -q "PASSED STEP" "$f"; then
        res=PASS
    elif grep -qE "FAILED STEP|Traceback" "$f"; then
        res=FAIL
    else
        res=INCOMPLETE
    fi
    printf "%-5s %-8s %-14s %-14s %-8s %-14s %s\n" "$i" "${l1:--}" \
        "${climbs[0]:--}" "${climbs[1]:--}" "${l4:--}" "${climbs[2]:--}" "$res"
done
