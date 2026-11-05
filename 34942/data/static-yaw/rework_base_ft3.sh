#!/bin/bash
# rework_base_ft3.sh: on the rework's Replay base (refresh12 2e2936166d plus
# stages-v2.py 1 2 3 4 5 G 6 and instrument-v2.diff), replay Flight test 3
# without and with the static yaw fix, in scratch worktree tfix-ab-34942v,
# and score both with the rework's arm_table.py.
# SCRATCH: the scratch directory; WT: the worktree; REFRESH12: the refresh12 checkout
set -e
S=${SCRATCH:?set SCRATCH to the scratch directory}/r1030/34942
D="$(cd "$(dirname "$0")/../replay" && pwd)"
WT=${WT:-$HOME/github/tfix-ab-34942v}
[ -d "$WT" ] || git -C "${REFRESH12:-$HOME/github/sfd-refresh12}" worktree add --detach "$WT" 2e2936166d > /dev/null 2>&1
cd "$WT"
[ "$(pwd -P)" = "$WT" ] || exit 2
if ! grep -q ABTEST libraries/AP_NavEKF3/AP_NavEKF3_Logging.cpp; then
    for st in 1 2 3 4 5 G 6; do python3 -I $D/stages-v2.py "$WT" $st; done
    git apply $D/instrument-v2.diff
fi
git submodule update --init --recursive -q > $S/build_v.log 2>&1
./waf configure --board sitl >> $S/build_v.log 2>&1
./waf replay >> $S/build_v.log 2>&1
cp build/sitl/tool/Replay $S/Replay-v-nofix
git apply $S/static-yaw-fix.diff
./waf replay >> $S/build_v.log 2>&1
cp build/sitl/tool/Replay $S/Replay-v-fix
git apply -R $S/static-yaw-fix.diff
echo "$S/logs/q25-0cb4-ft3.bin" > $S/loglist-ft3.txt
bash $D/run_replay.sh $S/Replay-v-nofix $S/loglist-ft3.txt $S/out-v-nofix
bash $D/run_replay.sh $S/Replay-v-fix $S/loglist-ft3.txt $S/out-v-fix
for v in nofix fix; do echo "== rework base, $v"; python3 $D/arm_table.py $S/loglist-ft3.txt $S/out-v-$v; done
