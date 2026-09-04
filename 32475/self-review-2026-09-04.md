# PR #32475 - self-review, 2026-09-04

Pre-submission review of `pr-throw-mode-improvements` at f1ed87b9c1 against
merge-base 16f9f66379, followed by the fixes. Five parallel reviewers over the
diff plus four independent Codex passes (three cold, one verification). The
mechanical CI gate was clean before and after.

The review is recorded here rather than on the PR. Nothing was posted to
GitHub.

Three findings were settled by measurement in SITL rather than by argument,
and that is the part worth keeping: two of them contradicted what the code's
own comments and parameter documentation claimed, and one contradicted a
reviewer.

## What measurement changed

### A carrier drop fell to the ground

`aa956d2e2e` added an abort to `Throw_Wait_Throttle_Unlimited`: if
`throw_in_freefall()` goes false during spool-up, the state machine returns to
`Throw_Detecting` and the motors spool down. The gate is a ceiling on body
`|accel|`.

Body `|accel|` in a fall is drag, and drag grows with v^2. It reaches 0.5 g
somewhere around 10-16 m/s for a multirotor, which is one to two seconds of
falling. Past that the abort fires - and re-detection uses the same ceiling,
so it cannot re-arm.

Measured with the values `THROW_DROP_CNF`'s own documentation recommends for
carrier drops (0.5-1.0 s) and `MOT_SPOOL_TIME` at the top of its documented
range:

```
detected=yes  freefall_lost_count=1  recovered=no  final_alt=-0.0
```

The vehicle detected the drop, aborted during spool-up, and fell to the
ground with the motors shut down.

Fixed by requiring the vertical velocity to agree before aborting. A vehicle
that is still gaining downward speed is falling whatever the accelerometer
magnitude says; one that is not is being supported, which is the false trigger
the abort was for. `ThrowDropLongFall` covers it.

Severity, honestly: the recommended configurations in `../analysis` use
`MOT_SPOOL_TIME = 0.05`, not the 2.0 the harness used, and Rosser1/log32/34
measured body accel at 0.16-0.38 g during spool-up at 8-12 m/s descent - well
inside the gate. The failure needs a long enough fall before
THROTTLE_UNLIMITED that drag builds, which the recommended settings avoid. It
is still reachable: `MOT_SPOOL_TIME` defaults to 0.5 and its range allows 2,
`THROW_DROP_CNF` is recommended at 0.5-1.0 for carrier drops, and
ThrowDoubleDrop already had `SIM_SHOVE_Z` softened from -11 to -10.5 with a
comment blaming exactly this drag interaction. The fix only relaxes the abort,
and only when the vertical velocity says the vehicle is still falling, so it
cannot regress the validated configurations.

### THROW_ALT_DCSND climb-back - measured correctly, diagnosed wrongly

The target is `drop_release_alt_m - THROW_ALT_DCSND`, a fixed height below the
release point. Measured at the shipped default:

```
release_alt=55.58  lowest_alt=52.97  settled_alt=54.32
total_loss=1.25    climb_back=1.35
```

I read the 1.35 m climb-back as a defect and clamped the target to the current
height. **That was wrong and has been reverted.** `../analysis/topics/
throw_mode_drop.md` documents the climb-back as intentional, under "Target
Altitude and Climb-Back": it is trajectory-planned, cannot overshoot, never
exceeds the release altitude, and for hand drops (DCSND=0) recovering altitude
is the point - it preserves ground clearance. It is explicitly contrasted with
the old `cos_tilt` bounceback that `934bb8ad27` removed, where Rosser1/log43
dropped 2.5 m and then climbed 7 m *above* release. Rosser2/log22 flew the
intended behaviour: 3.13 m fall against a 3 m target, 0.28 m climb-back.

So the measurement was right and the interpretation was not. The number I
measured is the feature working.

What does survive is the **documentation**: the parameter said "Total altitude
lost in a drop is: freefall distance + uprighting distance + this value.
Typical total loss is 5-10m", which describes the upstream relative-to-current
behaviour, not this one. That is what made the measured 1.25 m look wrong. The
description now says what the code does, including the climb-back.

### The EKF source set was stranded

`throw_do_nextmode_handoff()` cleared `source_set_switched` unconditionally,
before applying `THROW_SRC_SET` and before `set_mode()`. With `THROW_SRC_INI`
set and `THROW_SRC_SET` left at its default 0, nothing restored the pre-throw
set and `exit()` was disarmed.

`THROW_SRC_INI`'s documentation recommends pointing it at a source set with no
horizontal aiding, so the vehicle finishes the throw with no horizontal aiding
and every position-requiring mode refused. Measured:

```
restore_msgs=0  completion_switch_msgs=0  loiter_accepted_after_throw=False
```

