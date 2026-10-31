#!/bin/bash
# cmp_34942_stages.sh: apply #34942's replayed text stages (stages-v2.py,
# 1 2 3 4 5 G 6) to refresh12's EKF3 before the topup, and diff the result
# against the EKF3 the cherry-picks produced. Empty diff = the topup's code is
# the code the Replay evidence was measured on.
set -e
WT=/home/andy/github/sfd-refresh12
PRE=${1:-35e04e1064}
STAGES=/home/andy/github/ardupilot-pr-analysis/34942/data/replay/stages-v2.py
OUT=/tmp/claude-1000/-home-andy-github-smallfastdrone-beta/c72a7562-fe47-4333-b873-673b10019194/scratchpad/r1030/34942/stagecmp
rm -rf "$OUT"
mkdir -p "$OUT/libraries"
git -C "$WT" archive "$PRE" libraries/AP_NavEKF3 | tar -x -C "$OUT"
for st in 1 2 3 4 5 G 6; do
    python3 -I "$STAGES" "$OUT" "$st"
done
mkdir -p "$OUT/head"
git -C "$WT" archive HEAD libraries/AP_NavEKF3 | tar -x -C "$OUT/head"
diff -ru "$OUT/libraries/AP_NavEKF3" "$OUT/head/libraries/AP_NavEKF3" && echo "IDENTICAL: topup EKF3 == stages-v2 on $PRE"
