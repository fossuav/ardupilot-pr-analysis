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