Fixed by clearing the flag only when `THROW_SRC_SET` actually claims the
source set. `ThrowSrcInitRestoredOnCompletion` covers it, and asserts LOITER
is accepted afterwards rather than just looking for the message.

### A reviewer's refutation that measurement overturned

One reviewer reported both spin autotests as vacuous, deriving a steady-state
gyro rate of ~10 rad/s from SITL's rotational drag - too low to exercise the
spin-scaled ceiling. The arithmetic used `400` where `SIM_Frame.cpp` has
`radians(400.0)`, a factor of 57.

Measured from the dataflash log of an actual `ThrowSpinTumbleDrop` run: peak
`|gyro|` 23.67 rad/s (1356 deg/s), and 70 IMU samples where only the
spin-scaled cap admits freefall against 6 where a plain 0.5 g gate does.

Settled properly by rebuilding with `drop_body_in_freefall()` neutered to a
plain 0.5 g check and re-running:

| test | neutered gate | covers |
|------|---------------|--------|
| `ThrowSpinDrop` | passes | the earth-frame OR-gate, which is what its comment claims |
| `ThrowSpinTumbleDrop` | fails | the body-frame spin ceiling |

Both tests have teeth, for the two different mechanisms their own comments
name. The finding was wrong and is recorded here so it is not rediscovered.

### One of my own findings, refuted the same way

I thought the `arming_check_throttle()` override let the vehicle arm in THROW
at full throttle, which would be live at the next mode change.
`AP_Arming_Copter::arm_checks()` still rejects
`get_pilot_desired_climb_rate_ms() > 0`, so the permitted band really is
0..mid+deadzone - which is what the change intended. No defect.

## Claims in the code that did not survive checking

These are all cases of the playbook's "self-consistency between description
and code": prose a reviewer reads alongside the diff, asserting behaviour the
diff does not implement.

- **The drop "distance cross-check" was the time check written twice.**
  `fall_confirmed` tested `0.5*g*t^2 >= 0.5*g*confirm_s^2`, which reduces to
  `t >= confirm_s` - identical to `time_confirmed`, with zero disagreement
  across every value swept. No altitude was read anywhere in the block, yet
  the comment said it "cross-validates that the vehicle actually fell the
  expected distance, not just sustained low-g on a smooth-flying carrier". It
  was also the only claimed defence against a false trigger. Replaced with a
  real velocity-change test.

- **The freefall ceiling cannot do what its comment promised.**
  `cap = 0.5g + 0.06*w^2` reaches 1 g at 9.04 rad/s (519 deg/s), so above that
  a vehicle reading a normal 1 g passes. The comment said "A stationary
  carrier (|a|~1g, w=0) is always rejected", true only at the w=0 it names.
  The drop path had also dropped `changing_height` and `no_throw_action`, and
  `THROW_ALT_MIN`/`MAX` default to 0, so nothing else stood in the way. Not
  reproducible in SITL, which has no held-and-spun state; the arithmetic is
  the evidence. The velocity-change confirmation now carries this.

- **The comment's history is real, but not reconstructible from the PR.** It
  said the ceiling "Replaces a fixed 1.5g ceiling". No commit in
  `16f9f66379..HEAD` ever contained one, which is why I first read this as
  false. It is not: `../analysis` records the fixed 1.5g tier as `c06a7252`
  and the physics ceiling that replaced it as `7ad2dc32`, both on the
  SmallFastDrone branch, driven by marmotte5/log2-c3 and SFD1/log55. The
  problem is narrower than I claimed - an upstream reviewer cannot verify any
  of it from the diff, and the cited log is private. Keep the physics, drop
  the branch archaeology and the log reference; that history belongs in the
  PR description.

  My related complaint that `r_max = 0.06` is "not derived from the log" also
  misread it: `../analysis` treats 0.06 m as a design *envelope* covering
  typical FC stacks, not a fit to log55 (which implies 0.017-0.048 m). An
  envelope above the observed values is the right shape. Withdrawn.

- **The `baro_ground_effect.cpp` change was a no-op.** `AP_GroundEffect`
  only latches `takeoff_expected` under `else if (land_complete)`, which is
  exactly the condition the new code used to *disable* the compensation. The
  deweight window the comment promised could never open. Reverted; the file is
  now byte-identical to upstream.

- **`THROW_DROP_AG` documented thrust it does not control.** "Multiplier on
  hover throttle... At 1.0, maximum arrest thrust equals hover (1g)". It
  multiplies the position controller's vertical speed and acceleration limits
  (5 m/s, 15 m/s^2); no hover throttle is read.

- **`THROW_NEXTMODE` omitted a value the code accepts.** ACRO is handled in
  the switch and used by `ThrowNextModeAcro`, but was missing from `@Values`.

