# PR #33498 - inhibit Z gyro bias from optical flow when there is no yaw source

Analysis archive for [ArduPilot/ardupilot#33498](https://github.com/ArduPilot/ardupilot/pull/33498).
Branch `pr-gyro-z-unobservable-without-yaw` (andyp1per fork), base `master`,
PR head `ba52c7e431` (pushed 2026-09-15); before that `17f19f6202`
(2026-09-02). Local head `55aa43f4c6` (2026-09-16, rounds 2 and 2b, not pushed). The flight evidence is from a 4-inch optical-flow quad (MatekH743,
ARK Flow, no compass in the flow source set); numbers are cited inline and
no logs are committed.

## Status (one line)

Correctness fix, flight-validated on the airframe that exposed it. The
2026-09-15 round makes the guard purely fusion-based (the compass leg M1 is
measured and fixed) and adds an autotest; pushed 2026-09-15 as `ba52c7e431`
and rmackay9's review answered the same day. See "Round of 2026-09-15" below.
Round 2 (2026-09-16, local, not pushed): the AP-Review re-acquisition finding
reproduced and fixed in `checkGyroCalStatus()`, with a recovery autotest; see
"Round 2, 2026-09-16" at the end.

## Review 2026-09-10: two of the three legs are honest, the compass leg is not

Current GitHub state: tridge approved this head, rmackay9 requested changes
with two inline comments. The review below converges on the same line he
pointed at, for a different reason - and his proposed replacement would make
it worse.

The predicate is **not sufficient**. Of its three legs, GPS
(`recentGpsYawFusion()`, stamped only by a successful `fuseEulerYaw(GPS)` or
`alignYawAngle()`) and EXTNAV (the new `last_extnav_yaw_fuse_ms`, correctly
*not* the existing `last_extnav_yaw_fusion_ms`, which is refreshed for
rejected samples too) are genuine fusion-freshness tests. The compass leg,
`use_compass() && !magTimeout`, is configuration plus a 10 s innovation
timeout, and both can stay true forever with zero compass fusion.

**M1. The compass leg never inhibits when the compass stops delivering.**
Chain, all traced: `Compass::use_for_yaw()` is a pure parameter test with no
health term; `use_compass()` adds only the source enum and
`!allMagSensorsFailed`; `magHealth` is written *only* inside
`FuseMagnetometer()` and `fuseEulerYaw()`, is not re-initialised in
`InitialiseVariablesMag()`, and is sticky between fusions; and
`AP_NavEKF3_MagFusion.cpp:511-517` runs `if (magHealth) { magTimeout =
false; lastHealthyMagTime_ms = imuSampleTime_ms; }` **every filter step,
regardless of whether any mag data was fused**. Meanwhile `readMagData()`
stops storing samples once `compass.healthy()` goes false, the ring buffer
drains, `dataReady` never fires again, and `magHealth` is frozen at true.
`allMagSensorsFailed` does not save it: `compass.available()` stays true
with the backend registered, and the `magTimeout && assume_zero_sideslip()`
path needs `magTimeout` false and fly-forward, which is false on copter.

- Scenario A: flow-only Loiter, `EK3_SRC1_YAW=1`, a single external I2C
  compass wedges at t=60 s. From t=60.5 s the EKF fuses no yaw of any kind
  and the guard returns false for the rest of the flight - exactly the
  configuration the PR exists to protect, left unprotected.
- Scenario B, and this is the airframe class: `magFailTimeLimit_ms` is
  10000 and `magTimeout` is cleared by a *single* healthy fusion.
  Intermittent interference on a high-current 4-inch quad - 9 s of rejected
  innovations, one good sample, repeat - keeps `magTimeout` permanently
  false while almost no yaw information enters. The flight here shows GZ
  reaching -1.43 deg/s within seconds of flow fusion going live, so 10 s
  windows are ample.

Fix: mirror the other two legs. Stamp `last_mag_yaw_fuse_ms` where compass
yaw actually fuses - the `fuseEulerYaw(MAGNETOMETER)` FUSE_YAW branch, the
anchored case, and the three `magFusePerformed = true` sites in
`FuseMagnetometer()` - and test it at 5 s. That makes all three legs
symmetric and is the genuine "variable for the last yaw source actually
fused" rmackay9 is asking for. Cheapest partial fix is adding
`dal.compass().healthy(magSelectIndex)`, which closes scenario A only.

**Decline rmackay9's `yaw_source_last` -> `getYawSource()` suggestion, with
reasons.** The predicate is not new - it is byte-identical to what stood in
`AP_NavEKF3_Control.cpp:62-66` before this PR; the diff extracts it verbatim.
`yaw_source_last` is not a change-detector: it is the effective yaw source
behind ~20 existing decisions including `use_compass()` itself.
`setYawSource()` deliberately remaps COMPASS->NONE and
GPS_COMPASS_FALLBACK->GPS while `wasLearningCompass_ms` is set, so swapping
in `getYawSource()` would report a compass yaw source *during compass
calibration*, when the compass is deliberately not fused - strictly worse
for this guard. It is also not stale by a step: `controlFilterModes()` ->
`setAidingMode()` -> `setYawSource()` runs ahead of `SelectMagFusion()` and
`SelectFlowFusion()` in the same iteration.

**Take his second comment.** Both call sites read `if
(!flowYawGyroBiasInhibited())`; `recentYawFusion()` returning true when a
reference is being fused reads better and lines up with
`recentGpsYawFusion()`. Separately, the new `last_extnav_yaw_fuse_ms` and
the existing `last_extnav_yaw_fusion_ms` differ by two characters on
adjacent lines. The GPS pair does this properly (`last_gps_yaw_ms` for the
sample, `last_gps_yaw_fuse_ms` for the fusion); rename the old member to
`last_extnav_yaw_ms` - three uses.

### Should-fix

- `if (fuseEulerYaw(EXTNAV))` marks a fusion `FinishFusion()` may have
  skipped: `fuseEulerYaw()` returns true unconditionally after
  `faultStatus.bad_yaw = FinishFusion(...)`, and `FinishFusion()` returns
  true and applies nothing when the update would drive a variance negative.
  The correct idiom is 70 lines below in the same file (`yawAnchored &&
  !faultStatus.bad_yaw`). The pre-existing GPS path has the same gap - out
  of scope, but worth one sentence so it is a decision.
- Body-frame odometry has the identical hole and is untouched.
  `FuseBodyVel()` applies the unguarded `kalman_mask |=
  (1<<10)|(1<<11)|(1<<12)` at three sites, and `readyToUseBodyOdm()`
  explicitly does not require yaw alignment. Visual odometry and wheel
  encoders absorb the same phantom Z bias. Deferring is defensible; say so.
- The description does not pre-empt "why not just lower `EK3_GBIAS_P_NSE`".
  This record has the answer (1e-3 -> 1e-4 still ran GZ to ~2.0 deg/s, 40 s
  instead of 5 s): process noise sets the rate an unobservable state walks,
  not where it stops, and it is global across X/Y and every fusion path.
  One sentence. Note the review brief's inverse framing - "letting it learn
  with inflated process noise" - is the wrong direction: more Q learns the
  phantom faster. The alternative worth naming is the deflated one.

### Correction to this record, and a better mechanism

**"No SITL reproduction yet" is stale.** The PR description already carries
SITL A/B results - three figures, box-pattern runs, and the
GPS-yaw-dropped-after-takeoff run that separates this head from the
config-only first head. What is missing is an **autotest**, not a repro.

**The stated mechanism understates the case.** The attitude rows of the flow
Jacobian are each proportional to velocity and `H_LOS[4..6]` are pure
quaternion, so flow *does* observe yaw error whenever the vehicle
translates - it is not blind to heading. What it cannot separate is yaw
error from a rotation of the flow frame relative to the body, and the filter
has no state for the latter. A static misalignment therefore presents as an
ever-growing yaw error, and the only state that can produce a *sustained*
yaw correction rate is state 12 - hence the rail. "Jointly unobservable"
(the wording used here) is too strong; "the bias absorbs an un-modelled
static misalignment" is accurate and makes the change look inevitable rather
than defensive.

The honest regression: with a well-aligned flow sensor, flow was the only
in-flight path that could correct a *genuine* Z gyro bias in a no-yaw
configuration, and it is now frozen at its ground value for the flight. The
gate does not protect against taking off before it converged -
`checkGyroCalStatus()`'s no-yaw branch rotates the three bias variances as a
vector and tests only the horizontal terms, so at level attitude `P[12][12]`
is not tested at all and `delAngBiasLearned` can be true with the Z variance
still at its initial value. UNCONFIRMED how much this matters (`INS_GYR_CAL`
removes most of it at boot, and the PR's own A/B with a real 1 deg/s bias
shows ground learning captured 0.93 of it).

**What the bias does while inhibited.** State 12 is not frozen, only cut off
from flow. Still live: `fuseEulerYaw(STATIC)` on the ground, which computes
gains for every state with no mask and is the intended learning path;
`fuseEulerYaw(PREDICTED)` in flight, which has `innovYaw = 0` by
construction so it shrinks covariance without moving the state; and
`FuseVelPosNED` height fusion, where the `poorObservability` mask is
disabled outside AID_NONE, so `K[12] = P[12][9]*SK` still lets baro
innovations nudge state 12 through cross-covariance. **That last path is the
code-level candidate for the ~0.5 deg/s residual creep this record
attributes to "the magnetometer fusion path still nudging the bias".** With
`SRC2 YAW=0`, `SelectMagFusion()` returns before any magnetometer fusion
runs, so the mag path cannot have been active unless that flight also spent
time in a compass source set. Re-derive before repeating that explanation.

**Lifting is clean and the PR should say so:** the mask is K-only, nothing
is zeroed, nothing has to be restored, `P[12][12]` grows only on process
noise while inhibited, and whatever yaw fusion resumes learns the state
through its own unmasked gains. No discontinuity, no hysteresis needed. One
subtlety: with `Kfusion[12] = 0`, `KHP` row 12 is zero but column 12 is not,
and `FinishFusion()` symmetrises by averaging, so state-12 cross-covariances
shrink by half what they otherwise would. Second order, and identical to how
the existing AID_NONE mask behaves - not the `e004e792ff` wind-truth failure
mode, since no variance is forced to zero with live cross terms.

### Per-source behaviour (all verified)

- NONE - always inhibits. The target case.
- COMPASS - see M1. Correct on one edge: during compass calibration
  `setYawSource()` remaps to NONE, so the guard inhibits while the compass
  is deliberately not fused.
- GPS - inhibits 5 s after the last *accepted* fusion; a sample failing the
  innovation gate does not refresh it. This is the leg the earlier head
  (629b5959e9) got wrong, and it is now right.
- GPS_COMPASS_FALLBACK - the best-built leg. GPS yaw lost: leg 1 drops at
  +5 s and the fallback cannot engage before +10 s, so there is a correct
  5 s inhibit window; if it engages, `gps_yaw_mag_fallback_active` passes
  leg 2; if it never does, the guard keeps inhibiting. Caveat feeding M1:
  `magTimeout` in this mode is contaminated, because `fuseEulerYaw(GPS)`
  also writes `magHealth`.
- EXTNAV - fusion-fresh. With `EK3_FEATURE_EXTERNAL_NAV` compiled out the
  leg vanishes and an EXTNAV setting inhibits: the safe direction.
- GSF - always inhibits, correctly and harmlessly. The yaw estimator bails
  unless POSXY is GPS and VELXY includes GPS, so with flow as the velocity
  source it never fuses yaw at all; where it does, GPS pos/vel are being
  fused with state 12 unmasked, so nothing is lost.

### The autotest sketch needs reworking before it is written

- `SIM_FLOW_OFS_X` **does not exist on this tree** - the SITL flow knobs are
  `SIM_FLOW_ENABLE/RATE/DELAY/POS/RND`. Do not make an autotest depend on an
  unmerged branch.
- A symmetric `FLOW_FXSCALER` error is the wrong shape: a magnitude error is
  absorbed by the velocity states. The flight had a *rotation* (cross-axis
  596-931%, correlation -0.4). `FLOW_ORIENT_YAW` rotates the SITL flow
  vector without rotating the reported body rate - the un-modelled
  misalignment exactly. Asymmetric FX against FY is second best.
- Hover will not discriminate: the attitude rows of `H_LOS` scale with
  velocity, so near zero groundspeed the only route into state 12 is the
  weak `P[12][4..6]` cross-covariance. It needs sustained translation with
  heading changes, which is what the manual SITL runs did.
- "Assert GZ rails" needs a threshold: state 12 is constrained to
  +/-0.5*dtEkfAvg rad, saturating near 28 deg/s. Assert magnitude >0.5
  deg/s on master and <0.1 on the branch, and keep the injection inside
  `EK3_FLOW_I_GATE` or the innovation check rejects it and the flow never
  fuses.
- It needs a positive control: assert `XKF5.FIX/FIY` are non-zero and
  one-sided, or "GZ stayed near zero" is indistinguishable from "the flow
  was gated out". Coverage is a trace, not a green run.
- Build it on `LoiterNoCompassYaw` - flow-only Loiter, `EK3_SRC1_YAW=0`, no
  GPS, already arms and takes off, and today asserts only "still armed,
  still in Loiter". `EK3_SRC1_YAW=0` alone trips the new branch, so the
  compass need not be disabled.
- The highest-value test is not the original failure but the
  **GPS-yaw-lost-in-flight** case, because that is where this head differs
  from the predicate the previous round shipped. Constraint from the PR's
  own data: the drop must happen while `P[12][12]` is still large - dropping
  GPS after a full lap barely moves the bias, because the extra fusion
  collapses the variance and the flow gain scales with it.

### Notes

- 192 commits behind master and nothing has moved: only 2 of the 192 touch
  `AP_NavEKF3/`, both the `airspeed_sensor_enabled` removal, neither in a
  touched region. Three of the four files are byte-identical to master; the
  fourth moved the insertion point by one line. The patch applies with one
  offset and zero fuzz.
- Mechanical gates pass: `diff --check` clean, one commit, one module,
  correct prefix, no Claude attribution. Comment density matches the file.
- No DAL surface change, so Replay is unaffected.
- The new predicate line is 135 columns; it must wrap if it gains a fourth
  term from M1.
- Nothing new is logged, and the guard's state cannot be reconstructed from
  a log (`magTimeout` is XKF4.TS bit 3, but neither fusion timestamp is
  logged) - in a PR that exists because of a log diagnosis. Consider one bit
  in an existing status word.
- Commit-message accuracy: everything checks out except "the bias stays at
  the value learned on the ground" (height fusion still nudges it) and "the
  test is on fusion, not on the configured source" (true for two legs of
  three). Both are one-clause fixes.
