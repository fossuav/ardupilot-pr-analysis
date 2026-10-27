# Issue #34894: an EKF lane whose updates are all refused keeps reporting healthy

**Not a PR.** [ArduPilot/ardupilot#34894](https://github.com/ArduPilot/ardupilot/issues/34894),
opened 2026-10-26 by an outside reporter. Recorded 2026-10-27 in case we
pick it up; no branch, no code.

## The report

A HEXAX on CubeOrange+ with two F9Ps, V4.4.4 with **EKF2**, crashed at
7 m/s in GUIDED. The primary lane had been initialised about 50 m below
ground and never corrected, though both GNSS had a good fix; in flight it
was switched out, and the healthy lane then put the vehicle 50 m above a
home captured from the bad one. No log (customer site).

The reporter's Codex analysis reproduces the gap on 4.7.2 EKF3 in SITL by
**injecting** covariance into lane 0 (`P[9][9]` 2700, `P[15][15]` 1e-4,
`P[9][15]` -1, plus a 0.04 m/s/s IMU 0 accel bias step): GUIDED arming
with all checks passes with about 51 m of height error, and after a lane
switch the stationary vehicle reads about 52 m above home. A patch zip is
attached to the issue: reset the covariance after a numerical rejection,
and export the rejection through the fault mask. Their numbers: LAND
touchdown speed 7.81 m/s on baseline, 0.50 m/s with the patch.

Evidence tier: the crash is tier 1 but unlogged; the repro is tier 2 with
an injected cause. **What corrupted the covariance in flight is
unknown** - the repro shows why it was never caught, not how it started.

## What the code does (master `e96bd9053e`, derived from the source, not run)

- `FuseVelPosNED()` stamps `lastHgtPassTime_ms` (and the velocity and
  position pass times) when the innovation test passes, before
  `FinishFusion()` (`AP_NavEKF3_core.cpp:1999`) refuses the update if any
  `KHP[s][s] > P[s][s]`. Refused every time, the lane never corrects and
  never reaches the height or position timeout.
- The refusal sets `faultStatus.bad_dpos` and its siblings, which
  `getFilterFaults()` (`AP_NavEKF3_Outputs.cpp:566`) does not export.
- EKF2 has the same order (`AP_NavEKF2_PosVelFusion.cpp`: pass time at
  761, negative-variance check at 850) and the same fault mask.
- The report also cites Copter's `barometer_checks()` skipping the
  altitude-disparity check when both predicted horizontal position flags
  are set; not examined here.

## The direction posted on the issue (2026-10-27)

[Comment](https://github.com/ArduPilot/ardupilot/issues/34894#issuecomment-6445978979):
stamp the pass times only when the fusion is applied. A lane whose
updates are all refused then reaches the existing timeout after
`hgtRetryTimeMode12_ms` 5 s or `hgtRetryTimeMode0_ms` 10 s, and
`ResetHeight()` already does the recovery the reporter's patch adds: it
sets the height to the measurement and calls `zeroStatesVarCov(9, 9)`,
which clears an injected `P[9][15]`. While timed out `vert_pos` is false,
so a primary lane fails Copter's `ekf_alt_ok()` ("Need Alt Estimate") in
any mode without manual throttle, GUIDED included. A single refused
update changes nothing, so a numerical glitch cannot switch a lane or
trip a failsafe on its own (ARCH-5). The position and velocity timeouts
would need the same treatment (`posRetryTimeUseVel_ms` 10 s,
`posRetryTimeNoVel_ms` 7 s).

None of our open PRs addresses it (all 113 diffs searched 2026-10-26 for
`FinishFusion`, `getFilterFaults`, `faultStatus`, the pass timestamps and
covariance resets). Closest, and why not:

- #32768's arming `resetHeightDatum()` zeroes the lane's height but moves
  the origin by the same amount, so the absolute error is kept, and it
  leaves the covariance alone.
- #27283 and #34456 switch lanes on a lane that looks unhealthy; this
  one never does.
- #34851 adds `lastRngHgtPassTime_ms` at the same point and shares the
  blind spot; it would move with any fix (noted in `../34851/README.md`).

## If we pick it up

1. Reproduce first: the issue's injected covariance in a SITL autotest
   (needs a test hook to write `P`), arm in GUIDED, switch lanes, and
   show the height and home errors on master.
2. Move the pass-time stamps after a successful `FinishFusion()` for the
   height, position and velocity observations, in EKF3 (and decide on
   EKF2, where the crash flew).
3. A/B: the test fails on master and passes with the change; the height
   timeout and `ResetHeight()` must be shown firing, not assumed.
4. Check what else reads the pass times (timeouts, `hgtTimeout` users,
   pre-arm, lane error scores) before changing when they are stamped
   (ARCH-1).
5. Ask the reporter whether exporting the fault bits is still wanted on
   top, and whether the patch zip's numbers came from the same repro.
