#!/bin/bash
# cmp_34942_stages.sh: apply #34942's replayed text stages (stages-v2.py,
# 1 2 3 4 5 G 6) to refresh12's EKF3 before the topup, and diff the result
# against the EKF3 the cherry-picks produced. Empty diff = the topup's code is
# the code the Replay evidence was measured on.
# REFRESH12: the refresh12 checkout; SCRATCH: a scratch directory for the output
set -e
WT=${REFRESH12:-$HOME/github/sfd-refresh12}
PRE=${1:-35e04e1064}
STAGES="$(cd "$(dirname "$0")/../replay" && pwd)/stages-v2.py"
OUT=${SCRATCH:?set SCRATCH to a scratch directory}/r1030/34942/stagecmp
rm -rf "$OUT"
mkdir -p "$OUT/libraries"
git -C "$WT" archive "$PRE" libraries/AP_NavEKF3 | tar -x -C "$OUT"
for st in 1 2 3 4 5 G 6; do
    python3 -I "$STAGES" "$OUT" "$st"
done
mkdir -p "$OUT/head"
git -C "$WT" archive HEAD libraries/AP_NavEKF3 | tar -x -C "$OUT/head"
diff -ru "$OUT/libraries/AP_NavEKF3" "$OUT/head/libraries/AP_NavEKF3" && echo "IDENTICAL: topup EKF3 == stages-v2 on $PRE"