- **The PR description cites a mode upstream does not have.** "THROW_NEXTMODE
  accepts Stabilize, AltHold and Acro (and VALT where built)". VALT is real -
  mode 29 on the SmallFastDrone branch, with three topic files in
  `../analysis` - but it is not in the tree this PR targets, so the claim is
  unverifiable for a reviewer. Same for the autotest comment citing
  marmotte/log1, which is a genuine log. Both removed from the upstream test;
  the PR description still needs the VALT clause dropped.

## Design problems fixed

- **The yaw lock latching mid-spin is deliberate.** `yaw_align_locked` is set
  the first time `|yaw_err| <= 30 deg` with no rate condition, so a fast spin
  latches it within the first revolution and the ride and slew branches become
  unreachable. I gated the latch on spin rate; **that has been reverted.**
  `../analysis/topics/throw_yaw_accuracy.md` records the same observation from
  drop2/log1 #2 ("still spinning ~25 rad/s through the realign - yaw-lock
  fired spuriously") and the decision: gate the *message*, not the lock,
  because gating the lock coasts the spin in the zero-torque ride branch
  instead of braking it onto the target, delaying the handoff to the timeout
  without improving the heading. `throw_yaw_converged()` already gates the
  handoff on the rate. Nine field spin-drops at 12-34 rad/s back the current
  behaviour; I had no measurement against it.

  Still open and unresolved by either of us: the ride branch triggers above
  120 deg/s while `get_slew_yaw_max_rads()` caps commands at 60 deg/s by
  default, so a "ride" command is clamped to at most half the actual spin and
  does apply torque. Either the threshold or the comment is wrong.

- **`HORIZ_POS_ABS` is the wrong test for this PR's own target case.** It is
  `doingNormalGpsNav && filterHealthy`, false for an optical-flow vehicle with
  a good relative position - the configuration the no-GPS work exists for. Now
  `copter.position_ok()`, which accepts a relative estimate and honours the
  EKF failsafe.

- **The handoff can fire while still descending.** The drop path exits
  HgtStabilise on a 3 s timeout with no height or velocity requirement, and
  PosHold then hands off. I added `throw_velocity_good()` to the handoff
  condition and **reverted it**: nothing bounded the wait, so on a vehicle
  that cannot arrest it would hold the mode indefinitely, and PosHold keeps
  running the height controller either way. Worth revisiting with a bound, but
  not on an unmeasured hunch.

- **2 Hz STATUSTEXT for the whole of every stage.** "Waiting for throw"
  repeated indefinitely while armed. Each call pushes into a queue that is 10
  deep on constrained boards (overwriting oldest), writes a MSG record to the
  dataflash log, and drives the CRSF transmitter display. Nothing waited on
  the repeats. Now one message per stage transition, which is what upstream
  did and what the tests actually use.

- **The OSD flash blanked a global.** `set_flight_mode_str("    ")` on
  alternate half-periods. That string is consumed by AP_OSD, CRSF telemetry,
  MSP, HoTT and the OLED display, so the flash blanked the flight mode on the
  transmitter too. Removed; the per-stage strings (THRW/THR!/THHT/THPH) stay.

- **A predicate with side effects on the logging path.** The THRO logging
  block called `throw_detected()`, which is non-const and latches
  `drop_confirm_start_ms`, `drop_release_alt_m` and the free-fall timers - at
  10 Hz, in every stage including while disarmed. It now logs the latched
  state instead of re-running the detector.

- Two float-to-`uint32_t` casts that a negative or extreme parameter could
  make undefined (`THROW_DROP_CNF`, the yaw align timeout) now clamp before
  the cast. The three redundant `stage = Throw_PosHold` assignments collapsed
  to one.

## Comment density

The aggregate comment ratio was never the problem - 0.56 against mode_flip's
0.50 and mode_brake's 0.58. The block *length* was: multi-line explanatory
paragraphs, which the Copter mode files essentially do not use.

| | blocks >= 5 lines | blocks >= 8 lines |
|---|---|---|
| `mode_throw.cpp` upstream | 1 | 1 |
| `mode_flip.cpp` | 1 | 0 |
| `mode_throw.cpp` before | 27 | 11 |
| `mode_throw.cpp` after | 14 | 3 |

The three remaining long blocks are the `@LoggerMessage` field metadata
(required), the freefall helper header, and the throw-direction estimator
header.

## Left for the history rewrite

These cannot be fixed with new commits and need `/prepare-for-push` with
rebase and amend.

- **Six of eleven commits panic at boot.** `ParametersG2::var_info2` carries a
  duplicate idx 21 (`SURFTRAK_GLDST` and `THROW_DROP_AG`) in `910ef46774`,
  `1a4e61a3d2`, `9cf42aee88`, `f1c46abff3`, `aa956d2e2e` and `c405760717`;
  the last two also carry idx 64 and 65, past the 6-bit group level.
  `AP_Param::check_group_info()` calls `FATAL` -> `panic("Bad parameter
  table")`, from `AP_Vehicle::setup()` on every boot. Bisect is broken across
  most of the branch.

