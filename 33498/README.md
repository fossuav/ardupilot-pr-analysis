# PR #33498 - inhibit Z gyro bias from optical flow when there is no yaw source

Analysis archive for [ArduPilot/ardupilot#33498](https://github.com/ArduPilot/ardupilot/pull/33498).
Branch `pr-gyro-z-unobservable-without-yaw` (andyp1per fork), base `master`,
head `17f19f6202` (2026-09-02). All evidence is from real flights on a 4-inch
optical-flow quad (MatekH743, ARK Flow, no compass in the flow source set);
numbers are cited inline and no logs are committed.

## Status (one line)

One-commit correctness fix, flight-validated on the airframe that exposed it
and reconfirmed on a later flight; no SITL reproduction yet (see Reproduce).

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

## Branches and people

- `pr-gyro-z-unobservable-without-yaw` - the PR branch (one commit).
- Author: @andyp1per. No review yet.
- Related: #33497 (the same airframe's flow half-rate fault, fixed first so
  this could be seen), #33484 (per-axis lockout recovery).
