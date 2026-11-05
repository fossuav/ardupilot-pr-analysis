#!/bin/bash
# bisect_srcset.sh K [K...]: for each K, build refresh12 topup2's tip plus
# #34942's first K EKF3 commits (as picked on refresh12) in the scratch
# worktree tfix-ab-34942b and run MAV_CMD_SET_EKF_SOURCE_SET.
# SCRATCH: the scratch directory holding tfix/; WT: the worktree; REFRESH12: the refresh12 checkout
S=${SCRATCH:?set SCRATCH to the scratch directory}
WT=${WT:-$HOME/github/tfix-ab-34942b}
PICKS=(e78e5ccda2 e9e0c912b2 a9c2061a3f b80e115edc a6770bfbad 4dae59caf7 992bb00935)
[ -d "$WT" ] || git -C "${REFRESH12:-$HOME/github/sfd-refresh12}" worktree add --detach "$WT" 35e04e1064 > /dev/null 2>&1
cd "$WT" || exit 2
[ "$(pwd -P)" = "$WT" ] || exit 2
for k in "$@"; do
    git restore --source=HEAD --staged --worktree -- . || exit 2
    git checkout -q --detach 35e04e1064 || exit 2
    for ((i = 0; i < k; i++)); do
        git cherry-pick -n "${PICKS[$i]}" > /dev/null || { echo "pick ${PICKS[$i]} failed"; exit 2; }
    done
    bash $S/tfix/build_ab.sh "$WT" > /dev/null || { echo "build failed at K=$k"; exit 2; }
    bash $S/tfix/run_keep.sh "$WT" "bisect-k$k" MAV_CMD_SET_EKF_SOURCE_SET
done
git restore --source=HEAD --staged --worktree -- .
echo BISECT_DONE