- Worth adding to the description: `SelectMagFusion()` runs before
  `SelectFlowFusion()` in the same step, so the timestamps the guard reads
  are current rather than one step stale. It is the first thing a careful
  reviewer checks.

## Round of 2026-09-15: rmackay9's review, and M1 measured

Answering rmackay9's CHANGES_REQUESTED of 2026-09-07. Local commits on top
of `17f19f6202`, not pushed:

- `bfd220a15a` AP_NavEKF3: learn flow Z gyro bias only after actual yaw
  fusion
- `30ee7cc232` autotest: check optical flow learns no Z gyro bias without
  yaw fusion
- `bdce23d76c` AP_NavEKF3: do not overstate what last_mag_yaw_fuse_ms
  records (comment only)

### What changed

The guard is now `recentYawFusion()`: true if GPS, compass or external nav
yaw was fused within 5 s, read only from fusion timestamps. A new
`last_mag_yaw_fuse_ms` is stamped where compass data is actually fused:
after all three axes of `FuseMagnetometer()` (reached only if `magHealth`
passed and every `FinishFusion()` succeeded), and after
`fuseEulerYaw(MAGNETOMETER)` in the FUSE_YAW branch when
`!faultStatus.bad_yaw`. The external nav stamp got the same
`!faultStatus.bad_yaw` condition (the should-fix above). The guard no longer
reads `yaw_source_last`, `use_compass()` or `magTimeout`, and
`setWindMagStateLearningMode()` is byte-identical to master again: the
hoisted `recentGpsYawFusion()` is gone.

