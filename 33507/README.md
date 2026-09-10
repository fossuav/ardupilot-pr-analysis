# PR #33507 - estimate the accel-Z bias inside the AGL KF (EKF3)

Analysis archive for [ArduPilot/ardupilot#33507](https://github.com/ArduPilot/ardupilot/pull/33507).
Branch `pr-agl-kf-zbias` (andyp1per fork), base `master`, head `0c429893cf`
(2026-07-27). Evidence is Replay on, and flights of, a 4-inch optical-flow quad
(MatekH743, ARK Flow, downward rangefinder), flights of a 5-inch baro-only
indoor quad, and Replay on a second flow-navigation airframe; numbers inline,
no logs committed.
Upstream logs the AGL KF as `XKFA`; the flights were on the SmallFastDrone
branch where it is `XKF6`.

## Status (one line)

The bias state is right; its process-noise default is not. Bias state
flight-validated; the decoupled process noise `EK3_AGL_ABIAS_P` (third
commit) was Replay-derived and then flight-confirmed, but the 0.05 default
that passes the autotest under-tracks thermal drift on two airframes
(0.1-0.3 flown; 0.3 flight-validated). The PR body and one code comment still
describe Qbias in terms of `EK3_ABIAS_P_NSE`, which the third commit replaced.

## Review 2026-09-10: the bias state absorbs climb rate, and this record's evidence for 0.3 does not isolate it

The estimator algebra is sound - `F*P*F'` re-derived by hand term by term,
the Joseph update is exact for `H = [1,0,0]` and reduces to the 2-state form
when the bias terms vanish, symmetry is maintained on both triangles, and
`[H; HF; HF^2]` has rank 3 so the bias is observable in principle (third
order in dt, i.e. only from a height ramp over seconds). Simulated at Q=0.05
in a static hover with a true 0.3 m/s2 accel error, `b` converges to 0.2997
in 120 s with `BiasStd` 0.0084, in line with the flight numbers below. The
881-commit lag is clean: `merge-tree` conflict-free and
`AP_NavEKF3_OptFlowFusion.cpp` is byte-identical between base and master.

Three things block it, and the first two are about this record as much as
the PR.

**1. `aglKfB` absorbs any sustained AGL rate at `w/tau`.** The tau = 2 s
decay of `aglKfV` is gated on `!rangeDataToFuse`, which is a *per-sample*
flag, not "the rangefinder is absent". With a healthy 10 Hz rangefinder on a
400 Hz filter it is false on ~39 of 40 steps, so the decay runs continuously
in normal flight. To hold `aglKfV = w` against it, the prediction must be
driven by `b`, so `b` settles at `w/tau_eff`. Simulated on the shipped
equations with **true accel bias exactly zero**, a constant 0.9 m/s climb
drives `aglKfB` to +0.438 after 60 s at every Q from 0.05 to 0.30 - that is
`0.9/2.051` to three figures, a property of the propagation, not the gains.
Terrain does it too: 5 m/s over a 10% slope gives about -0.24 m/s2. The
failure this creates is the one already noted here as "the re-acquisition
transient after a long dropout": the 5 s timeout reset restores `h` and
zeroes `v` but deliberately *preserves* `b`, so a preserved +0.44 re-drives
`v` toward +0.9 m/s of spurious climb in a hover, with only `P[2][2] = 1.0`
to relearn it. That is a modelling defect, not a tuning question. Fix by
gating the decay on a real dropout, or by folding it into `F` so the
covariance matches what the states do - either changes the answer to "what
should the default be", so it has to be settled first.

**2. The under-tracking evidence does not isolate the bias state.** Running
this record's own metric - regress AGL-KF height change on true height
change over 1-5 s baselines - against the shipped filter with **no true
accel bias and no thermal drift at all** (hover, +/-1 m climbs, 0.04 m range
noise) reproduces the flight signature:

| EK3_AGL_ABIAS_P | slope 1 s | corr | slope 5 s | final b |
|---|---|---|---|---|
| 0.05 | 0.803 | 0.954 | 0.804 | -0.011 |
| 0.30 | 0.967 | 0.982 | 0.967 | -0.010 |

against the flown 0.59-0.71 at 0.05 and 0.83-0.94 at 0.3. `b` sits at -0.01
in both - there is nothing for it to track. The mechanism is that Qbias
propagates `P[0][2] -> P[0][1] -> P[0][0]`, so raising it raises the
*height* gain: converged hover `hStd` 0.124 -> 0.156 m and `Kh` 0.058 ->
0.084 across 0.05 -> 0.30, 45% harder pull toward the rangefinder. So "0.3
measures better" is real; "because 0.05 under-tracks thermal drift" is not
what that metric shows, and this record states it as settled. Discriminating
test: hold Q at 0.05 and lower `EK3_RNG_M_NSE` (or raise `EK3_ACC_P_NSE`)
until `Kh` matches the Q=0.3 case, then re-run the regression. If the slope
recovers, the parameter is a proxy for the height gain and the fix belongs
elsewhere.

For balance, the bias state does do its job on a genuine drift. True accel
error ramping 0 -> 0.35 m/s2 over 200 s in a hover:

| Q | 0.05 | 0.10 | 0.20 | 0.30 | 0.50 |
|---|---|---|---|---|---|
| bias lag (m/s2) | 0.052 | 0.032 | 0.021 | 0.017 | 0.013 |
| residual v (m/s) | -0.067 | -0.039 | -0.023 | -0.018 | -0.012 |

A higher default helps the thermal case too. The point is only that the
published evidence does not separate the two effects.

**3. Shipping 0.05 is not defensible as the diff stands.** The whole feature
is behind `EK3_OPTIONS` bit 3 and `EK3_OPTIONS` defaults to 0, so this
parameter cannot affect a vehicle that has not opted in - and the people who
opt in are the ones this record says 0.05 fails (1.3 m drift against 0.3 m,
0.2 recovering the full 60% PD-drift reduction on log66, log311 monotonic to
0.3). Nothing in the PR pins 0.05 either: its autotest requires only
`bias_after - bias_before >= 0.1` against a 0.7 m/s2 injection, 14%
tracking, which cannot distinguish 0.05 from 0.3. The overshoot constraint
cited here belongs to #33478 - neither `EK3_AglKfVelForVelD` nor
`_aglKfVelMaxSpd` exists in this tree. Either ship 0.2-0.3, or ship 0.05 and
say in the commit message and the parameter doc what was flown and what
holds the default lower.

### Corrections to the commit messages and comments

- `8373f1da1b` says "XKF6 now logs the bias estimate" - upstream it is
  **XKFA**. Downstream name leaked into an upstream commit message.
- The same commit says "only the inactive-lane and frozen hover corrections
  are removed before it". `git grep accelBiasHoverZ` on the base returns
  nothing: **the frozen hover-Z correction does not exist upstream.** This is
  exactly the failure the EKF3 playbook warns about.
- That sentence also understates what *is* removed. `learnInactiveBiases()`
  assigns `inactiveBias[active].accel_bias = stateStruct.accel_bias` on
  every IMU frame, so `velDotNED.z` already has the main filter's own
  accel-Z bias estimate removed. `aglKfB` is the **residual error in state
  15**, not an independent estimate - which contradicts "independent of the
  main filter" in the commit message and in two code comments.
- `@Units: m/s/s` is wrong. `Qbias = sq(P * imuDt)` with `aglKfB` in m/s2
  makes `P` m/s3, the same as `EK3_ABIAS_P_NSE`, which is documented
  `@Units: m/s/s/s`. Same error on the member comment.
- Parameter index 14 is downstream numbering (13 is `FLOW_QMIN` and 15 is
  `AGL_VD_SPD` on the fork). Upstream `var_info2` uses 2-11, so 12 is free
  and should be taken - as with #33478's index 15, the gap is invisible to a
  maintainer.
- Stale comments: the `EK3_OPTIONS` `@Description` for bit 3 still says
  "2-state" (this one reaches the wiki), as do three headers; the `Qbias`
  block still names `EK3_ABIAS_P_NSE`; ":790 so the hard reset finds v near
  zero" is no longer true given finding 1; and the observation model comment
  still reads `H = [1, 0]`.
- The parameter doc's "only updates from clean rangefinder measurements, so
  a higher value here cannot learn a bad bias" overstates it. The only
  cleanliness test is a 5-sigma innovation gate against the filter's own
  variance. Stale data cannot move it; *wrong* data - a slope, a reflective
  floor, something moving under the vehicle - moves it faster at higher Q.

### Robustness items

- **Covariance loses positive-definiteness ~0.7 s before the validity
  timeout.** The three diagonals are clamped (100, 100, 25) while
  `P[0][1]`, `P[0][2]`, `P[1][2]` grow unbounded. Simulated from the
  post-reset covariance with the rangefinder absent, `P00` caps at t = 4.0 s
  and the smallest eigenvalue goes negative at **t = 4.26 s**, while
  `aglKfValid` holds until 5 s. Inside that window `getHAGL()` and the flow
  range scaling still consume the filter and a returning sample would be
  fused through a non-PD `P`. From a converged hover the crossing is at 40 s,
  so the exposure is specifically reset-then-dropout - an intermittent
  rangefinder over grass or water. Pre-existing in the 2-state block, but
  this PR extends the clamp pattern rather than fixing it and adds two more
  unbounded off-diagonals. Clamp each off-diagonal to
  `sqrt(P[i][i]*P[j][j])`, or rescale the row and column when a diagonal
  clips.
- `Qbias` is unconstrained where the main filter uses
  `constrain_ftype(..., 0.0, 1.0)`. `@Range` is not enforced at runtime, so
  `EK3_AGL_ABIAS_P = 100` drives `P[2][2]` to its cap in about a second.
- `aglKfB` has no magnitude limit, where the main filter clamps to
  `EK3_ACC_BIAS_LIM`. With finding 1 that is what lets a climb push it to
  half a metre per second squared.
- `aglKfValid` is never cleared on persistent innovation rejection - the
  clear is only reachable inside the `!rangeDataToFuse` branch. A rangefinder
  that keeps delivering rejected readings never invalidates the filter; the
  5 s timeout instead hard-resets `h` to the rejected reading. The PR now
  carries `aglKfB` through that path unchanged, so a bias learned on bad data
  survives every reset for the rest of the flight.
- Two paths step `velDotNED.z` by the full learned bias with no notification
  to the AGL KF: `stateStruct.accel_bias.zero()` in `ConstrainVariances`
  when the delta-velocity bias covariance falls below the safe minimum, and
  the lane-switch copy in `AP_NavEKF3_Measurements.cpp`. After either,
  `aglKfB` is wrong by the whole step and relearns at Q - tens of seconds at
  0.05. This is what LupusTheCanine's "a shared AccZ bias?" is really asking
  about, and it deserves a sentence in the PR body.
- It is a closed loop, not one-way: `aglKfH` -> flow range scaling ->
  `FuseOptFlow` -> main filter velocity -> state 15 -> `velDotNED` ->
  `aglKfB`. Low gain, but the body should not call the AGL KF decoupled
  without qualifying it.
- `SelectFlowFusion()` returns early when `magFusePerformed && dtIMUavg <
  0.005f`, so `UpdateAglKf()` and its `h += v*dt` are dropped on roughly 10%
  of steps at 400 Hz despite the "every IMU step" comment. Modelled, it moved
  the slope by only a few percent - well below the decay effect - but it
  means the filter's internal clock runs slow, which a bias state absorbs.
  UNCONFIRMED as a contributor.
- `Qbias = sq(P * imuDt)` is loop-rate dependent, matching house convention
  (`Qvel` and the main filter do the same) - but it means "0.3 was
  flight-validated" is validated at one airframe's filter rate.

### Autotest

- The `>= 0.1` threshold on a 0.7 m/s2 injection accepts 14% tracking. The
  simulation converges the bias fully within 30 s in a hover even at Q=0.05,
  so the assertion could be `> 0.45` and would then constrain something.
- It tests a **step**; the parameter exists for a **ramp**. A subtest that
  ramps `SIM_ACC1_BIAS_Z` over ~120 s and checks tracking lag is the test
  that would distinguish 0.05 from 0.3, and is the one this record says is
  missing.
- Nothing asserts `XKFA.Valid` stays 1 after the injection, or that the
  vehicle stays inside rangefinder range while an instantaneous 7%-of-g step
  disturbs the main filter's altitude in LOITER.
- Two consecutive identical `land_and_disarm()` calls at the end. Harmless,
  but it reads as an unrun edit.
- The first commit ASCII-ises pre-existing `^2` and em-dash characters in
  comments it does not otherwise touch - out of scope under the surgical
  modification rule, and it missed one.

## Fixed and pushed 2026-09-10: head 0c429893cf -> 2532ac916e

One code change, the rest comments and messages.

- `@Units` was `m/s/s`; the state is m/s/s so its process noise is m/s/s/s,
  which is what `EK3_ABIAS_P_NSE` already declares. Fixed in the parameter
  doc and the member comment. `param_parse.py --vehicle ArduCopter` runs
  clean and emits `m/s/s/s`.
- Parameter index 14 (downstream numbering) moved to **12**, the first free
  index upstream. Verified no collision in `var_info2`.
- Code: `Qbias` now uses `constrain_ftype(..., 0.0f, 1.0f)`, mirroring what
  the main filter applies to `_accelBiasProcessNoise`. `@Range` is not
  enforced at runtime, so before this a value of 100 drove `P[2][2]` to its
  cap in about a second. Builds clean (`./waf copter`).
- The first commit message said XKF6 (the fork's name); upstream it is
  **XKFA**. It also claimed a "frozen hover correction" is removed before
  `velDotNED.z` - that does not exist on the base - and called the estimate
  "independent of the main filter". All three corrected: the message now
  says what the state actually is, the residual left after
  `learnInactiveBiases()` and `correctDeltaVelocity()` have removed the main
  filter's own estimate every IMU frame.
- Stale "2-state" wording fixed in four places, including the `EK3_OPTIONS`
  bit 3 `@Description`, which reaches the wiki. Fixed the pre-existing
  en-dash on that same line while editing it.
- `Qbias = sq(EK3_ABIAS_P_NSE * imuDt)` in the header block now names
  `EK3_AGL_ABIAS_P`; the observation model comment now reads `H = [1, 0, 0]`;
  the decay comment no longer claims the hard reset finds v near zero, since
  the bias state sustains `b_az*tau` against it.
- The parameter description no longer claims a higher value "cannot learn a
  bad bias". Stale or absent range data cannot drive it; a sloping or
  reflective surface can, and faster at higher values.
- Removed the duplicated `land_and_disarm()` in the autotest.
- The commit message now states that 0.1-0.3 was flown and 0.3
  flight-validated, and that the step-injection autotest does not pin the
  default.

Still open, and deliberately not changed: the **default remains 0.05**, and
the two design findings above (the decay gated on a per-sample flag, and the
fact that the under-tracking evidence does not isolate the bias state) need
measurement before either the default or the decay is touched.

## SITL A/B 2026-09-10: both review findings confirmed, and 0.3 is the wrong lever

Two runs on the PR's own tree (head 2532ac916e), Copter SITL, optical-flow
hover with an analog rangefinder, `EK3_OPTIONS=8`, single lane, and
**`SIM_ACC1_BIAS_Z = 0` throughout** - there is no true accel bias anywhere
in either test, so every non-zero bias estimate below is the defect.

### A/B 1: aglKfB tracks climb rate, not accel bias

Steady climbs and descents at both process-noise values, bias averaged over
the last 12 s of each phase, climb rate by least squares on `XKFA.HAgl`:

| Q | phase | w (m/s) | aglKfB | predicted w/tau_eff |
|---|---|---|---|---|
| 0.05 | hover | +0.000 | -0.007 | +0.000 |
| 0.05 | climb | +0.377 | **+0.155** | +0.184 |
| 0.05 | descent | -0.412 | **-0.155** | -0.201 |
| 0.30 | hover | +0.005 | -0.002 | +0.003 |
| 0.30 | climb | +0.375 | **+0.169** | +0.183 |
| 0.30 | descent | -0.407 | **-0.181** | -0.199 |

The sign follows the climb direction, the magnitude scales with the rate,
and it is essentially independent of Q - +0.155 against +0.169 for a 6x
change in process noise. Hover returns it to zero every time. The measured
values sit 8-23% below the `w/tau_eff` prediction, which is expected: the
rangefinder correction partially opposes the drift the decay creates, so
`w/tau` is an upper bound rather than an equality. **Finding 1 confirmed.**

### A/B 2: the under-tracking slope is a height-gain effect

Same airframe, oscillating height (+/- ~2 m bobs on a 8 s cycle, 12 cycles
per arm) so the filter's 1.8 s time constant shows as attenuation. An
earlier run using sustained ramps gave slope ~1.0 in every arm and settled
nothing - on a ramp a constant lag does not attenuate a change-vs-change
slope. The stimulus has to oscillate, which is what the flights did.

Regress AGL-KF height change on true height change (`SIM.Alt`):

| arm | EK3_AGL_ABIAS_P | EK3_RNG_M_NSE | slope 1 s | 2 s | 5 s | HAglStd | mean bias |
|---|---|---|---|---|---|---|---|
| A | 0.05 | 0.5 | 0.747 | 0.710 | 0.712 | 0.117 | +0.010 |
| B | 0.30 | 0.5 | 0.907 | 0.870 | 0.875 | 0.142 | -0.005 |
| C | **0.05** | 0.15 | **0.955** | **0.917** | **0.921** | **0.046** | -0.003 |

Arm A reproduces the flight signature this record used to justify 0.3
(measured 0.59-0.71 at 0.05); arm B reproduces the improvement (0.83-0.94 at
0.3). Arm C holds Q at 0.05 and raises the height gain directly by lowering
the rangefinder noise instead - and **beats arm B**, at 2.5x lower reported
height uncertainty.

So the slope responds to the height gain, not to the bias state. Note also
that arm B *inflates* `HAglStd` (0.117 -> 0.142) while improving the slope,
exactly as Qbias propagating through `P[0][2] -> P[0][1] -> P[0][0]`
predicts, whereas arm C improves the slope and tightens the variance. And
the mean bias is ~0 in all three arms, because there is no bias to learn.
**Finding 2 confirmed: EK3_AGL_ABIAS_P is acting as a proxy for the height
gain in this evidence.**

### What this decides

- **Do not raise the default to 0.3 on the strength of the under-tracking
  numbers.** That evidence does not isolate the bias state, and the same
  improvement is available without touching the bias process noise.
- Arm C is a **diagnostic, not a recommendation**: the SITL rangefinder is
  nearly noise-free, so `EK3_RNG_M_NSE = 0.15` is free here and would be
  over-trusting on a real sensor.
- The decay gate (finding 1) has to be fixed before any default is chosen,
  because it is what couples the bias state to vertical motion.
- What is **not** settled: whether a higher default is needed to track
  genuine thermal drift. That argument is separate and still standing - the
  bias-lag table above shows Q does help a real ramp - and it needs its own
  test with a non-zero `SIM_ACC1_BIAS_Z` ramp. These two runs say only that
  the *published* justification is the wrong one.

## Fixes 2026-09-10 (head b1e8ecbcd8): the decay gate, and the default stays 0.05

The decay defect is fixed by carrying **#33478's `b04875313b`** rather than a
new commit - the same defect, the same fix, and the same
`aglKfRngGapMax_ms` name. Note the two branches will not auto-dedupe: the
patch-ids differ because the surrounding line is `aglKfV += (aglKfB -
velDotNED.z)*imuDt` here and `aglKfV -= velDotNED.z*imuDt` there, so whichever
rebases onto the other needs a manual resolution or a skip. The clean
upstream answer is to split it into its own small PR that both depend on;
that is a call, not something done here.

Measured after the fix, same runs as before:

| | before | after |
|---|---|---|
| aglKfB, 0.38 m/s climb, Q=0.05 | +0.155 | **+0.0002** |
| aglKfB, 0.41 m/s descent, Q=0.05 | -0.155 | **-0.0001** |
| aglKfB, climb, Q=0.30 | +0.169 | **+0.0001** |

And it removes most of the under-tracking that the 0.3 default was argued
from - the three-arm run again, before and after:

| arm | slope 1 s before | after | HAglStd before | after |
|---|---|---|---|---|
| A Q=0.05 RNG=0.5 | 0.747 | **0.964** | 0.117 | 0.117 |
| B Q=0.30 RNG=0.5 | 0.907 | 1.086 | 0.142 | 0.141 |
| C Q=0.05 RNG=0.15 | 0.955 | 1.080 | 0.046 | 0.046 |

Q=0.05 after the fix (0.964) beats Q=0.30 before it (0.907), at the same
reported uncertainty, and B and C now overshoot slightly - a mild sign that
0.3 is too loose once the decay is gated properly. **So the default stays at
0.05**, and the flights that appeared to need 0.3 were compensating for the
decay, not for insufficient process noise. `OpticalFlowAGLKalmanFilter`
still passes: a real injected 0.7 m/s2 bias moves the estimate -0.013 ->
0.334.

Outstanding: the third commit's message still argues the default from the
flight values and should be rewritten around this result. That needs an
amend.

## The problem

The 2-state AGL KF integrates `velDotNED.z`, which still carries the active
accel-Z bias (`correctDeltaVelocity` removes only the inactive-lane bias and
the frozen hover-Z correction). With no bias state the rangefinder only
partially corrects the drift, so the AGL height sits high by an amount that
tracks the main filter's bias: `HAgl - RFND*cosTilt` was +0.33 m at
`XKF2.AZ` 0.51 decaying to +0.13 at 0.21 (4-inch quad, log56). Not tilt
(which lowers it), not lag (it was high during the climb). That offset feeds
the flow velocity scaling (~20% early-flight scale error), would corrupt
altitude outright if the AGL height were fused as the rangefinder
observation (#33359), and with #33478 a short AGL velocity becomes a short
main-filter velocity and a sinking altitude hold.

## The conclusion and why

Add the bias as a third state, `[h, v, b_az]`, observable from successive
rangefinder updates, with the Joseph update reducing to the 2-state form when
the bias terms are zero. Flown on the 4-inch quad, log59 (not committed):
`Bias` converged to -0.065 (std 0.018) and `HAgl` tracked the rangefinder
with no offset.

Then it was too stiff. `Qbias` was sized for a static bias, but the bias
drifts with IMU temperature (~5 C of prop-wash cooling per flight). log66:
`BiasStd` locked at 0.009, a persistent +0.1 m/s upward residual in both
`VD` and `-VAgl` while the rangefinder was flat, and altitude ran to 1.16 m
against 0.13 m with the rangefinder selected as height source all flight.
The lever is the residual velocity, not the height switch.

Hence the third commit: a dedicated `EK3_AGL_ABIAS_P`, decoupled from the
main filter's `EK3_ABIAS_P_NSE`. It is safe to loosen because the AGL-KF bias
is a pure random walk with no prediction term - it changes only in the
innovation-gated rangefinder update, its covariance is capped, and after 5 s
without the rangefinder the filter is marked invalid - so a looser value
cannot learn a bad bias on stale range data, unlike the main filter.

## Key findings

### Replay sweep on log66 (PD drift over the hover / main-filter AZ std)

| setting                          | drift  | AZ std |
|----------------------------------|--------|--------|
| baseline (shared 0.02)           | 0.74 m | 0.034  |
| shared EK3_ABIAS_P_NSE = 0.1     | 0.29 m | 0.051  |
| decoupled EK3_AGL_ABIAS_P = 0.1  | 0.40 m | 0.034  |
| decoupled 0.2                    | 0.30 m | 0.033  |
| decoupled 0.3                    | 0.27 m | 0.033  |

Raising the shared noise recovers the drift but makes the main filter's bias
noisier (0.051), the bad-bias risk. The decoupled parameter recovers the full
~60% reduction at 0.2 with the main filter unchanged.

### Under-tracking at the default, fixed at 0.3

Regress AGL-KF height change on rangefinder height change over 1-5 s
baselines (slope 1.0 = perfect; the input normalises out so flights of
different aggression compare). Flown on the 5-inch baro-only quad (not
committed):

| log            | `AGL_ABIAS_P` | slope     | corr      |
|----------------|---------------|-----------|-----------|
| log35          | 0.05          | 0.70-0.71 | 0.93-0.94 |
| log38 phase 1  | 0.05          | 0.59-0.61 | 0.89-0.90 |
| log41 seg1     | 0.3           | 0.83-0.85 | 0.96      |
| log41 seg2     | 0.3           | 0.84-0.87 | 0.96-0.97 |
| log41 seg3     | 0.3           | 0.90-0.94 | 0.97-0.98 |

Low slope at high correlation is a gain error, not noise, which is what
made it findable. With 0.3 and #33478 that airframe held 36 s hands-off at
0.13 m true std.

The same value came out of a Replay sweep on a second flow-navigation
airframe (log311, not committed), metric = main-filter altitude lag behind
the rangefinder over a 0.9 m/s climb: 1.70 m at 0.05, 1.03 at 0.1, 0.47 at
0.2, 0.20 at 0.3, ~0 at 0.5, monotonic, with no hover-height penalty and no
jitter (0.026 m against the rangefinder's own 0.040). 0.3 rather than 0.5
keeps the re-acquisition transient after a long dropout proportionally
smaller. A third airframe wanted 0.1-0.2.

The intuitive reading is backwards: a rising `XKFA.Bias` during a climb
looks like the bias "stealing" velocity, which argues for a lower Q. The
Replay refuted it; the ramp is the filter correctly tracking the offset and
needs to be faster.

### The default is the autotest's number, not the airframe's

0.05 passes `EK3_AglKfVelForVelD` (a sudden bias step overshoots at >=0.1)
and gives ~36% of the reduction. Flown at 0.05 on the 4-inch quad (log67):
`BiasStd` locked at 0.0156, exactly as Replay predicted (~0.0155), and
altitude still drifted (1.3 m against 0.3 m) on a flight that cooled 7 C.
Replay predicts 0.2 gives `BiasStd` 0.041. A slow thermal drift and a step
are different tests; the default is tuned to the step. The parameter doc's
own argument ("only updates from clean rangefinder measurements, so a higher
value cannot learn a bad bias") supports a higher default.

### The bias freezes on a dropout, and the velocity does not go to zero

With no measurement `aglKfB` holds (by design) while the prediction keeps
adding `(aglKfB - velDotNED.z)*dt`; the 2 s decay leaves a steady state of
residual x tau, not zero. The bias state shrinks the residual but any
unlearned part still integrates. The consequence for consumers of `aglKfV`
and `aglKfH` (the velD fusion, the height-source switch in #33359, the HAGL
gate in #32472) is written up in `../33478/`.

### The root beneath it

The 4-inch airframe's accelerometer reads ~0.77 m/s^2 low at 45 C despite
`INS_TCAL1` enabled to 70 C (IMU.AccZ -9.04 at 45 C, -9.79 at 28 C, pre-arm,
level). The whole chain - ground bias learning, AGL-bias tracking, residual
velocity, altitude drift - is compensating for a sensor that should read
flat over temperature. Fixing the thermal calibration removes the thing being
chased; this PR makes the chase work in the meantime.

## What is here

```
33507/
  README.md    <- this file
```

No logs committed; logs 56, 59, 66 and 67 (4-inch quad), 35, 38 and 41
(5-inch quad) and 311 (second airframe) are cited by number only.

## Reproduce

```
git checkout pr-agl-kf-zbias
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.OpticalFlowAGLKalmanFilter
```

The Replay sweeps are real-log only (`--force-ekf3` over a log carrying
RISI/RFRN/RRNI/ROFH). The under-tracking has no SITL reproduction yet:
inject a slowly ramping `SIM_ACC1_BIAS_Z` during a flow hover with repeated
1-3 m climbs at 0.05 and 0.3, and regress `XKFA.HAgl` change on rangefinder
change; the default should show a slope well under 1 at high correlation.

## Branches and people

- `pr-agl-kf-zbias` - the PR branch (three commits: state, autotest,
  decoupled process noise).
- Author: @andyp1per. No maintainer review yet.
- Consumed by #33478 (`../33478/`), whose flight validation ran this filter
  at 0.3; #33359's `aglKfH` fusion needs it.
- Reviewer question (LupusTheCanine): a shared AccZ bias? The AGL KF bias
  has to stay learnable while the baro is gated, which is exactly when the
  main-filter bias freezes; #33478 makes the main bias observable through
  the velD fusion instead of by sharing the state.
