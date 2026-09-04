# PR #32473 - inhibit accel bias learning during acro flight (Copter / EKF3)

Analysis archive for [ArduPilot/ardupilot#32473](https://github.com/ArduPilot/ardupilot/pull/32473).
Branch `pr-acro-bias-inhibit` (andyp1per fork), base `master`, so the diff
contains all of #32471 as well. No logs of its own; the numbers below are from
[#32471's SITL A/B](../32471/README.md) of 2026-09-04, which measures the same
gates.

> **Read this before changing the code.** This branch still carries a change
> that #32471 measured and dropped. See "The commit that must not survive".

## Status (one line)

Open, review required. Three commits of its own on top of `pr-vrf-core`; one of
them reinstates a change measured worse by 0.27 m, and the headline inhibit is
ungated by any parameter.

## The problem

Acro sustains rates and accelerations where the accel bias is poorly observable,
so the EKF learning it there moves the bias the wrong way. The PR routes a
vehicle-set inhibit into the accel-bias Kalman gains.

## The commit that must not survive

`361da5d064` *"AP_NavEKF3: keep accel-bias covariance alive while learning is
inhibited"* is `cb5026417f` under another name: it routes four
`CovariancePrediction` / `ConstrainVariances` gates off
`accelBiasLearningInhibited()` onto `inhibitDelVelBiasStates`.

Measured in [#32471](../32471/README.md), `ACC_ZBIAS_LEARN=6` with VRF present:

| | height error | `XKF2.AZ` range |
|---|---|---|
| with the change | 0.713 / 0.476 m | 0.46 |
| without it | **0.448 m** | **0.01** |

`=2` is unchanged at 0.196 m either way, so the revert is a no-op whenever the
vehicle flag is clear. Freezing P instead is worse still at 0.905/0.882 m.

The reason it keeps coming back is that the code argument for it is good:
`ConstrainVariances` calls `zeroStatesVarCov(13,15)` every cycle while the
inhibit is held, and `Kfusion[i] = P[i][stateIndex]*SK` reads exactly those
cross-covariances, so the gains really are zero when learning re-enables. The
mechanism is real and the change is still worse - the cost is that P[15][15]
inflates across the disarmed period and the state is released into the takeoff
transient. A 2026-09-04 `/pr-review` derived this argument from the source,
believed it, and had to be told by the A/B. Do not re-derive it; re-run
`../32471/data/ab-2026-09-04/harness.py`.

## Open

**The acro inhibit is ungated.** `Copter::update_accel_bias_inhibit()` asserts it
whenever the mode is ACRO and the spool state is `THROTTLE_UNLIMITED` - the whole
powered segment, not just high-G. On stock parameters every acro flight now
freezes all three accel-bias states, including a straight-and-level acro cruise
with good GPS where the bias is strongly observable. No A/B, no autotest, and no
log field records the flag. Owner decided 2026-09-04 to leave it and argue it on
the PR; it is the finding peterbarker's standing objection bears on most
directly.

**Nothing tests the acro path.** `AccelBiasMovingPlatform` covers
`ACC_ZBIAS_LEARN` bit 2 but never enters ACRO, so the branch's headline change
is source-traced only.

## Review history

2026-09-04 `/pr-review` of the 22-commit diff: 8 must-fix, 14 should-fix. The
findings belonging to these three commits were fixed; those belonging to the
#32471 commits underneath were fixed on that branch instead. Of the fixes made
here, one - `361da5d064` - was kept and its commit message *strengthened* before
the analysis notes were consulted. That is the mistake this file exists to stop
repeating.

Also fixed here: the `learnZBias` gate introduced by
`AP_NavEKF3: learn Z accel-bias by observability not ground effect` was
regressing EXTNAV and BEACON height sources (its `switch` had `default: false`,
and `activeHgtSource` can legitimately be either), and its RANGEFINDER and GPS
legs were tautologies because `selectHeightForFusion()` has already failed those
over to baro before `FuseVelPosNED()` runs. Narrowed to the one case that is
actually corrupt: the height observation, on baro, in ground effect.

## Branches and people

- `pr-acro-bias-inhibit` - depends on `pr-vrf-core` (#32471).
- Author: @andyp1per.
- peterbarker, 2026-07-17: this revisits #20776, which was deliberately reduced
  to #20781. Answered in prose ("insufficient"), not in code.