One deliberate behaviour difference, derived from the source, not measured:
the guard no longer tests which source is active, so after an in-flight
switch away from GPS or compass yaw the flow can still learn the bias for up
to 5 s. A yaw reference really was fused in that window, and each stamp can
only be written while its source is the active one.

### Measured, SITL, 2026-09-15

Autotest `FlowGyroZBiasNoYawReference` as committed in `30ee7cc232`:
flow-only Loiter, analog range finder, `FLOW_FXSCALER 200`, 16 legs of 10 s
forward flight with a yaw turn between legs (240 s), bias-free simulated
gyro, yaw reference removed 5 s after takeoff. Metric is max |XKF1.GZ| in
deg/s over both cores. Every flight also logged 3085-4201 non-zero XKF5 flow
innovations, so flow was fused in all of them.

| code | no yaw source | all compasses fail (`SIM_MAGn_FAIL 1`) | GPS yaw lost (`copter-gps-for-yaw.parm`, both receivers disabled) |
|---|---|---|---|
| merge-base `c56e34434b` | 0.30 | 0.30 | 0.23 |
| PR head `17f19f6202` | 0.00 | **0.29** | 0.02 |
| temporary guard on the configured source, `frontend->sources.getYawSource(core_index)` | 0.00 | 0.31 | 0.08, 0.18, 0.18 (three runs) |
| `bfd220a15a` | 0.00, 0.00 | **0.03**, 0.03 | 0.01, 0.02 |

