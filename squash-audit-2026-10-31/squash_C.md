# Squash C, built 2026-10-31 (not pushed)

Built in the sq-c worktree on fresh branches `sq/<PR>` from each PR's
current head, by cumulative `cherry-pick -n` plus `commit`. Folded commits
keep the first commit's author and date. Every branch's tree equals its PR
head (`git diff <old head> sq/<PR>` empty). Push plan: `push_C.tsv`
(remote andyp1per, lease on each old head). No other andyp1per branch
contains any of these heads, so nothing is stacked on them.

Builds, all clean (rc 0, no warnings):
- SITL copter at every new code commit, 32 commits.
- SITL plane at sq/31274's ESC telemetry fold, its Plane doc commit and its tip.
- CubeOrange-bdshot copter and the iomcu-dshot iofirmware at sq/31274's tip.

The two #34210 commits needed a fresh `waf configure`, as their merge base
differs, and then built. pr_review mechanical gate: #29000, #34210 and
#31274 are clean; #32475 has its pre-existing diff-size note.

## #29000: 3 -> 2, sq/29000 4293e19e9f

- 7d8003272d Copter: switch off fast rate while doing temperature calibration
  (4cc85b68cf + fcc3339b2b; the empty body now describes both)
- 4293e19e9f autotest: check the rate thread is off during temperature calibration (fbf9c380f9)

## #34210: 6 -> 3, sq/34210 4836c83d44

- 38823a70ee AP_Logger: add land failsafe events (b649cfdd8c)
- 4f9bbc5566 Copter: add advanced land failsafe (LAND_FS_OPTIONS bit 0)
  (84f977c110 + bc5a6362d3 + aa2cf2ddcf; the message gains the land-speed
  band, the 2.0 result and what engages the option)
- 4836c83d44 autotest: cover the advanced land failsafe (93dcf216c0 + 5be30dcfff)

## #31274: 30 -> 13, sq/31274 820f2550b0

1. b78ca17cd8 SITL: add SIM_ESC_ERR_RATE (6fe73f3735)
2. 0c20459ed2 AP_ESC_Telem: report SIM_ESC_ERR_RATE from the SITL ESC backend (00d3d50182)
3. ebfda43548 AP_ESC_Telem: add an error rate limit to are_motors_running()
   (cb66e83fde + 0d7ac89ec9 + 5db531fdc2; the message drops the old "only
   reports on a good frame" claim)
4. 4239a853ee AP_Vehicle: fail the ESC takeoff check on a high ESC error rate (3684d45ce3)
5. 3493769179 autotest: changed takeoff blocked message (4ef30eefe0)
6. 05c012c9c7 AP_Motors: add get_test_seq_output_mask() (eccb30a3c6, moved ahead)
7. 35b27a46dd Copter: warn in motor test about an ESC error rate over 1%
   (a9ae4cdc82 + 9efaf7eb79 + 5f27cedfe2 + 4c00536edd + 77f46482c4 + c11583c917;
   subject 58 characters, body describes the motor test only)
8. 6a2be9f1c7 Copter: document the ESC error rate check in TKOFF_RPM_MIN
   (535181712d + 732a25b539 + c736ba44e9 + 4ae2a316c1)
9. aa8f76a9c0 Plane: document the ESC error rate check in Q_TKOFF_RPM_MIN (a0cd91585c + d5c7a7697d)
10. f5a37a7caf AP_HAL_ChibiOS: report the bdshot error rate as a percentage
    (ed05baf35f + 2e53a6400b + e2187aa2b1 + 715c381342)
11. 988f8abb9e AP_HAL_ChibiOS: keep a DShot error rate from a full window after a reset (f0d19ac649, unflown, own commit)
12. 06eda38a7e AP_ESC_Telem: say what a fresh DShot error percentage means (d228911760)
13. 820f2550b0 autotest: test the ESC error rate takeoff check and motor test warning
    (defda06bc8 + a1d434498e + 40518bd547 + db7371c4d8)

Changes from C.md's plan:
- The SITL pair moved to the front. `0d7ac89ec9` edits the line that
  `00d3d50182` adds, so folding it into `cb66e83fde` needs the SITL commit
  in first. Both SITL commits are unchanged.
- `d228911760` stays its own commit after the restart fix, not folded into
  commit 3. Its comment describes the restart behaviour, which exists only
  from commit 11.

## #32475: 54 -> 28, sq/32475 8e931047e5

- The nine base commits are untouched: the branch starts at `f7a5aeb84f`,
  so they keep their hashes.
- The 16 behaviour fixes and today's `ae9b93be1f` are picked unchanged,
  in their order.
- `249d924c23` + `c174d165e9` become `87c105d240` "Copter: name the throw
  uprighting timeout, and say what drop code does", at the naming commit's
  place. At the comment commit's place, `7283b680dc` conflicts in config.h.
- All 26 test commits after the base, today's `16042bc083` included, fold
  into `8e931047e5` "autotest: cover the throw mode fixes", after the
  fixes.

## #34696, #32514, #32270: nothing to do

C.md names no fixups to fold for any of them. #32270's `ee9dc05040` is not
split.
