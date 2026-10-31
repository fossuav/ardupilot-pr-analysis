# Squash A, 2026-10-31: #34942, #32471, #32473

Built in /home/andy/github/sq-a (new worktree, now detached at sq/32473-1031).
Nothing pushed; push plan in push_A.tsv (remote andyp1per, leases on the
current heads, all confirmed with ls-remote).

## #34942, pr-ekf3-gnd-hgt-check: 2a52c965e2 -> sq/34942 3c73e8b64b (10 -> 9)

- 1-4 unchanged (d6825422d5 .. c7fc88ce75, same SHAs).
- 5 bf1ea90b4e -> be28758909: reworded. The SFD-O4 sentence now reads
  "eight flights of another vehicle" and adds that on six later flights it
  moves the flow core's yaw by 0.14-0.29 deg from EKF start at every boot.
- 6 7cf54da6dd -> d0e8e22ce0 (same tree as the original).
- G 21a8e3a683 + 2a52c965e2 -> ab8b538157, G's message extended with the
  wait while a measured vertical velocity is fused (the ship case, the
  EK3HardLandingRearm figure).
- 3da7a8cf2e -> 9ebb3a11ac; dc76e048a6 -> 3c73e8b64b, on top.
- Tree: `git diff 2a52c965e2 sq/34942` empty.
- Builds: SITL copter at ab8b538157 (the one new code tree; commits 5 and 6
  have the originals' trees) and at the tip, no warnings; Replay builds and
  runs log68 at the tip.
- Gate: one must-fix, a false positive. `dal.snprintf` into the pre-arm
  message buffer (AP_NavEKF3_Outputs.cpp:115) matches the printf check; the
  old head has the identical tree.

## #32471, pr-vrf-core: 5afa8d69fb -> sq/32471 0ffebdf4c3 (50 -> 44)

Deviation from A.md: the two fixes cannot fold into f1b61c9cf8. They call
hoverZBiasApplied(), first in 1f809d9a13 (commit 25), and a7fdc4d09b also
getAccelIndex(), first in ab79d946ee (commit 31), so commits 3-30 would not
build. A.md's dry-run checked application only. Folded instead into the
first commits where their helpers exist, each in the same family:
- 1f809d9a13 + 7e0882eb10 -> a7c0dd2176 (hover Z-bias off the inactive IMU
  compare, and now off the covariance prediction); message extended.
- ab79d946ee + a7fdc4d09b -> 48031ab1e8 (the accel bias accessors; AHRS's
  getAccelBias() now includes the applied correction); message extended.
Both targets are in every flown build; both fixes flew with apply on and
were verified by the 10-31 RISK A/B.
- 1-24 unchanged (to 8659291d12, same SHAs).
- 9a9f3a8aed + 235e1c1c19 + ae81b5886d -> e3d6a7c48d (one autotest commit).
- 04e501e13d + 54d41e98c1 + 5afa8d69fb -> 0ffebdf4c3 (one autotest commit).
- On top as before: 19206748ae, 01227784b6 (+1c14ca0a3e), 3973add04c
  (+d9e7d85f5c), 85dbca9896 (+117508173e); da4ec5479f and feddc0eea2 kept.
- Tree: `git diff 5afa8d69fb sq/32471` empty; from da4ec5479f's copy on,
  every commit's tree equals its original's.
- Builds: SITL copter at the six new code trees (a7c0dd2176, 0c262ac347,
  91366f243e, 58a7408099, 78916b65f1, 48031ab1e8) and the tip, no warnings;
  Replay builds and runs log68 at the tip.
- Gate: three notes, subjects over 72 characters, all unchanged subjects.

## #32473, pr-acro-bias-inhibit: f945737262 -> sq/32473-1031 1edfa5daf1

(sq/32473 already exists from 2026-10-04 in /home/andy/github/sq-32473; not
touched.)
- Restacked on sq/32471: d3b5890246 -> df2bc0b558, 115050a65d -> 28fcc46137,
  968ea7d7e5 -> 719b2caffe, 3ca94847db -> 1edfa5daf1. f945737262 drops (its
  cherry-pick is empty: #32471's 54d41e98c1 is in the squashed test commit).
- Conflict: d3b5890246's ArduCopter/Parameters.cpp, resolved by rerere with
  refresh12's resolution; the ACC_ZBIAS_LEARN block equals refresh12's apart
  from the index (25 here, 23 on SFD).
- Check: #32473's own diff (d9e7d85f5c..3ca94847db against
  sq/32471..sq/32473-1031) is identical, line for line, in every file but
  Parameters.cpp, and there its word-level changes to the description (the
  acro clause, "learns", the reboot sentence, the Bit 3 sentence) are
  identical, applied to v3's base text.
- Builds: SITL copter at df2bc0b558, 719b2caffe and the tip, no warnings.
- Gate: the same three notes, from the #32471 commits it carries.