The head's no-yaw-source number is from a first run of the test that ended
in LAND; the flight portion is identical. That run found a harness problem:
in LAND with the flow scale error the vehicle touched down and then held a
30 deg roll demand on the ground (ATT.DesRoll -29.7, Roll 0.1) and never
detected the landing, so the test lands in ALT_HOLD.

M1 is real at tier 2: with every compass dead in flight the head's compass
leg keeps passing and the bias runs to 0.29 deg/s, the same as with no
guard. The fusion guard holds it at 0.03.

The GPS-yaw-lost case is the noisy one. The configured-source guard is
logically identical to the merge-base there, yet read 0.08 once and 0.18
twice against the merge-base's 0.23. The likely cause is how long GPS yaw
fused on the ground before takeoff, which sets `P[12][12]` at the loss; not
isolated. The test threshold is 0.1 deg/s: guarded runs top out at 0.03,
and the compass case alone separates a revert or a configured-source guard
(0.29-0.31) from the fix.

Also run at `bdce23d76c` (binary built from `bfd220a15a`; the later commit
is comment-only), all passing: `LoiterNoCompassYaw`,
`GPSForYawCompassFallback`, `MagFail`, `OpticalFlowLimits`. The external
nav stamp change was not exercised in SITL.

### rmackay9's three points

1. "I don't think using yaw_source_last is correct." The guard no longer
   reads it; see the numbers above.
2. "A new use of yaw_source_last... change to getYawSource(core_index), OR
   we need a new variable to capture what the last yaw source that was
   actually fused."
   - Not new: master's `setWindMagStateLearningMode()` has the identical
     expression inline (`AP_NavEKF3_Control.cpp:62-65` at `c56e34434b`);
     the head only hoisted it. Derived from the source.
   - `yaw_source_last` is not only a change detector. `setYawSource()`
     writes it from `getYawSource(core_index)` with one remap while the
     compass is being calibrated (COMPASS -> NONE, GPS_COMPASS_FALLBACK ->
     GPS), and about 25 decisions on master read it, `use_compass()` among
     them. Swapping `getYawSource()` into `recentGpsYawFusion()` is a no-op:
     both remapped values stay inside the GPS set. Derived from the source.
   - A guard on the configured source is what fails, measured: 0.31 deg/s
     with the compass dead, 0.08-0.18 with GPS yaw lost.
   - His second option is what was done: fusion timestamps for all three
     sources and nothing else.
3. Rename the double negative to `recentYawFusion()`: taken.

### Not done this round, with reasons

- Renaming `last_extnav_yaw_fusion_ms` to `last_extnav_yaw_ms`: master code
  outside the change; the new member's comment carries the distinction.
- The pre-existing GPS path stamps `last_gps_yaw_fuse_ms` on a
  `fuseEulerYaw(GPS)` return without checking `bad_yaw`. Master code with
  the same gap the external nav path had; left alone, worth a sentence on
  the PR.
