#!/bin/bash
# replay_pair.sh: build the instrumented topup3 Replay without and with the
# static yaw fix in worktree tfix-ab-34942r (only), keep both
# binaries here, and replay loglist2.txt through each into out2-nofix/ and
# out2-fix/.
# SCRATCH: the scratch directory; WT: the worktree
set -e
S=${SCRATCH:?set SCRATCH to the scratch directory}/r1030/34942
WT=${WT:-$HOME/github/tfix-ab-34942r}
cd "$WT"
[ "$(pwd -P)" = "$WT" ] || exit 2
git apply -R "$S/static-yaw-fix.diff"
./waf replay > "$S/build_replay_nofix.log" 2>&1
cp build/sitl/tool/Replay "$S/Replay-nofix"
git apply "$S/static-yaw-fix.diff"
./waf replay > "$S/build_replay_fix.log" 2>&1
cp build/sitl/tool/Replay "$S/Replay-fix"
md5sum "$S/Replay-nofix" "$S/Replay-fix"
R="$(cd "$(dirname "$0")/../replay" && pwd)/run_replay.sh"
bash $R "$S/Replay-nofix" "$S/loglist2.txt" "$S/out2-nofix"
bash $R "$S/Replay-fix" "$S/loglist2.txt" "$S/out2-fix"
for d in "$S"/out2-nofix/* "$S"/out2-fix/*; do echo "$(basename $(dirname $d))/$(basename $d): $(tail -1 $d/replay.out)"; done
echo PAIR_DONE
