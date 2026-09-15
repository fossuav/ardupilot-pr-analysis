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

Open, REQUEST CHANGES from the 2026-09-12 automated review. Local head
`7d2bc5ae9d` (2026-09-15, not pushed) adds a test that enters ACRO and a comment
fix on top of `39c0642ed7`. SITL shows the ungated inhibit trades acro height
error for post-acro height error and costs 1.0 m on a take-off in acro, so
gating it is the open decision.

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

### Superseded 2026-09-15 by the SITL A/B and the new autotest

`AccelBiasLearningInhibitedInAcro` (`7d2bc5ae9d`) now enters ACRO, and the A/B
in "Automated review round, and the acro inhibit measured" below replaces "No
A/B". The two paragraphs above are left as the state of 2026-09-05. The
ungated inhibit is still open.

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

## Automated review round, and the acro inhibit measured (2026-09-15)

The 2026-09-12 dev-call review at `39c0642ed7` returned REQUEST CHANGES.
Its acro findings were measured in SITL on 2026-09-15 rather than argued.
Everything in this section is tier 2 (SITL), one run per cell unless marked,
taken on `39c0642ed7` plus a local-only probe that selects the vehicle
behaviour from an environment variable: no acro inhibit, the PR's XYZ
inhibit, or a Z-only inhibit built on the existing per-axis
`dvelBiasAxisInhibit[2]` save and restore. The probe is
`data/acro-ab-2026-09-15/probe_variants.diff`; it is not on any pushed branch.

### No flight record behind the acro inhibit

Searched `../analysis`, `../analysis-private` and the auto-acro journal on
2026-09-15. Nothing measures accel-bias learning in acro, with or without the
inhibit. The one aerobatic bias observation is an auto-acro flight flown in
GUIDED, where this inhibit does not apply: 7.5 g peaks through a 15.5 g
clipping IMU, and `XKF2.AZ` walking -0.02 to -0.11 m/s/s across the flight.
The 2022 predecessor #20776 carried no numbers either. So the premise in the
commit message, that learning in acro "moves the bias the wrong way", is
inspection only.

**Owed:** SFD-O4 log7 (see `../../analysis/logs/log7_sfdo4.md`) flew 134 s of
ACRO on `SmallFastDrone-4.7.1-beta`, which carries this inhibit, with
`LOG_REPLAY=1`. Replaying it with the inhibit events suppressed would give the
first tier-1b answer. Its log root was not mounted on this machine on
2026-09-15.

### The rig

`AcroBiasProbe` (probe only, `probe_autotest.diff`): LOITER to 40 m, 30 s
hover, then 60 s of acro flown by an in-SITL Lua driver, then 40 s of
ALT_HOLD. The driver alternates roll and pitch flips closed on integrated
gyro (330 deg each, up to 370 deg/s) with 1 s full-throttle punch-outs, and
holds 30-46 m with a throttle loop; peaks reach 2.5 g. A first attempt timed
the flips from the harness at speedup 8 and crashed the vehicle, so the flips
have to be closed inside SITL.

Height error is |`XKF1.PD` - `SIM2.PD`| referenced to the pre-acro hover.
IMU errors are injected on both IMUs: none; 3% scale on every axis
(`SIM_ACCn_SCAL_*` 1.03); a 5 cm lever arm (`SIM_IMU_POS` 0.05 on each
axis); a motors-on offset (`SIM_ACC_VRF_Z` 0.15). "Bias moved" is the
largest |`XKF2` - pre-acro value| during acro, X/Y/Z in m/s/s, logged at
0.01 resolution. Height errors are mean / max in metres.

| IMU error | acro inhibit | bias moved | in acro | exit 0-10 s | exit 10-35 s |
|---|---|---|---|---|---|
| none | off | .03/.05/.01 | 0.06/0.20 | 0.03/0.08 | 0.00/0.02 |
| none | XYZ (PR) | 0/0/0 | 0.08/0.22 | 0.03/0.09 | 0.01/0.01 |
| none | Z only | .03/.04/0 | 0.06/0.16 | 0.02/0.06 | 0.00/0.02 |
| 3% scale | off | .05/.06/.06 | 0.26/0.62 | 0.21/0.36 | 0.21/0.36 |
| 3% scale | XYZ (PR) | 0/0/0 | 0.61/0.87 | 0.30/0.85 | 0.07/0.11 |
| 3% scale | Z only | .09/.13/0 | 0.44/0.75 | 0.25/0.55 | 0.01/0.02 |
| 5 cm lever | off | .01/.04/.03 | 0.08/0.30 | 0.08/0.18 | 0.13/0.20 |
| 5 cm lever | XYZ (PR) | 0/0/0 | 0.22/0.47 | 0.09/0.21 | 0.02/0.03 |
| 5 cm lever | Z only | .03/.02/0 | 0.17/0.38 | 0.03/0.07 | 0.01/0.02 |
| VRF 0.15 | off | .01/.02/0 | 0.06/0.24 | 0.02/0.05 | 0.01/0.03 |
| VRF 0.15 | XYZ (PR) | 0/0/0 | 0.07/0.23 | 0.04/0.08 | 0.01/0.01 |
| VRF 0.15 | Z only | .02/.04/0 | 0.06/0.21 | 0.01/0.02 | 0.01/0.02 |

The same VRF offset with the vehicle armed and taken off in ACRO, so the
inhibit engages on the ground at spool-up, 75 s of acro. Off and XYZ were
each run twice and agreed to 0.04 m; the second run is in brackets.