- `FuseBodyVel()` still learns state 12 unguarded: deferred, as before.
- Logging the guard state: not done.
- Replay against log53/log56: owed. The log roots are not mounted on the
  machine this ran on. In the flights' own no-yaw source set the two guards
  behave identically (derived from the source); what Replay would show is
  the up-to-5 s tail after a switch from a compass-yaw source set.
- History: `17f19f6202`'s message still describes the compass test as "in
  use and not timed out". The three AP_NavEKF3 commits want squashing under
  a rewritten message before the push.

## The problem

First flow-only Loiter on the airframe (`EK3_SRC2` POSXY=0, VELXY=5, YAW=0;
log53): no flyaway, but a loose hold - GPS speed mean 0.47 m/s and the EKF
position wandered ~10 m over 160 s. Calibration was not the cause: the raw
static gyro-Z was -0.000 rad/s and `XKF1.GZ` was 0.0 on the ground. GZ
jumped to -1.43 deg/s the instant flow fusion went live at takeoff, which is
a continuous -1.4 deg/s yaw drift, ~108 deg over the flight. The flow-cal
check confirmed the frame had rotated away from the body: cross-axis 596-931%
and correlation -0.4, against 1-2% and -0.98 on the previous flight.

## The conclusion and why

With optical flow as the velocity source and no yaw source, heading and the
Z gyro bias are jointly unobservable: a flow-velocity mismatch can be
reconciled by nudging yaw or by moving the bias, indistinguishably, and the
filter dumps it into the bias. Position is integrated in NED, so a yaw drift
smears the position integral.

Flow position hold does not need absolute yaw. A constant yaw offset cancels
because yaw appears in both the flow-to-NED rotation and the NED-accel-to-lean
rotation. What it cannot tolerate is yaw drift. The requirement is a stable
relative yaw, which the gyro provides if its bias is left at the calibrated
value. Hence: mask state 12 out of the optical-flow Kalman update whenever
the yaw source is None, mirroring the existing accel-Z inhibit under flow.
X/Y gyro biases stay observable through gravity and are untouched.

## Key findings

### Stiffening the bias state does not work

`EK3_GBIAS_P_NSE` 0.001 -> 0.0001 (log54, not committed) still ran GZ to
~2.0 deg/s and saturated it; it took ~40 s instead of ~5 s. Process noise only
throttles how fast an unobservable state moves; a persistent one-sided
innovation still drives it to the rail. The measurement update has to be
inhibited.

### Validation

Flown on the same quad, log56 (not committed), same config plus the inhibit:
flow-cal cross-axis 596-931% -> 2-4%, correlation -0.4 -> +0.95 (the yaw is
again consistent with the true body frame); GZ held ~0 for 50 s and crept
only to ~0.5 deg/s over the flight. The PR's before/after figure is a
different metric on the same flights, the flow-vs-GPS velocity scatter
(|corr| 0.01 -> 0.91). A later flight (log58) reconfirmed GZ stable at
-0.06 deg/s with no yaw drift.

Two residuals, neither addressed here: the slow creep to ~0.5 deg/s is
probably the magnetometer fusion path still nudging the bias (the inhibit is
in the flow update only); and the X-axis flow scale read 1.21 on a low, short
flight with few strafe samples, so do not trim `FLOW_FXSCALER` from it.

### Alternatives considered

GSF yaw (`SRC_YAW=8`) needs GPS velocity and is out for flow-only. A
deliberately distrusted compass (`SRC2_YAW=1` with high `EK3_MAG_NSE`) remains
the fallback if a yaw observation is ever wanted.

## What is here

```
33498/
  README.md    <- this file
```

No logs committed; logs 53, 54, 56 and 58 are cited by number only.

## Reproduce

No SITL test exists. A candidate: optical-flow-only nav with
`EK3_SRC1_YAW=0`, no compass, inject a persistent one-sided flow mismatch
(`SIM_FLOW_OFS_X` from the #33484 branch, or a `FLOW_FXSCALER` offset) and
assert `XKF1.GZ` rails on master and holds with this change. SITL flow is
perfectly scaled, so without an injected mismatch nothing drives the bias.

### Superseded 2026-09-15 by the autotest in `30ee7cc232`

`Tools/autotest/autotest.py test.Copter.FlowGyroZBiasNoYawReference` on the
branch. It uses `FLOW_FXSCALER 200` rather than `SIM_FLOW_OFS_X` (not on
master) and covers no yaw source, compass lost in flight and GPS yaw lost in
flight. Numbers and the threshold rationale are in "Round of 2026-09-15"
above. The paragraph above is left as the design the test grew from.

## Branches and people

- `pr-gyro-z-unobservable-without-yaw` - the PR branch (one commit).
- Author: @andyp1per. No review yet.
- 2026-09-15: four local commits (see "Round of 2026-09-15"); reviews:
  tridge (automated) APPROVE at `17f19f6202`, rmackay9 CHANGES_REQUESTED
  2026-09-07, not yet answered on the PR.
- Related: #33497 (the same airframe's flow half-rate fault, fixed first so
  this could be seen), #33484 (per-axis lockout recovery).

## Pushed 2026-09-15

