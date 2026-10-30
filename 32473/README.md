# PR #32473 - inhibit accel bias learning during acro flight (Copter / EKF3)

Analysis archive for [ArduPilot/ardupilot#32473](https://github.com/ArduPilot/ardupilot/pull/32473).
Branch `pr-acro-bias-inhibit` (andyp1per fork), base `master`, so the diff
contains all of #32471 as well. Head `1be046f169` (2026-09-30), two commits
directly on #32471's `b8ad09e9cb`; previous heads `dbf7c6ed12`, `59c2705a71`. No logs of its own; the numbers below are from
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

### Superseded 2026-09-15 (later) by the gating decision

Decided: the acro inhibit goes behind `ACC_ZBIAS_LEARN` bit 3, off by default,
holding all three axes. Pushed 2026-09-15 as `pr-acro-bias-inhibit` head `fc67be977d`,
restacked onto #32471 as pushed (`bb0a818b52`). See "Gated behind
ACC_ZBIAS_LEARN bit 3" below. The line above is left because it records what
the decision was made on.

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

## Gated behind ACC_ZBIAS_LEARN bit 3 (2026-09-15)

The user's decision after the A/B above: opt-in, default off, all three axes.
No SFD or other parameter file sets the bit.

Branch `pr-acro-bias-inhibit-restacked`, built by cherry-pick onto #32471's
pushed head `bb0a818b52` so `pr-acro-bias-inhibit` (`7d2bc5ae9d`) is left as
it was:

| commit | what |
|---|---|
| `66efdd6102` | Copter: add ACC_ZBIAS_LEARN bit 3 to inhibit accel bias learning in acro |
| `fc67be977d` | autotest: check ACC_ZBIAS_LEARN bit 3 holds accel bias learning in acro |

`66efdd6102` folds `39c0642ed7`, the comment fix `d5bc764af9` and the gate into
one commit, so no commit on the branch ships an ungated inhibit. The gate is
`AccZBiasLearn::INHIBIT_ACRO` (`ArduCopter/Attitude.cpp:172`) and
`acro_hold = inhibit_acro && ACRO && THROTTLE_UNLIMITED` in
`update_accel_bias_inhibit()` (`Attitude.cpp:269-276`); `ACC_ZBIAS_LEARN`'s
@Description and @Bitmask gain bit 3 (`ArduCopter/Parameters.cpp:1076-1077`).
The enum and the parameter docs are the only two places bits 0-2 were
described, and both carry bit 3. `@RebootRequired: True` is unchanged although
bit 3, like bit 2, is read live at 1 Hz.

`fc67be977d` makes the test revert-sensitive in both directions with one
flight and two acro segments: bit 3 set and a +0.5 m/s/s Z bias step 3 s into
acro, 20 s in ALT_HOLD, then bit 3 cleared and the step removed 3 s into a
second acro segment. SITL, 2026-09-15, `XKF2.AZ` core 0:

| build | acro, bit set | ALT_HOLD after | acro, bit clear | result |
|---|---|---|---|---|
| `fc67be977d` | 0.000 | 1.010 | 0.330 | pass (twice, identical) |
| inhibit forced on regardless of the bit | 0.000 | 1.010 | **0.000** | fails on the bit-clear leg |
| acro inhibit removed | **0.300** | 0.440 | 0.280 | fails on the bit-set leg |

Thresholds: bit-set leg under 0.05, the ALT_HOLD check at least half the step,
bit-clear leg at least 0.15 (the uninhibited readings are 0.28-0.33). The
1.010 after the first exit is the #32471 release restore overshooting the
0.5 step, the same transient as finding (d) above; the check only needs it
to have learned.

Also at `fc67be977d`: `VibrationRectificationBiasLearning` and
`AccelBiasMovingPlatform` pass; copter and plane build; the mechanical gate
reports only two subject-length notes on #32471's own commits.

A note on "Z only measured worse", which is how this decision was summarised.
On the height metric Z-only is not worse: in every row of the acro table it
is at or below XYZ (0.44 against 0.61 m in acro with the scale error, 0.76
against 1.01 m on the take-off in acro). What it costs is X/Y bias (0.16 /
0.24 m/s/s on that take-off) and 1.0 deg of mean roll error. Holding all three
axes was chosen on that attitude cost, not on height.

### Pushed, retitled and answered (2026-09-15)

Force-pushed `39c0642ed7` -> `fc67be977d` (33 commits: #32471's 31, then
`66efdd6102` and `fc67be977d`). The PR is retitled to the commit subject,
"Copter: add ACC_ZBIAS_LEARN bit 3 to inhibit accel bias learning in acro",
and its body rewritten: opt-in design, the SITL trade-off table, why all three
axes are held (attitude, not height), the dropped covariance commit, and the
open items. Reply to the 2026-09-12 automated review posted 12:34Z
(https://github.com/ArduPilot/ardupilot/pull/32473#issuecomment-5680233979).
`AIReview` was already on, so the 2026-09-12 round is stale from the push.

Still open: flight evidence for enabling bit 3 (the log7 Replay above is
owed), and the release-restore transient, being re-measured on #32471 with
repeated runs.

### The release restore, A/B'd on #32471 (2026-09-15)

See `../32471/`, "The release restore, A/B'd". Repeated SITL runs (3 per
cell) keep #32471's restore as pushed: after an acro exit it gives the lowest
sustained height error at every bias step (0.33 m mean 10-35 s after the exit
at 0.50 m/s/s, against 1.78 m without the restore). The single-run "8.0 m
against 6.0 m" in finding (d) above was mostly the vehicle following the
corrected estimate down: the EKF was 4.7 m low at the release. Superseded by
that A/B for the restore question.

It weighs against enabling bit 3, not against the restore: with no acro
inhibit, the in-flight bias step leaves 2.4x less height error at the exit
(1.98 against 4.70 m at 0.50 m/s/s). A bias that changes during acro is the
case where holding learning costs most. Consistent with bit 3 staying off by
default.

### Superseded 2026-10-29 for the acro exit

A flight (below, "2026-10-29") left acro carrying a vertical velocity error,
and the restore learned it as -0.8 m/s/s of bias within a second; altitude
hold then climbed the vehicle with the stick down. The A/B above injected
a bias step in acro, the one case where the error at the exit is a bias. The
restore now runs only for a hold that was disarmed at some point, so S1 above
is unchanged and S2's V2 row is what an acro exit now does. The numbers above
are left as measured: they are the cost of the change.

## Branches and people

- `pr-acro-bias-inhibit` - depends on `pr-vrf-core` (#32471), `39c0642ed7` as
  of 2026-09-05 on the fork; local `7d2bc5ae9d` as of 2026-09-15, unpushed,
  and must be restacked onto #32471's Replay de-dup fix when that lands.
  Restacked 2026-09-15 as local `pr-acro-bias-inhibit-restacked`
  (`fc67be977d`, on #32471's `bb0a818b52`) and force-pushed over the fork
  branch the same day; the local restacked branch was then removed.
  `59c2705a71` 2026-09-17; `dbf7c6ed12` 2026-09-29, restacked on #32471's
  `c9f68beab8`.
- Author: @andyp1per.
- peterbarker, 2026-07-17: this revisits #20776, which was deliberately reduced
  to #20781. Answered in prose ("insufficient"), not in code.

Result posted on the PR 2026-09-15 13:34Z
(https://github.com/ArduPilot/ardupilot/pull/32473#issuecomment-5681061008),
and the body's "Still open" bullet on the restore replaced with the repeated
numbers, including that no acro inhibit is better at the exit (1.98 against
4.70 m) and worse afterwards (1.13 against 0.33 m).

## Review round of 2026-09-15 13:52Z: throttle cuts and flips released the inhibit (2026-09-17)

The round found the acro condition keyed on THROTTLE_UNLIMITED: without air
mode a 400 ms throttle cut makes acro request ground idle in the air, so the
1 Hz writer released and re-set the inhibit, and each release fired #32471's
covariance restore.

Measured in SITL (LOG_REPLAY on to see the DAL events), bit 3 set, 0.5 m/s/s
Z step, then three 1 s throttle cuts each followed by a climb to arrest the
descent:

| gate | REV3 events in the acro segment | XKF2.AZ movement |
|---|---|---|
| spool state (`fc67be977d`) | SET, then UNSET/SET at every cut | 0.58 m/s/s (test fails) |
| armed and not landed | SET, UNSET on leaving acro | 0.00 (test passes) |

A first attempt with six 0.9 s cuts and hover throttle between them put the
vehicle from 40 m into the ground: the harness ran the cut for about 1.5 s of
sim time and hover throttle could not arrest 13.6 m/s. Hence the climb after
each cut.

FLIP started from acro: before, UNSET on entering FLIP and SET on the return
to ACRO; with `mode_flip.orig_mode_number() == ACRO` included, the inhibit
holds through and XKF2.AZ moved 0.000 across the flip (probe only, not in
the test).

Parameter text: the "learns in flight regardless" sentence qualified for bit
3, a note that bits 0-1 need a reboot and bits 2-3 are live, and a line that
taking off in acro with bit 3 holds the ground-learned bias.

Commits on `pr-acro-bias-inhibit` (local): `6493b6c6aa` (Copter gate, flip,
param text), `603dc42be1` (test). Restacked as local
`pr-acro-bias-inhibit-restacked` on #32471's `7a61baa62e`: `5f9f8f9a60`
(bit 3 commit with the gate fix folded in) and `59c2705a71` (test folded).
On it AccelBiasLearningInhibitedInAcro, VibrationRectificationBiasLearning
and AccelBiasMovingPlatform pass, copter and plane build, gate clean. Not
pushed. Reply and body update drafted.

### Pushed and answered (2026-09-17)

Force-pushed `fc67be977d` -> `59c2705a71`, restacked on #32471's
`7a61baa62e`: `5f9f8f9a60` (bit 3 with the armed-and-not-landed gate and the
flip hold folded in) and `59c2705a71` (throttle cuts in the test). The PR
body updated to "flying in acro, including through throttle cuts and flips
started from acro" and the test description. Reply posted 08:56Z
(https://github.com/ArduPilot/ardupilot/pull/32473#issuecomment-5711708890).

## 2026-09-22: the acro premise measured on a real flight

The live objection was that the inhibit is unevidenced - no flight measured bias
learning in acro. SFD-O4 log17 closes it: 258 s with 134.5 s of continuous ACRO,
flown with `ACC_ZBIAS_LEARN = 8` so the inhibit was held, then replayed twice
through the same tree with only `NavEKF3::getInhibitAccelBiasLearning()` patched
to return false. That removes the acro inhibit and leaves the geometric
`inhibitDelVelBiasStates` gate alone, so the arms differ in one thing.

`XKF2.AZ`, core 0, ACRO window taken from the flight's own MODE records:

| | mean | std | range |
|---|---|---|---|
| inhibit held, as flown | -0.0600 | 0.0005 | -0.070 to -0.060 |
| learning left on | -0.0315 | 0.0390 | -0.090 to **+0.030** |

Both arms are identical up to the acro entry (-0.0725, std 0.0043). With learning
on, the state ran 0.12 m/s2 and **changed sign** inside the first 20 s of acro,
then fell to -0.09; with the inhibit it sat on one logged level for 134 s.

**This corrects the PR's own SITL result**, which said the flips moved the bias by
at most 0.06 m/s2 and that "SITL does not show acro learning the bias the wrong
way". Real acro moved it twice as far and through zero. SITL was understating it.

Bounds on the claim: `XKF2.AZ` is logged at 0.01 m/s2, so 0.12 is 12 LSB (clear of
quantisation) but the held arm's 0.0005 std means "never moved a whole LSB", not
"constant". And a real flight has no truth reference, so the argument that the
excursion is wrong rests on its shape and timing.

`plots/acro_zbias_ab.png`, regenerated by `plots/make_plots.py`.

## Restacked on the rebased #32471 (2026-09-29)

Head `59c2705a71` -> `dbf7c6ed12`, still stacked directly on #32471, now
its `c9f68beab8` (rebased onto master `26c7363f64`). No change of its own
beyond the restack:

| was | now |
|---|---|
| `5f9f8f9a60` Copter: add ACC_ZBIAS_LEARN bit 3 ... | `fd6e38331f` |
| `59c2705a71` autotest: check ACC_ZBIAS_LEARN bit 3 ... | `dbf7c6ed12` |

What moved underneath, from `../32471/` "Rebased, and disarm no longer
writes back a stale bias":

- The release restore (`9b852c9464`, now `78326a5b3b`) writes `Pmut`
  instead of `P` after master made `P` const for writes. Same values, so
  the acro-exit numbers above still describe it, on the commits they were
  taken on. Derived from the source, not measured.
- Disarm saves the hover Z-bias only if learning ran since arming, and the
  learner is re-seeded on arm. Independent of bit 3.
- Open there and relevant here: bit 2's inhibit is asserted only from the
  1 Hz task. This branch's `update_accel_bias_inhibit()` is the same
  `one_hz_loop` writer, so the acro hold also starts and ends up to 1 s
  after entering or leaving ACRO. Derived from the source, not measured.

No tests were recorded as re-run on `dbf7c6ed12` itself for this update;
the 2026-09-17 results were taken on `59c2705a71`.

## Restacked on #32471's `b8ad09e9cb` (2026-09-30)

Head `dbf7c6ed12` -> `1be046f169`, force-pushed. Both commits
patch-identical (`git range-diff` `=`), no conflicts:

| was | now |
|---|---|
| `fd6e38331f` Copter: add ACC_ZBIAS_LEARN bit 3 ... | `6dcba24d89` |
| `dbf7c6ed12` autotest: check ACC_ZBIAS_LEARN bit 3 ... | `1be046f169` |

The base moved for #32471's 2026-09-30 round: AHRS now removes the
applied hover Z-bias, the covariance prediction takes it off `dvz`, and
two test fixes. None touches the bit-3 gate.

Re-run on `1be046f169` (SITL, tier 2): AccelBiasLearningInhibitedInAcro
and VibrationRectificationBiasLearning pass (hover PSCD.AD +0.011).
The acro A/B numbers above were taken on earlier heads and are not
re-measured; derived from the source, not measured, the base change
does not move them, since bit 3 gates learning and the AHRS change sits
outside the EKF.

The local `pr-acro-bias-inhibit` had been an older pre-restack line
(`12beaf9914`, 20 commits not on the PR); kept as branch
`old/pr-acro-bias-inhibit-local` in the ardupilot clone.

## Round of 2026-09-30 (AP-Review at 1be046f169), handled 2026-10-03

On local branch fix/32473 (not pushed), over head 82bd6cd00f.

The Replay blocker (the inhibit event dropped when the cores start before DAL
logging) was answered, not coded. AP_Logger::allow_start_ekf() holds the EKF
until logging only when LOG_REPLAY and logging while disarmed are both set,
and InitialiseFilter's DAL frame starts logging before the cores exist, so in
a replayable log the event is always written. Every scenario the review lists
(5 s start-wait timeout, watchdog reset, LOG_DISARMED=2 with USB, LOG_DISARMED
0) starts the log after the cores, without the InitialiseFilterEKF3 frame
Replay needs: measured (SITL, tier 2), a log started mid-session by setting
LOG_DISARMED at runtime replayed 0 EKF messages with and without a
pending-until-logging fix. That fix was written and dropped. Residual, not
specific to this PR: a REV3 write that fails is not retried.

Flip coverage added (SITL): three flips from ACRO in the first segment, the
MODE parser treating FLIP as part of the acro window, and a check that one
flip lasted at least 1 s (the inhibit runs at 1 Hz). Estimate moved 0.000
m/s/s with the hold, 0.14-0.23 with it removed (fails the 0.05 bound).

Comment fixes and the bit-3 commit message now cites the Replay A/B. Two
flake8 E131 registrations came from #32471's stack and fail flake8 there too;
fixed on fix/32471 (c8cd9431e6, b08d10b8d1). Rebase #32473 onto that and drop
its copies.

## Codex cold read of the ACRO inhibit (2026-10-03)

One finding, verified by reading: `acro_hold` requires `!ap.land_complete`,
which a mid-air disarm forces true. A re-arm in ACRO while falling therefore
releases the inhibit until the land detector sees throttle, plus up to 1 s
for the 1 Hz update, so learning can run during a 1-2 s fall. That is the
same order as the 1 Hz latency every mode change already has, and
`ap.disarmed_in_air` exists only on #32768's branch. Not changed; to be
stated as a known limitation if raised.

Pushed 2026-10-03: 82bd6cd00f -> adba7a0000 (force, restacked on 1f357b2429). a8267e13f1 reworded with the Replay A/B evidence (patch unchanged), 82bd6cd00f patch unchanged; new: flip-from-acro test, Copter comment, autotest comment/indent. AccelBiasLearningInhibitedInAcro, VibrationRectificationBiasLearning, AccelBiasMovingPlatform pass.
Reply posted 2026-10-03: https://github.com/ArduPilot/ardupilot/pull/32473#issuecomment-5973681037

## 2026-10-29: the release restore learned a velocity error as bias

Tier 1 and 1b. A T25 (MicoAir743v2, `REPLAY_INDEX` t25-308a-run,
2818322/45) on SFD `308a7e73`, `ACC_ZBIAS_LEARN` 10 (bit 3 from the SFD
defaults, plus bit 1), no GPS, `EK3_OPTIONS` 92 (AGL KF velocity fused as
velD). Times are `TimeUS` seconds.

- ACRO 92.6-108.3 s with the hold set. The EKF read a steady climb of +1.2 to
  1.9 m/s while the range finder held about 1.1 m: a velocity offset, not a
  growing error, left by earlier events in the boot (a switch disarm at 1.4 m
  that tumbled the vehicle, and a hand release that dropped 1 m and clipped
  the accelerometers on impact).
- VALT at 108.3 s. The 1 Hz writer released the inhibit at 109.0 s and the
  restore raised `XKV2.V15` from 5e-8 to 4e-6. At 110.0 s one AGL KF velD
  fusion (innovation -1.09 m/s, test ratio 0.92) moved `XKF2.AZ` from 0.10 to
  -0.70 m/s/s.
- The EKF then read a 1.4 m/s descent while the range finder showed a climb
  from 1.2 to 3.5 m with the stick fully down. Back to ACRO at 112.75 s, where
  the hold froze the bias at -0.82 and the EKF height ran to -37 m.

Replay through the flown build is bit-identical. With only the restore
removed, the replay matches the flight to 109.2 s and the bias goes 0.17 to
0.13 over the rest of the log; the fix below ported to the beta gives the
same, first deviation at 109.2 s. Removing the acro inhibit or the AGL KF
velD fusion instead also avoids the jump, but those replays depart earlier.
The flight is not a fault of #34933 (no refused fusion, P valid throughout).

Why the 2026-09-15 A/B did not see it: S2 stepped a bias in acro. The
2026-09-22 log17 replay above says real acro mis-learns the bias rather than
the bias really changing, so an inhibited acro exit is more likely to carry a
velocity error than a bias error. The covariance cannot tell them apart at
the release: the hold zeroed the bias cross-covariances, so the filter takes
the velocity as known and credits any innovation to a bias acting since.

SITL (tier 2), `AccelBiasAcroExitVelocityError`: LOITER hover at 40 m, ACRO,
`EK3_SRC1_VELZ` 0, +1.5 m/s/s on both IMUs for 0.5 s 3 s into acro, 3 s more
acro, ALT_HOLD:

| build | velD error at the exit | `XKF2.AZ` moved in the next 10 s | runs |
|---|---|---|---|
| `399a5f4a27`, restore as pushed | 1.21-1.25 m/s | 0.56-0.62 | 4 |
| with the fix | 1.21-1.26 m/s | 0.04 | 4 |

In the probe runs the restore's ALT_HOLD lost 7.6 m in about 5 s while the
EKF error swung from -3.4 to +1.7 m; without it the error decayed smoothly
and the vehicle descended 5.2 m over 14 s following the corrected estimate.

The fix, local and unpushed on `pr-acro-bias-inhibit`: `0d693fa234` with
fixup `57efcebaec` (EKF), `f622c86503` with fixup `956fd95d21` (test). The
restore now needs the hold to have been disarmed on some frame, including
the frame it ends on (`vehicleInhibitAccelBiasArmedOnly`). The arm release
of bit 2 and a disarm in acro restore as before; leaving acro, or landing in
it, keeps the floored variance. On #32471 alone every hold is disarmed, so
the change does nothing there; that is why it is this PR's commit.

Cost: an acro exit now behaves as V2 in the 2026-09-15 S2 table. With a real
0.15 m/s/s step in acro, mean height error 10-35 s after the exit 0.36 m
against 0.08 m; at 0.50, 1.78 against 0.33 m. `AccelBiasLearningInhibitedInAcro`
learns 0.42-0.43 of its 0.5 step after 20 s (passes at 0.25) where the restore
overshot to 1.00.

Codex cold read, one task per commit:

| finding | disposition |
|---|---|
| an armed hold suppresses the restore for good, so landing in acro carries a collapsed gain into the next take-off | refuted on the premise: the 5e-8 floor is above the converged value before acro (1.7-2.5e-8 in SITL, 6.2e-9 on the flight). A hold ending at a disarm now restores as before (fixup); deferring to the next disarm declined |
| the test's positive control checked height error, the mechanism needs velocity error | accepted: requires abs(`XKF1.VD` - `SIM2.VD`) at least 0.5 m/s at the exit |

At the fix tip: `AccelBiasAcroExitVelocityError` (twice),
`AccelBiasLearningInhibitedInAcro`, `AccelBiasMovingPlatform`,
`VibrationRectificationBiasLearning`, `EK3_AccelBiasInhibitOnGroundMoving`
and `Replay` pass; `EK3AccelBias` passed on the first version. With the EKF
commit reverted the final test fails (0.56). Mechanical gate clean.

Open: squash the fixups and correct the commit message numbers (needs a
rebase/amend grant), the PR description, the SFD beta port, and a replay of
SFD-O4 log17's acro exit (the fingerprinted copy is not on this machine).
The SFD defaults keep bit 3 on (`ACC_ZBIAS_LEARN` 8) for every SFD board.

Pushed 2026-10-29: `399a5f4a27` -> `b7c4f1601d` (fast-forward). The fixups
were squashed and both messages carry the final numbers: `6118e47b19` (EKF),
`b7c4f1601d` (test); the tree is identical to the tested fixup head
`956fd95d21`. Quick review recorded at `b7c4f1601d`: mechanical gate clean,
Codex cold read as above. PR description updated: the acro-exit change in the
summary, the new test and the flight replay under testing, and the stale
"no flight evidence" and "restore kept" open items replaced with the cost
above. No reply posted; `AIReview` is on, so the bot reviews the new head.
Still owed: the SFD beta port and the log17 replay.

SFD beta, 2026-10-29: carried as refresh11 topup4, pushed to
`SmallFastDrone-4.7.2-beta` at `6307d4d424` (`7ab6409ca3` EKF,
`0b0aafdec7` test). On the beta the new test fails without the EKF commit
(0.59 m/s/s) and passes with it (0.04, twice); the accel bias tests and
`Replay` pass. The T25 flight replayed through the beta build matches it to
109.2 s and the bias then holds at 0.13-0.17 m/s/s. SFD-O4 log56's acro exit
(264.8-304.4 s, into LOITER), replayed through the beta before and after:
the flow lane's bias went -0.10 to -0.50 m/s/s at 310 s and back by 316 s
without the change, and moves at most 0.06 with it; the GPS lane is within
0.05 either way. Still owed: the log17 replay.

## 2026-10-30: restacked on the AP_UInt8 fold, inhibit logged again on a log restart

AP-Review at `9396a8ee52` (COMMENT). One should-fix item: the logged
inhibit level is not reset when the DAL starts a new log. Not changed,
as the bot says no action is needed: the one-frame snapshot mismatch
with a Lua `arm()`.

### Restack

The four commits were cherry-picked onto #32471's folded head
`1c14ca0a3e`, where `ACC_ZBIAS_LEARN` is now `AP_UInt8`, and all four
are `=` in the range-diff (`range-diff.txt`; `range-diff-full.txt` has
all 46):

| was | now |
|---|---|
| `140916717d` Copter: bit 3 | `595fc7b301` |
| `c645bb59eb` autotest: bit 3 | `58a03779f5` |
| `f13f0d3dd4` AP_NavEKF3: armed hold keeps the variance | `5704841ad5` |
| `9396a8ee52` autotest: acro exit | `3665408206` |

Running `git diff 9396a8ee52 3665408206` shows only the type line. The
old head is kept as `r1030/32473-orig`.

### The log-restart gap, verified

The latch is #32471's (`b3d36ad887`). `_inhibitAccelBiasLearningLogged`
holds the level the DAL last accepted for the whole boot. When the
logger closes and reopens, the DAL sees the edge and force-writes its
own records, but the EKF still believes the level is in the log. So a
log that starts while bit 2 or bit 3 holds the inhibit gets no set
event. Reproduced in SITL with a LOG_ERASE while disarmed under bit 2:
the boot log has the set, and the restarted log has no REV3 at all.

### The fix

- `b6c2292cdd` AP_DAL: `is_logging()`, a read-only view of the
  `logging_started` state the DAL already keeps for its own force-write.
- `f5408912a2` AP_NavEKF3: while the DAL is not logging, set the latch
  to false. Replay starts every log with the inhibit clear, so a held
  level is sent again in the new log, and a clear level adds nothing to
  logs that never hold the inhibit, on any vehicle.
- `e7a1af6303` autotest: AccelBiasInhibitLoggedAfterLogRestart. Erase
  the logs while bit 2 holds the inhibit, wait for logging to restart,
  then wait for REV3 set in the new log. The erase takes about 58 s of
  sim time, because LOG_MAX_FILES defaults to 500 and one file goes per
  io tick. Lowering LOG_MAX_FILES was rejected: in a long CI run it
  would leave higher-numbered logs behind.

The set lands right after the restarted log's first DAL frame. That is
the same one-frame lateness as a late-started log, which the bot's
validation found harmless, since Replay's EKF is still bootstrapping.

In SITL, AccelBiasInhibitLoggedAfterLogRestart fails on the pre-fix head
binary (`3665408206`, md5 `b4b26a93`) with "accel bias inhibit never
reached logs/00000001.BIN", and passes with the fix. It is the same on
#32471 alone (see its notes).

Replay probe: erase the logs while disarmed under bit 2, then 60 s on a
platform accelerating at 1 m/s/s, then replay the restarted log:

| firmware | REV3 in restarted log | flight `XKF2.AZ` | Replay C100/C101 `AZ` |
|---|---|---|---|
| without the fix | 0 | 0.000 | -0.990 / -0.980 |
| with the fix | 1 (set) | 0.000 | 0.000 / 0.000 |

Not covered, derived from the source and not measured: LOG_REPLAY
turned on at runtime. With LOG_REPLAY 0, `WriteReplayBlock` reports
success without writing, so the latch takes the level. When LOG_REPLAY
is then set, `allow_start_ekf()` is already true for the running log,
so the DAL sees no new log. Its own records are not force-written
either, and that log cannot be replayed whatever this latch does.

Also visible to a reviewer: in Replay, AP_DAL_Standalone and
logging-disabled builds `is_logging()` is always false. So while the
inhibit is held, `log_event3()`, a no-op returning true in those builds,
is called on every frame. Replay output is unchanged: Replay passes.

### Runs

Tests at `82e59588c9`, whose tree is identical to `e7a1af6303` (only
the EKF commit message was reworded since), all passed:
AccelBiasInhibitLoggedAfterLogRestart, Replay (all bits, AccelBiasInhibit
included), AccelBiasMovingPlatform, VibrationRectificationBiasLearning,
AccelBiasLearningInhibitedInAcro, AccelBiasAcroExitVelocityError and
EK3_AccelBiasInhibitOnGroundMoving.

Builds pass, with no warnings:

- the CI replay job: replay with `--debug --disable-scripting`, then
  tool/AP_DAL_Standalone with `--no-gcs` added;
- the DAL-only commit, copter and replay.

Gate: three subject-length notes on older #32471 commits, and branch
conventions pass. Not pushed.

### Follow-up after the quick review

The top three commits were rebuilt by cherry-pick: `b6c2292cdd` ->
`b2dd7dd478`, `f5408912a2` -> `a047afa128`, `e7a1af6303` ->
`9b0b2e5138`. The tree differs from `e7a1af6303` only in the
`is_logging()` comment and the test.

- The messages now say the set is re-sent when the DAL itself sees
  logging start, which is when it writes its own records again. They
  also say it lands one frame after the restarted log's first DAL frame,
  harmless as for a late-started log. `AP_Logger::logging_started()` is
  true while any backend runs, so a file log that restarts while the
  MAVLink backend stays active is missed. The DAL's own records miss it
  too; one sentence says so.
- The test's two polls retry on `OSError` (log deleted after listing),
  `ValueError` (empty file) and `struct.error` (log ends inside a
  record) until their timeouts, and the REV3 poll reads one fixed path.
  SITL: it passes on the fixed binaries (`24e8e63d`, and `4380c96a` at
  `9b0b2e5138`), and still fails on the pre-fix `b4b26a93`, "accel bias
  inhibit never reached logs/00000001.BIN".
- Not catchable: pymavlink 2.4.49's fast indexer (`dfindexer_cy`) calls
  C `exit(1)`, printing "Invalid length in FMT message at N", when a
  log ends a few bytes into an FMT record. Over truncations of the first
  40 KB of a real log, the fast indexer raised `struct.error` on 128 of
  233 and exited on 1 (8192 bytes); the legacy indexer
  (`PYMAVLINK_FAST_INDEX=0`) neither raised nor exited on any. A poll
  that opens the restarted log while its FMT block is being flushed can
  therefore end the autotest process. This is rare, and any test that
  reads a log being written shares the risk, but it is most likely in
  the first second of a log, which is where this test reads. Fixing it
  belongs in pymavlink.

### The fix moved to #32471, and this branch restacked on it

Andy chose to carry the restarted-log fix on #32471, where the code it
fixes lives. There it is `feddc0eea2`, `3973add04c` and `d9e7d85f5c`.
This branch is now #32473's own four commits, cherry-picked onto that
head. The fix-on-top version is kept as `r1030/32473-fixontop`
(`9b0b2e5138`).

| was | now |
|---|---|
| `595fc7b301` Copter: bit 3 | `d3b5890246` |
| `58a03779f5` autotest: bit 3 | `115050a65d` |
| `5704841ad5` AP_NavEKF3: armed hold keeps the variance | `968ea7d7e5` |
| `3665408206` autotest: acro exit | `3ca94847db` |

The bit-3 test commit conflicted with the restart test in both the
method placement and the registration list. It was resolved in the
order `9b0b2e5138` had, so `git diff 9b0b2e5138 3ca94847db` is empty.
Range-diff against the original `9396a8ee52`
(`range-diff-restack2.txt`):

- 43 commits are `=`, and one is `!`: the AP_UInt8 fold.
- The three fix commits are new.
- The Copter and EKF commits are `=`.
- The two autotest commits are `!` in context only: the restart test
  now sits above them.

At `3ca94847db` (SITL): AccelBiasLearningInhibitedInAcro,
AccelBiasAcroExitVelocityError and AccelBiasInhibitLoggedAfterLogRestart
pass. Gate: the same three older subject-length notes, and branch
conventions pass. Not pushed.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `9396a8ee52`
-> `3ca94847db`.