- **The series develops the feature twice.** `aa956d2e2e` is a 714-line second
  pass over all five earlier `Copter:` commits, and `c405760717` /
  `4f2903810a` are fix-ups of it. `c405760717` re-adds an `AP_GROUPINFO` that
  `aa956d2e2e` deleted - a regression introduced and repaired inside one PR.
  Squash map: `c405760717` and `4f2903810a` into `aa956d2e2e`; `f1ed87b9c1`
  into `f1c46abff3`; ideally `aa956d2e2e` into the four commits it revises.

- **`c405760717` carries a dead cherry-pick trailer** pointing at a commit
  that exists only on `fossuav/SmallFastDrone-4.7.1-beta`. It resolves to
  nothing for a reader and leaks a private branch name.

- **`75be73908e`'s message has non-ASCII** (`±`, `°`) on three lines. The
  mechanical gate missed this: its `BANNED_CHARS` covers quotes, dashes and
  arrows but not those.

- **The PR description** does not follow `.github/PULL_REQUEST_TEMPLATE.md`
  (Summary / Classification & Testing / Description), still claims VALT, and
  does not mention that the THRO log field `AccEfZ` was renamed to `AeZ`.
  That rename is forced by the 64-character label limit, but only because the
  new fields are `TYaw`/`YSrc`; `TYw`/`YSr` fits at exactly 64 and would leave
  the existing field alone.

## What reading ../analysis changed

The review above was done without the development record in
`../analysis/topics/throw_mode_drop.md` and `throw_yaw_accuracy.md`. Reading
them afterwards overturned four conclusions, all in the same direction: I had
treated deliberate, flight-validated decisions as defects because the PR diff
does not carry the reasoning behind them.

| Finding | After reading |
|---------|---------------|
| THROW_ALT_DCSND climb-back | intended and validated; change reverted, doc still corrected |
| Yaw lock latches mid-spin | considered and rejected with a stated reason; change reverted |
| "Replaces a fixed 1.5g ceiling" is false history | real history on the feature branch; only unverifiable from the PR |
| `r_max = 0.06` not derived from the log | it is an envelope, not a fit; withdrawn |
| VALT does not exist | mode 29 on the feature branch; not in the upstream tree |
| ThrowYawAbsolute's 180 deg target is degenerate | it is the regression case for the timeout sizing; restored |

That is the cost of reviewing a long-lived feature branch by its diff alone.
The reasoning exists, in detail, and none of it is in the commits - which is
also the actionable point for the PR: a reviewer at the dev call will be in
exactly the position I was.

Two claims in `../analysis` are wrong and should be corrected at the source,
because they are where the code comment and the parameter documentation got
them from:

- `throw_mode_drop.md`, drop detection: "The timer also cross-checks that the
  vehicle has fallen the expected freefall distance for that time (d =
  0.5*g*t^2), validating that freefall is genuine rather than sustained low-g
  on a smooth-flying carrier." The implementation compared the same elapsed
  time against itself and read no altitude at all. There was no cross-check
  until this review added one.
- `throw_mode_drop.md`, parameter table: "THROW_DROP_AG | Drop arrest
  aggressiveness - hover throttle multiplier (1.0-4.0)". The tuning section a
  few hundred lines earlier has it right - it scales the position
  controller's vertical speed and acceleration limits - and the code agrees
  with the tuning section.

## Not covered

No hardware. No flash-size measurement on a 1 MB board, which matters:
`MODE_THROW_ENABLED` defaults to 1 with no hwdef disabling it, and
`mode_throw.cpp` went from 333 to about 1040 lines. The upward-throw path is
barely exercised - every new autotest is a drop. The IMU direction-finding
yaw path (`THROW_YAW_TYPE` 1 and 2) still has no test; only Absolute is
covered.

One estimator issue was found and left alone as out of scope for this pass:
`throw_dir_update()`'s held-still gate tests accelerometer *magnitude* only,
so a specific force of 0.8 g vertical plus 0.6 g horizontal has magnitude
exactly 1 g and passes with the anchor attitude 37 degrees wrong. A carrier in
a sustained coordinated turn qualifies. Gravity then leaks into the horizontal
integration fast enough to cross the 1.5 m/s confidence threshold in 0.25 s,
and the fabricated heading is logged as high-confidence `ImuDirection` in
`THRO.YSrc`. This wants a real fix before the direction-finding yaw modes are
recommended.

## Files

```
32475/
  README.md                    <- orientation, flight history
  self-review-2026-09-04.md    <- this file
  data/
    measurements.md            <- the four SITL harness results quoted above
    harness.diff               <- the throwaway autotest harness used
```
