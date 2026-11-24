# PR #35307 - EKF3 recovers a single-axis flow lockout without the AGL KF

Analysis archive for [ArduPilot/ardupilot#35307](https://github.com/ArduPilot/ardupilot/pull/35307).

Opened 2026-11-20 at `6ba48e9d7e`, branch `pr-flow-lockout-no-aglkf`,
stacked on #35147 (`27bb095723`), which stacks on #34630 and #33484; the
top five commits are this PR's. On by default, as a fix for a silent
divergence.

## What it does

#33484's single-axis lockout recovery scaled its reset by the AGL KF's
height, so it ran only with EK3_OPTIONS bit 3. This scales it by the
height the flow is fused against when the AGL KF is off: the terrain
estimate, or the main filter's own height when the range finder is its
height source. The same tests apply (range fused within 500 ms, no step
lag, restart confirmed). Both non-AGL heights restart from one range
(the terrain estimate after 5 s without one; the main filter when the
range finder becomes its source again, via ResetPositionD), and each
restart is confirmed with the AGL KF's constants. No downward range
finder: no recovery.

Commits: `1c60a62392` plumbing (flowResetHeight() and FlowResetHeight,
behaviour-neutral), `b0fc04d85a` behaviour, `26509d156f` OSD docs,
`6c5a25ecbe` build_options label, `6ba48e9d7e` autotest.

## How it got here

Prototyped while investigating flow averaging, to cure an averaging
runaway on the ARK 5" log, which later proved to be the Replay artifact
#35306 fixes. The first version also reset with no range finder, scaled
by the assumed terrainState - pd. Review rejected that: #33484's log7
already showed a coasting height being "the height the fusion uses"
gives a wrong reset (14.67 -> 2.87 m/s), and a 4.6 log replayed without
its range finder showed resets scaled by 2.0 m against a 0.4-1.0 m range,
diverging again within a second. Two review rounds then added the
terrain restart confirmation, the range-height regime's confirmation,
fusion times for freshness, per-regime variance (Popt, P[9][9]), and
keyed XKF7 and the OSD floor to a lane with a downward range finder.

## Evidence

- SITL (tier 2): five legs with bit 3 clear (recovered; step deferral;
  terrain restart; range-height restart; no range finder, neither
  recovered nor deferred). Without `b0fc04d85a` the test fails at the
  first; with either restart confirmation disabled it fails at that
  one's leg. OSDEKFLanes passes.
- Fleet Replay (tier 1b, 423 logs, beta + #35306): plumbing commit
  identical on all 423. The PR changes 33: flow 1 m/s out 830 -> 411 s
  (lower on 17 cores, higher on 4, at most +4.7 s); GPS p95 lower on 3
  cores (largest 12.05 -> 4.37 m/s), higher on 1 by 0.01. On top of flow
  averaging: 574 -> 331 s, GPS p95 summed -1.3, none worse.

### Superseded 2026-11-23 in its log count

The 423 files of that fleet Replay are 381 distinct logs: 40 flights sit
in the cache under two or three names, so its counts and sums take them
more than once. The numbers stay as measured; re-run on the distinct logs
before citing them.

## Decided, not changed

- Kept under EK3_FEATURE_OPTFLOW_AGL_KF (#33484's define for the flow
  recovery); the build option's label now names the recovery.
- InitVelocityFromFlow's flowResetHeight() check cannot fail (that
  function returns unless bit 3 and aglKf.valid); kept as #35147's
  AGL-only precondition.
- Rover with FLOW_HGT_OVR: the reset scales by the override as the flow
  does, while the range tests describe the terrain estimate; reachable
  before with bit 3. Stated in the PR.
- The latch fields a PX4Flow bus thread reads are #33484's (d1c53122f5;
  #34783 moves PX4Flow to the main loop).

## Open

- #33484's "Both axes wrong" leg (a8eaab68f9) failed once and passed on
  rerun: a reset can fall as the leg clears the fault and disarms, with
  no XKF1 after it. Timing race in that test, not this PR.

### Superseded 2026-11-23

The leg's race is fixed in #33484 (`255fe24724`, 24 of 24).

## 2026-11-20: pending height source switch

While stacking #35312, the range-height restart leg failed about one run
in five: when the range finder came back as the main height source,
`activeHgtSource` changed one update before `ResetPositionD()` reset the
height to the range, and in that update the range-height regime read
confirmed with the baro's height. Caught with replay logging on and
instrumented: one core reset 167 ms after the range returned, its switch
25 ms later. Fixed in `80e1cb5824` (a pending switch counts as an
unconfirmed restart): the failing run's replay defers, the leg passed ten
in ten, and the 423-log fleet replay is unchanged. Pushed and commented
(issuecomment-7049227050).

## 2026-11-20: restacked on #33484's round-19 fixes, pushed `0fec57455e`

The new-reading test now applies to every regime through
`flowResetRangeState()`. Found a latent link failure in this PR's pushed
code: `MIN(..., aglKfRestartConfirmSigma)` in `selectHeightForFusion()`
bound the static constexpr member by reference, which under gnu++11
needs an out-of-class definition; Copter.Replay's build failed to link
once #33484's fixes changed the inlining. Fixed in `48f3825f31` by
reading it by value. Replied (issuecomment-7051121473).

## 2026-11-23: AP-Review's second round fixed, pushed `186c96fa4a`

On #35147's `fc082533e1`, eight commits are now this PR's. `28f9a00d81`
builds the recovery with the range finder compiled out, where
`flowLockoutRecoveryConfigured()` returns false. `186c96fa4a` gives each
deferral reason its own 10 s report timer, so "range stale" no longer
hides the restart that follows it. The both-axes leg fix first pushed here
as `4bcfc44274` moved to #33484 the same day; the tree is unchanged by the
move. Description updated and posted 2026-11-23.

Tier 2, at `ab1cbb1a73` on this code: EK3_FlowAxisLockoutRecovery 24 of
24; EK3_FlowVelocityAtAidingStart, OSDEKFLanes, OpticalFlowFocusAlt,
OpticalFlow and Copter.Replay pass; builds with AP_RANGEFINDER_ENABLED=0
and EK3_FEATURE_OPTFLOW_AGL_KF=0 pass. Tier 1b, `64196a8a82` against
`ab1cbb1a73`: no EKF state change on 385 distinct logs, 22 print more
deferral messages. CI on this head had not finished when this was written.

Open: a 5 s height timeout with the range finder as the height source
restarts the height through `ResetHeight()` without arming
`rngHgtRestartConfirm` (AP-Review, low). Derived from the source, not
measured. Flight code, not changed.

Reply drafted and held at Andy's word, 2026-11-23, not posted:

> The guard is in d5301acbb1, and a build with the range finder compiled out now links. The description counts the eight commits. The height timeout restarting the height from one range sample is still open.

## 2026-11-23 (later): restacked on #34630's comment, pushed `21597f0586`

Same code. `28f9a00d81` is now `d5301acbb1` and `186c96fa4a` is
`21597f0586`; the held reply above quotes the new hashes.

AP-Review's round 2 at `186c96fa4a` leaves two low findings, not changed:

- `ResetHeight()` on a same-source height timeout does not arm
  `rngHgtRestartConfirm`, the item already recorded above.
- New: the compiler may reorder the two plain stores at
  `AP_NavEKF3_OptFlowFusion.cpp:847`. The bot reports GCC -O3 writing
  `flowVelResetUnhealthy = true` first, so on a multi-core Linux board
  PX4Flow's bus thread could see the latch with an old run start, which
  `0be392bd9e` set out to prevent. Its claim, not reproduced here.

CI and AP-Review on this head had not finished when this was written.

## 2026-11-24: AP-Review round 5 at `21597f0586`, COMMENT

The same two lows as before, nothing new: the same-source height timeout
restart is not confirmed (`AP_NavEKF3_OptFlowFusion.cpp:1028`), and the
store order of the latch and run start across threads (`:849`). See
#35312's entry for the optional `EK3_OPTIONS` rate caveat on this PR's
sentence.

## 2026-11-24: round 5's low fixed and the EK3_OPTIONS rate, local `fc/35307-1124b` (`e6b3835829`), not pushed

- `ba0f2cacaf`: `EK3_OPTIONS` says the recovery needs flow samples no
  more than 250 ms apart. A first wording said 4 Hz or faster; the Codex
  cold read pointed out that the code tests the gap, not the rate.
- `8d351c271a`: `ResetHeight()` arms `rngHgtRestartConfirm` whenever the
  range finder is the height source, so a restart after a 5 s height
  timeout is confirmed as one after a switch is.
- `e6b3835829`: a new leg. Range finder height source, climbed to
  6-8 m, the range stepped 4 m long and a flow axis stuck: the height
  times out and restarts from the long reading while the lockout waits.
  SITL, tier 2: without the fix the first core checked resets on the
  restart sample in 3 runs of 3; with it the whole test passes 3 of 3.
  A first version stepped the range 3 m short and failed both ways.
  Probes showed why: a restart to a short height widens the flow gate,
  the locked axis passes again at the reset and no recovery is pending
  in the confirmation window. A long step narrows the gate and the
  lockout outlasts the reset.
- Replay, tier 1b: the 423 cached logs through Replay without and with
  the fix, unchanged 423 of 423 (2.88 M XKF1 rows; two logs empty in
  both).
- A SITL build with `EK3_FEATURE_OPTFLOW_AGL_KF` 0 builds.
- Not changed: round 5's second low, the order of the quality latch's
  stores against the PX4Flow bus thread. #33484's `0be392bd9e` orders
  them in source and says that does not make them safe to share; #34783
  removes the cross-thread access by publishing PX4Flow frames from the
  main loop. The audit reads it OPEN, as expected.

Quick review: gate clean (notes only), cold reads: the doc wording
(fixed), the fix and the test no findings. Description drafted: eleven
commits, six legs, the third restart. #35312 restacked on it. The reply
held on 11-23 is folded into a new draft. Not pushed.

Pushed 2026-11-24 at `e6b3835829`. Description and reply
(issuecomment-7136265843) posted the same day.
