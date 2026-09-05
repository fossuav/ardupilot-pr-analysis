# PR #32473 - inhibit accel bias learning during acro flight (Copter / EKF3)

Analysis archive for [ArduPilot/ardupilot#32473](https://github.com/ArduPilot/ardupilot/pull/32473).
Branch `pr-acro-bias-inhibit` (andyp1per fork), base `master`, so the diff
contains all of #32471 as well. No logs of its own; the numbers below are from
[#32471's SITL A/B](../32471/README.md) of 2026-09-04, which measures the same
gates.

> **Read this before changing the code.** This branch once carried a change
> #32471 measured and dropped. It is gone as of 2026-09-05, but the argument for
> it is good enough that it has come back twice, so the section recording why it
> is wrong stays: see "The commit that must not survive".

## Status (one line)

Open, review required. One commit of its own on top of `pr-vrf-core` as of
2026-09-05 (`39c0642ed7`), touching only `ArduCopter/Attitude.cpp`. The headline
inhibit is still ungated by any parameter, which is the live objection.

## The problem

Acro sustains rates and accelerations where the accel bias is poorly observable,
so the EKF learning it there moves the bias the wrong way. The PR routes a
vehicle-set inhibit into the accel-bias Kalman gains.

## The commit that must not survive (gone 2026-09-05, kept because it recurs)

**Resolved.** `merge-base --is-ancestor 361da5d064 pr-acro-bias-inhibit` says
no, and the four gates in the branch's own tree read
`accelBiasLearningInhibited()`, which is the good state - `cb5026417f`'s entire
effect is to make them `inhibitDelVelBiasStates`. The commit object still
exists but no branch reaches it. This file claimed otherwise until 2026-09-05,
which was worth catching: a reader acting on it would have gone looking for
something that was not there.

The rest of this section stays, because the argument for the change is strong
enough to have been re-derived from the source twice. There is now also a
better answer than a prohibition: `9b852c9464` on `pr-vrf-core` addresses the
same covariance collapse by re-initialising P[13..15] once on the falling edge
of the inhibit, measuring 0.467 m to 0.284 m where `cb5026417f` measures
0.713/0.476 m and oscillates. Anyone reaching for `cb5026417f` wants that
instead.

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

A second arm agrees, measured 2026-09-04 on `pr-vrf-core`: with the change
applied, the shipped `AccelBiasMovingPlatform` autotest fails at 3.9 m against
its 2.5 m gate; without it the same test passes at 1.632 m. That is the cheapest
possible check on this commit - run `test.Copter.AccelBiasMovingPlatform`, no
harness or A/B logs needed. Because #32473 sits on top of `pr-vrf-core`, the
test is already present on this branch and `361da5d064` should make it fail.

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

## Rebased onto the reworked #32471, 2026-09-05

Replayed with `--onto pr-vrf-core cab18be57b`, which drops `cab18be57b`
*"AP_NavEKF3: narrow the Z accel-bias inhibit to a baro in ground effect"*.
That commit narrowed a gate #32471 no longer has: the gate was cherry-picked
into `pr-vrf-core`, held behind the feature flag, then removed outright once
present-against-removed measured 1 to 2 mm. Carrying it here would have
reintroduced a gate measured inert.

`1cb76ce055` replayed unchanged as `39c0642ed7` - only the blob hashes and line
offsets differ. It touches `ArduCopter/Attitude.cpp` alone, and
`update_accel_bias_inhibit()` was byte-identical on both sides.

One interaction worth noting rather than a conflict: this commit makes the
vehicle write the inhibit as a *level* every second, and #32471 now writes the
DAL event only on change, so repeated identical writes cost nothing. The
`arm()` call that clears the flag is left in place and is now redundant, since
`update_accel_bias_inhibit()` writes false while armed and out of acro.

`AccelBiasMovingPlatform`, `VibrationRectificationBiasLearning`, `Replay` and
the four EK3 accel-bias tests pass on the rebased branch. The acro path itself
is still untested, as below.

## Branches and people

- `pr-acro-bias-inhibit` - depends on `pr-vrf-core` (#32471), `39c0642ed7` as
  of 2026-09-05.
- Author: @andyp1per.
- peterbarker, 2026-07-17: this revisits #20776, which was deliberately reduced
  to #20781. Answered in prose ("insufficient"), not in code.