Force-pushed as two commits on the same base: `17f19f6202`, `bfd220a15a` and
`bdce23d76c` squashed into `97661a3b2d` ("AP_NavEKF3: learn Z gyro bias from
optical flow only after yaw fusion"), then the autotest `30ee7cc232` as
`ba52c7e431`. The tree is byte-identical to `bdce23d76c`'s, so every number in
the 2026-09-15 round holds for the pushed head.

Reply to rmackay9 posted 2026-09-15 11:23Z
(https://github.com/ArduPilot/ardupilot/pull/33498#issuecomment-5679359765): his second
option (record what was actually fused) taken, the `getYawSource()` swap
declined with the SITL table, `recentYawFusion()` named as he suggested. The
PR body's guard paragraph was replaced to describe the fusion-only test, the
FlowGyroZBiasNoYawReference table added and the automated-test box ticked.
The PR had no `AIReview` label; it was added 2026-09-15, so its 2026-09-02
APPROVE round will be superseded by a review of `ba52c7e431`.

## Round 2, 2026-09-16: flow aiding never restarts once yaw fusion has stopped

Reviews at `ba52c7e431`: tridge (automated) COMMENT 2026-09-15 14:54Z (then
deprecated), AP-Review REQUEST CHANGES 2026-09-16 04:11Z, rmackay9 approved
2026-09-15 23:11Z with a suggested commit (`a6eeb104ed`) and said on
2026-09-16 07:16Z he would check the recovery finding himself unless we did.

Local commits on top of `ba52c7e431`, not pushed:

- `576746c749` AP_NavEKF3: skip the Z gyro bias check while no yaw is being
  fused
- `bc305a61b3` AP_NavEKF3: record the anchored compass yaw fusion
- `790286326b` AP_NavEKF3: gps-for-yaw fuse time fixed (rmackay9's
  `a6eeb104ed`, cherry-picked with his authorship)
- `6f4552b8ba` autotest: tighten FlowGyroZBiasNoYawReference
- `6a7e1d9d0f` autotest: check optical flow aiding restarts while compass yaw
  is not fused
- `9e5f3fd364` autotest: do not state an unmeasured reason for the GPS case
  limit (comment only; squash into `6f4552b8ba`)

### The finding reproduced

`checkGyroCalStatus()` drops the Z axis from the `delAngBiasLearned` test
only when no yaw source is configured. With the PR, flow stops learning the Z
gyro bias once yaw fusion stops, so with a configured but dead compass
`P[12][12]` never falls below `delAngBiasVarMax` (`sq(radians(0.15 *
0.012))` = 9.87e-10). `delAngBiasLearned` gates `readyToUseOptFlow()`, and
from AID_NONE nothing else can restart aiding.

SITL 2026-09-16, non-debug build with a temporary dataflash probe
(`delAngBiasLearned`, `P[10..12]`, `recentYawFusion()`, `PV_AidingMode`) that
was never committed. Flow-only Copter, `FLOW_FXSCALER 200`, no GPS,
`EK3_SRC1_YAW 1`, all three compasses failed 5 s after takeoff, box legs
until t = 346 s, then `SIM_FLOW_ENABLE 0` for 30 s in ALT_HOLD. Core 0:

| code | `P[12][12]` 60 / 200 / 330 s | `delAngBiasLearned` | aiding restarted |
|---|---|---|---|
| merge-base `c56e34434b` | 2.97e-9 / 9.54e-10 / 5.07e-10 | true from 184.3 s | yes, at flow return (378.1 s) |
| PR head `ba52c7e431` | 3.93e-9 / 3.76e-9 / 3.39e-9 | false from 4.7 s on | **no**, 60 s waited |
| head + `!recentYawFusion() \|\|` | 4.07e-9 flat | true (XY test) | yes, at flow return (377.4 s) |

One run each. The review's 3/3 plus these agree.

**Pre-existing on master for an early dropout.** The same dropout 5 s after
the compass fails (the autotest's timing) does not recover on the
merge-base either: `P[12][12]` was 7.93e-9 at the dropout, 8x the threshold,
and master only gets under it after about 180 s of flow flight. So the fix
also removes a master limitation, and the new test fails on master as well
as on the PR head. Measured, one run each: merge-base no restart in 30 s;
head no restart; fix restarted 1.0 s after flow returned; no yaw source
configured (`EK3_SRC1_YAW 0`, existing branch) restarted 0.6 s after.

A side observation from the fix run: in the XY branch the variance vector is
rotated by `prevTnb` (the "checkGyroCalStatus and tilt" note in the EKF3
playbook), so with `P[12][12]` at 4e-9 `delAngBiasLearned` toggled false
during every pitched leg and true when level. A restart therefore needs the
vehicle roughly level when flow returns. Same property as master's
no-yaw-source branch; not changed.

### Fix chosen, and its side effects

`576746c749` adds `!recentYawFusion() ||` to the condition, the review's
suggestion, keeping the existing no-source clause (it still decides the up
to 5 s tail after a switch away from a fused source).

`recentYawFusion()` is also false at boot before the first yaw fusion, and
the same function gates `readyToUseGPS()` and `readyToUseRangeBeacon()`.
Measured on the probe build, 2 runs each with the fix, 1 without, all
identical:

| vehicle, defaults | cov init | first yaw stamp | `delAngBiasLearned` | GPS aiding starts | `P[12][12]` at GPS start |
|---|---|---|---|---|---|
| Copter, fix | 5.94 s | 6.14 s | 41.54 s | 41.74 s | 1.04e-9 |
| Copter, head | 5.94 s | 6.14 s | 41.54 s | 41.74 s | 1.04e-9 |
| Plane, fix | 10.27 s | 12.31 s | not needed | 20.67 s (with `delAngBiasLearned` false) | 1.48e-7 |
| Plane, head | 10.27 s | 12.31 s | not needed | 20.67 s | 1.48e-7 |

No sample had `recentYawFusion()` false between the first stamp and GPS
start. Plane starts GPS aiding with `P[12][12]` 150x the threshold as a matter
of course (`assume_zero_sideslip()` bypasses the check), which bounds what an
earlier start can cost.

Derived from the source, not measured: on the ground the FUSE_YAW branch
fuses compass yaw even over the innovation gate, and EK3_MAG_CAL 7 anchors
it, so a compass-configured Copter stamps continuously on the ground. The one
configuration left where the stamp can be missing on the ground is
EK3_MAG_CAL 4 with 3-axis fusion rejected from boot; there the fix lets the
XY-only test pass and GPS aiding start without the Z variance converged,
where master waited. A narrower "ever fused, not recently" form would keep
master's wait there; not adopted, because the measured default boots do not
change and Plane shows an unconverged Z variance at GPS start is not in
itself harmful. Recorded in case that edge ever shows up.

Recovery autotest `FlowAidingRestartsWithoutYawFusion` (`6a7e1d9d0f`): no
flow error, compasses failed in ALT_HOLD, wait for the compass to report
unhealthy, flow off until "stopped aiding", flow on, expect "started relative
aiding" within 30 s. About 6 s wall on the debug build (first recorded here
as "about 2 min", a misreading; see the correction below). Debug build: passes at
`6a7e1d9d0f`; with `576746c749` reverted it fails ("Failed to receive text:
ekf3 imu0 started relative aiding"). The GPS-yaw-lost recovery takes the same
branch; derived from the source, not run.

### GPS-yaw-lost leg on the debug build

CI builds `./waf configure --board sitl --debug`. Merge-base EKF3, old test
(yaw lost 5 s after takeoff): 0.09 and 0.10 deg/s, both under the 0.1 limit,
reproducing the review. A third run on a build carrying the dataflash probe
read 0.21, so the value is sensitive to timing.

Changed in `6f4552b8ba`: yaw lost straight after takeoff, and a 0.05 limit
for that case only. Debug build, max |GZ| deg/s:

| code | GPS yaw lost | runs |
|---|---|---|
| merge-base | 0.22, 0.11, 0.13, 0.10 | 4, all fail |
| `6f4552b8ba` and later | 0.01, 0.01, 0.01 | 3, all pass |

Merge-base compass case with the immediate loss: 0.39 (1 run). Full test at
`6a7e1d9d0f` on debug: no yaw source 0.00, compass lost 0.02, GPS yaw lost
0.01, about 46 min wall on this machine.

**Correction 2026-09-16: that runtime is wrong by a factor of 60.** The
autotest `AT-` prefix is seconds since the harness started, not minutes, and
the "46 min" was read off `AT-0046.5`. Timed directly with `date`, the same
test on the same debug build took 71 s wall (46.5 s in the original run). The
"about 2 min" for the recovery test was the same misreading (`AT-0005.7`).
The numbers above are unaffected; only the runtimes were wrong. The test
has since been shortened anyway; see "Round 2b" below.

### "Flow was fused" now means accepted

`6f4552b8ba` replaces the XKF5 FIX/FIY count with: "fusing optical flow"
appeared, and no "stopped aiding" while armed. With flow as the only aiding
source, AID_RELATIVE drops to AID_NONE once `prevFlowFuseTime_ms` is 5 s
stale, which only advances when a flow update passes the innovation gate.
Nothing new is logged.

Mutation, debug build, no-yaw-source case: `FinishFusion()` never called for
flow. Old metric on that log: 3156 non-zero FIX/FIY samples (it would have
passed). New check: 2 "stopped aiding" while armed, so the test fails. (The
bias limit failed too in that run, at 0.64 deg/s on core 1, so this mutation
is caught twice; the review's mutation was not caught by the bias limit.)

### Items 4 and 5

- Anchored yaw stamp (`bc305a61b3`): the anchored `fuseEulerYaw(MAGNETOMETER)`
  with `!faultStatus.bad_yaw` is an applied yaw update, the same predicate the
  FUSE_YAW branch stamps on. Before, a failed 3-axis fusion straight after it
  skipped the stamp, which erred towards inhibiting.
- rmackay9's `a6eeb104ed` (`790286326b`): correct. `have_fused_gps_yaw` also
  decides clearing the compass fallback and `learnMagBiasFromGPS()`; a sample
  `FinishFusion()` did not apply should do neither, and the fallback cannot
  engage from it because `last_gps_yaw_ms` is still refreshed. Derived from
  the source. The commit message's reason is not quite the case it catches:
  an in-flight innovation over the gate already returns false; what it adds
  is `FinishFusion()` skipping the update. Other callers: EXTNAV and
  MAGNETOMETER already check `bad_yaw`; the anchored call checks and now
  stamps; GSF's result only chooses whether to fuse a synthetic yaw that
  cycle, and STATIC/PREDICTED results are unused. Left alone.

### Non-blocking, recorded

- The bias test passes with `recentYawFusion()` forced false: it only
  checks that too much bias is not learned, and never-learn satisfies that.
  No cheap case discriminates: whenever a yaw reference is fused it observes
  state 12 through its own gains, so flow's contribution is second order.
  Derived from the source, not measured. The recovery test does not
  discriminate it either (forced false takes the XY branch).
- Masked-gain covariance symmetrisation (half-corrected cross-covariance
  rows): pre-existing on master for every `kalman_mask` use (mag states
  16-21, wind 22-23, bias states); this PR changes one bit's condition.
  Agreed with AP-Review that it belongs to a separate discussion.
- Wiki: a sentence for the optical flow page is drafted in the round-2
  reply.

### Round 2b, 2026-09-16: FlowGyroZBiasNoYawReference shortened

Asked for on the strength of the wrong 46 min figure; still worth doing,
because the flight time is what CI pays for. `55aa43f4c6`:

- The yaw reference is removed at arming, before the climb, instead of after
  takeoff. This is what made the difference. Measured on the merge-base
  debug build with `FLOW_FXSCALER 400` and the same legs: GPS yaw removed
  after takeoff gave 0.03 deg/s 30 s later and 0.14 at 120 s; removed at
  arming, 0.30 at 30 s and 0.71 at 120 s. The climb's yaw fusion shrinks
  `P[12][12]` enough to slow the phantom bias. Mechanism by inference from
  the timing, not probed.
- `FLOW_FXSCALER` 200 -> 400. At 200 with the short flight the merge-base's
  no-yaw-source case read 0.15, too close to the limit.
- 4 legs of 5 s forward, 2 s turn, 3 s stop (40 s) instead of 16 legs of
  10 s (240 s).
- One 0.1 deg/s limit for all three cases; the GPS case's 0.05 limit is gone.
- Tried and rejected: full forward stick (`RC2 1100`) made the merge-base's
  GPS case learn less (0.09 max over 240 s against 0.38 at `RC2 1300`).

Debug build, max |XKF1.GZ| deg/s over both cores:

| case | merge-base `c56e34434b` | `55aa43f4c6` |
|---|---|---|
| no yaw source | 0.26, 0.27, 0.26, 0.28 (4 runs) | 0.00, 0.00, 0.00 (3) |
| compass lost | 1.03, 1.06, 1.10, 0.90 (4) | 0.01, 0.01, 0.01 (3) |
| GPS yaw lost | 1.22, 1.26, 1.09 (3) | 0.01, 0.02, 0.01 (3) |

A fourth merge-base run lost its GPS case to "Did not detect reboot"
(SITL ports, not the test) and is not counted. Every merge-base run failed
the test; every run of this branch passed.

Wall time for the whole test on this machine's debug build: 71 s before,
23-24 s after (merge-base runs 24-25 s).

Accepted-fusion check, re-checked on the short flight with the same mutation
(flow `FinishFusion()` never called): the no-yaw-source case now learns only
0.04 deg/s, so the bias limit alone would pass it, and the case fails only
because aiding stopped twice while armed. The check is doing work the bias
limit cannot.

### History and push

Before push: squash `9e5f3fd364` into `6f4552b8ba`, and probably
`55aa43f4c6` too; reword `6a7e1d9d0f` (subject 75 characters, gate note).
Keep `790286326b` as rmackay9's commit. All of this needs a grant.

Replay: still not run against log53/log56 (log roots not mounted here). The
round-2 EKF changes only differ from `ba52c7e431` when yaw fusion has stopped
and aiding has dropped to AID_NONE, which those flights (no yaw source) never
reach; derived from the source.

### Round 2 pushed and answered (2026-09-16)

Force-pushed `ba52c7e431` -> `450d8d7378`, six commits on the same base, with
`97661a3b2d` kept so the SHA cited in the 2026-09-15 reply stays valid. Tree
byte-identical to the local `55aa43f4c6`, so every round-2 and round-2b
number holds for the pushed head:

| measured on | pushed as |
|---|---|
| `576746c749` skip the Z gyro bias check while no yaw is being fused | `0c4f801054` |
| `bc305a61b3` record the anchored compass yaw fusion | `a52c416e44` |
| `790286326b` rmackay9's gps-for-yaw fuse time (his authorship) | `db4de79a6c` |
| `ba52c7e431` + `6f4552b8ba` + `9e5f3fd364` + `55aa43f4c6` FlowGyroZBiasNoYawReference | `c2c6591548` |
| `6a7e1d9d0f` recovery test, subject shortened | `450d8d7378` |

The squashed test commit message gives the merge-base no-yaw-source range as
0.26 to 0.27 deg/s; the runs recorded above are 0.26, 0.27, 0.26 and 0.28, so
the message is 0.01 low at the top of the range. Left for the next rewrite.

Reply posted 19:10Z
(https://github.com/ArduPilot/ardupilot/pull/33498#issuecomment-5703092575)
answering the AP-Review round and rmackay9. PR body updated the same day: the
gyro bias check paragraph, the new test description and table, and both
autotests in the checklist; the old "guard on the configured yaw source" row
is gone from the body but remains in the 2026-09-15 reply.