| acro inhibit | Z bias through acro | height error in acro |
|---|---|---|
| off | learns 0.12 of 0.15 | 0.20 / 0.59 m (0.18 / 0.63) |
| XYZ (PR) | held at -0.01 | **1.01 / 1.30 m** (1.03 / 1.34) |
| Z only | held; X/Y absorb 0.16 / 0.24 | 0.76 / 1.07 m, roll error 1.0 deg mean |

What the two tables say:

- SITL does not reproduce the premise at any size worth freezing for. 370
  deg/s flips at 2.5 g moved the uninhibited bias by 0.06 m/s/s at most.
  SITL does not model clipping, which is the aerobatic failure the flight
  record does show, so this fails to support the premise for real acro; it
  does not refute it.
- The inhibit trades height error in acro for height error afterwards. With a
  scale or lever-arm error the uninhibited filter tracks the acro-effective
  bias and is better in acro (0.26 vs 0.61 m, 0.08 vs 0.22 m), then carries
  it out and is worse 10-35 s after (0.21 vs 0.07 m, 0.13 vs 0.02 m).
- Review finding (c) holds, and is larger than its 0.6-0.7 m estimate, but
  only for a take-off in acro. Entered from a hover, the climb had already
  learned 0.13 of the 0.15 and the cost is gone (0.07 vs 0.06 m).
- Z-only is not the compromise it looks like. With Z held, the flips push the
  error into X and Y: 0.16 / 0.24 m/s/s and 1.0 deg of mean roll error in the
  take-off case, 0.09 / 0.13 m/s/s with the scale error.

### The release transient, review finding (d)

`AccelBiasLearningInhibitedInAcro` (`7d2bc5ae9d`) steps a 0.5 m/s/s Z bias in
3 s into a 20 s acro segment, then goes to ALT_HOLD. Same flight on three
probe builds, 2026-09-15:

| build | `XKF2.AZ` after exit | height error at exit | altitude lost in 20 s ALT_HOLD |
|---|---|---|---|
| XYZ inhibit, P restored on release (`9b852c9464`) | **1.00 peak at +2.0 s**, within 0.05 of 0.5 by +12.6 s | 5.68 m | **8.0 m** |
| XYZ inhibit, restore skipped | 0.41 by +18.9 s | 5.69 m | 6.0 m |
| no acro inhibit | 0.29 at exit, 0.42 by +18 s | 2.30 m | 1.5 m |

The restore overshoots a 0.5 step by 2x and costs 2 m more altitude than
leaving the collapsed covariance to regrow; skipping it makes re-acquisition
slow instead. The take-off-in-acro VRF run shows the same shape, `XKF2.AZ`
0.00 to 0.27 at +3 s against 0.15 true, settling to 0.15 by +15 s. The
restore is #32471's `9b852c9464`, measured there as an improvement for the
bit 2 arm transient (0.467 to 0.284 m). Acro makes it fire on every acro exit,
with whatever innovation the acro segment accumulated.

### The review's findings at `39c0642ed7`

| finding | disposition |
|---|---|
| (a) acro inhibit not behind `ACC_ZBIAS_LEARN` | open, the owner's decision; numbers above |
| (b) XYZ frozen in flight, per-axis logic skipped | correct, derived from the source and not measured: `accelBiasLearningInhibited()` skips the whole observability block in `CovariancePrediction()`. The Z-only alternative measured worse, above |
| (c) ~0.6 m from the frozen VRF value | confirmed for a take-off in acro at 1.01 / 1.30 m; absent when acro is entered from a hover |
| (d) restore 3.7x looser than natural growth | confirmed as a 2x overshoot and 8.0 vs 6.0 m of altitude; the restore is #32471's |
| (e) no test enters ACRO | fixed, `7d2bc5ae9d`; fails at 0.30 m/s/s with the acro condition removed |
| (f) "sole writer" comment false | fixed, `d5bc764af9`; its self-heal clause described no real path either |
| (g) `RISJ` comment | #32471's line, not this commit's |
| (h) description stale | replacement drafted, not yet posted |

Tests at `7d2bc5ae9d`, 2026-09-15: `AccelBiasLearningInhibitedInAcro`,
`VibrationRectificationBiasLearning` and `AccelBiasMovingPlatform` pass;
copter and plane build.

### Reproduce

Apply both diffs in `data/acro-ab-2026-09-15/` to `39c0642ed7`, build copter,
then `run_probe.sh <cond>:<variant>:<pre-hover s>` with cond one of `clean`,
`scale`, `lever`, `vrf`, and variant 0 (off), 1 (XYZ), 2 (Z only), 3 (XYZ
without the release restore). `PROBE_ACRO_TAKEOFF=1` takes off in ACRO.
`analyse_probe.py` and `analyse_test.py` print the table rows. The gzipped
logs are the take-off-in-acro pair and the three release-transient flights.

## Branches and people

- `pr-acro-bias-inhibit` - depends on `pr-vrf-core` (#32471), `39c0642ed7` as
  of 2026-09-05 on the fork; local `7d2bc5ae9d` as of 2026-09-15, unpushed,
  and must be restacked onto #32471's Replay de-dup fix when that lands.
- Author: @andyp1per.
- peterbarker, 2026-07-17: this revisits #20776, which was deliberately reduced
  to #20781. Answered in prose ("insufficient"), not in code.
