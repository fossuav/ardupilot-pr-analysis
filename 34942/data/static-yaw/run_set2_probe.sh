#!/bin/bash
# run_set2_probe.sh: run ProbeStaticYawSet2 on master (scratch worktree
# tfix-ab-34942q at 278a68a57a) and on the fix (tfix-ab-34942p), with the
# probe test inserted uncommitted and removed afterwards.
# SCRATCH: the scratch directory holding tfix/ and r1030/34942; Q, F: the two worktrees
S=${SCRATCH:?set SCRATCH to the scratch directory}
P=$S/r1030/34942
Q=${Q:-$HOME/github/tfix-ab-34942q}
F=${F:-$HOME/github/tfix-ab-34942p}
[ -d "$Q" ] || git -C "$F" worktree add --detach "$Q" 278a68a57a > /dev/null 2>&1
bash $S/tfix/build_ab.sh "$Q" || exit 2
for wt in "$Q" "$F"; do
    python3 -I $P/insert_set2_probe.py "$wt" || exit 2
    bash $S/tfix/run_keep.sh "$wt" "set2-$(basename $wt)" ProbeStaticYawSet2
    git -C "$wt" restore --source=HEAD -- Tools/autotest/arducopter.py
done
echo PROBE_DONE
