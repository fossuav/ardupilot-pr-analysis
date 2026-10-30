# PR #32475 - Throw mode improvements (drop detection, uprighting, yaw, sources)

Analysis archive for [ArduPilot/ardupilot#32475](https://github.com/ArduPilot/ardupilot/pull/32475).
Branch `pr-throw-mode-improvements` (andyp1per fork), base `master`,
supersedes #32393. Every number here is from real drops on the SmallFastDrone
branches; no logs are committed. Vehicles are named by board.

## Status (one line)

Open since 2026-06, awaiting review. Six new parameters (THROW_DROP_AG,
THROW_DROP_CNF, THROW_SRC_INI, THROW_SRC_SET, THROW_YAW_TYPE, THROW_YAW_DEG).
Flown across roughly thirty drops on six airframes, from hand drops at 1 m to
releases from a carrier aircraft.

Self-reviewed 2026-09-04 (see `self-review-2026-09-04.md`), fixed, history
rebuilt and force-pushed. Head is now `8b5882e6d1`, eight commits by feature.
Two of the three measured failures were real - a carrier drop fell to the
ground on the spool-up abort, and THROW_SRC_INI stranded the EKF source set -
while the third, the THROW_ALT_DCSND climb-back, turned out to be the design
working and the change was reverted. The old series had 9 of 11 commits
panicking at boot on a duplicate parameter index present from the first
commit. The PR description has not been updated.

## The problem

Upstream throw detection for a drop reads EKF-derived velocity and
earth-frame acceleration and never checks the one thing that defines a
release: body-frame |accel| near zero. Two carrier drops on that logic,
both from a carrier aircraft (MatekH743 quad, not committed):

- log32: three false triggers with the vehicle still attached at 0.94 g.
  The carrier's 17 m/s exceeded THROW_HIGH_SPEED (5 m/s); the no-throw
  gate (<1 g) passed in turbulence. Released at ~10 m AGL, recovered to
  67 m, then a false LAND_COMPLETE disarmed it in the air.
- log18: never armed (a battery pre-arm blocked it; see #32401), dropped
  with motors off, 9 s to impact.

The rest of the PR is what it took to make the drop path work from
inverted, spinning and tumbling releases, and to hand off cleanly.

## The conclusion and why

Detect a drop from the body-frame IMU with a confirmation window, verify
freefall again during spool-up at zero throttle, upright at zero net
throttle, and only then arrest. Every one of those choices was forced by a
log, and two of them were revised twice. The gate that survived admits
body |a| up to 0.5 g + r_max * w^2 (r_max = 0.06 m): 0.5 g at rest, so a
carrier at 1 g is always rejected, 1.9 g at 15 rad/s, 6 g at 30 rad/s.

## Key findings

1. Confirmation time must not be tied to the descent target. The original
   timer was sqrt(2 * DCSND / g): with THROW_ALT_DCSND=3 that is 782 ms,
   which on an inverted hand drop from 11 m AGL consumed the altitude
   budget and the vehicle hit the ground in HgtStabilise at t=0.775 s
   (14 g spike; MicoAir743v2 quad, log25). The same vehicle with a
   100 ms window recovered the same drop in 3 m with 8 m to spare (log24).
   THROW_DROP_CNF is now independent of THROW_ALT_DCSND.

2. Uprighting throttle must be zero. hover * AG * cos(tilt) produced 2.8x
   hover once level on a high-thrust quad and launched it 7 m above the
   carrier (MicoAir743v2 quad, log43). With zero net throttle and attitude
   authority from ATC_THR_MIX_MAX only, an inverted (178 deg) hand drop
   uprighted in 300 ms with no attitude or altitude bounce, 4.56 m total
   fall (MambaH743v4 quad, drop session 2, log2). The arrest is deferred to
   the position controller, which plans the climb-back and cannot
   overshoot.

3. The descent-distance check cannot use EKF height without velocity
   aiding. With THROW_SRC_INI on a no-aiding set the velocity state drifts
   from pure accelerometer integration: 70 m/s after 58 s on a hovering
   carrier (MicoAir743v2 quad, log40, stuck in Uprighting 4.5 s until the
   pilot took over), 506 m/s after 220 s (log22). The check now falls back
   to 0.5 g t^2 when const_pos_mode is set.

4. Spin. Yaw spin at release loads the IMU with centripetal force w^2 r at
   the mount offset, so body |a| reads ~1 g through a genuine freefall.
   Three iterations:
   - Body-only 0.5 g gate at spool-up: two drops at ~20 rad/s bounced
     Detecting <-> Wait_Throttle_Unlimited (5 and 3 "freefall lost"
     resets) and never armed; body accel in freefall was (-9.20, +4.73,
     -0.10) m/s2, 1.05 g, at 21.9 rad/s (MambaH743v4 quad, 2026-05-02
     session, log4/log6). Fix: earth-frame Z < 0.5 g AND gyro > 10 rad/s
     as a fallback.
   - That fallback fails when the spin axis is not vertical. At 26 rad/s
     with a tumble, 0 of 640 IMU samples were below 0.5 g over 2 s of
     freefall and earth-Z oscillated +/-10 m/s2 at half the spin period,
     resetting the confirmation timer at sub-sample rate; "Throw detected"
     fired 380 ms before disarm, after impact (MambaH743v4 quad, 2026-05-04
     session, log2). Fix: admit body |a| < 1.5 g when gyro > 15 rad/s.
     Nine subsequent spin drops at 12-34 rad/s recovered with zero resets,
     body |a| at detection 0.36-1.03 g, lateral peak 143 m/s2 (2026-05-23
     sessions).
   - A multi-axis tumble at a combined 25-30 rad/s put body |a| at
     15-30 m/s2, above the fixed 1.5 g, while the off-vertical axis broke
     the earth-Z fallback; detection stalled ~900 ms and ~3.6 m
     (MicoAir743v2 quad, log55, 2026-05-27). Fix: the physics ceiling
     0.5 g + 0.06 w^2 in both throw_detected() and throw_in_freefall().
   Recovery time is set by how fast the vehicle bleeds spin, not by the
   gate: the same session had a 29.6 rad/s drop recover in 0.15 s.

5. Yaw alignment must not fight the spin and must not be a stage. Driving
   an absolute yaw target through input_quaternion from Uprighting on, with
   ATC_RATE_Y_MAX=0 and a stiff tune (ATC_ANG_YAW_P=19.5), fought residual
   spin with full attitude-error torque. A separate YawAlign stage after
   PosHold fixed the feel and added 0.5-2.2 s. Folded into HgtStabilise and
   PosHold (ride above 120 deg/s, rate-limited slew, lock inside 30 deg),
   yaw locked at 0.77-1.09 s after detection on every throw, before height
   arrest completed at 1.16-1.52 s (MambaH743v4 quad, 2026-05-04 session).
   The slew cap reads ATC_RATE_WPY_MAX so one parameter governs it.

   Large rotations then exposed the handoff: a 180 deg absolute target
   reached ~62 deg and timed out, because a flat 2.5 s timeout is shorter
   than 180 deg at the 60 deg/s slew (SITL, ThrowYawAbsolute), and a lock
   at the 30 deg window handed a heading-holding next mode a permanent
   residual. The timeout is now sized to the rotation (margin + |err|/slew,
   floor 2.5 s, cap 8 s so a slow yaw tune cannot stall it for tens of
   seconds) and the handoff waits for 5 deg and gyro Z under the ride
   threshold, so a fast spin sweeping through the target cannot hand off
   mid-spin.

6. Yaw accuracy is limited by dead reckoning, not direction finding. The
   throw runs yaw-unaided (THROW_SRC_INI to a set with no yaw source) and
   the compass realign at completion measures the drift directly: +31 deg
   after a 24 s pre-release hold with reorientation, -7.5, <5 and +4 deg on
   short holds (MambaH743v4 quad, 2026-05-23 sessions). A 1% gyro scale
   error at 30 rad/s for 1 s is already 17 deg.

7. A throw that is entered and not completed must restore the source set.
   ModeThrow had no exit(), so a pilot who entered THROW, never threw, and
   switched out left the vehicle on the throw-phase set for the rest of
   the power cycle. On a MicoAir743v2 quad (log36, not committed) that set
   was baro-height-only with no velocity source; on a later climb the EKF
   vertical velocity read +1.2 m/s (descending) against GPS -3 to -7, VALT
   held hover throttle against a full-down stick, the vehicle climbed 54 m,
   and the flight was prolonged into a battery-sag motor desync and crash.
   exit() now restores the pre-throw set; the completion handoff still
   applies THROW_SRC_SET.

8. The completion set must aid the next mode. ThrowDropSourceSwitch
   originally switched to SITL's default no-aiding SRC2 and hung on disarm:
   LAND's position controller chased ~1 m/s of dead-reckoned drift on the
   ground and the land detector never settled. That is correct detector
   behaviour; the test now gives SRC2 GPS aiding and the parameter
   description says so.

9. Two things seen on throw launches that are not throw bugs, for anyone
   reading field reports: an ARK_fpv quad configured props-in on a
   props-out build spun up to 24 rad/s in yaw and crashed from 14 m
   (reversed yaw torque, FRAME_TYPE); and a sibling with 56 m/s2 of
   throttle-correlated vibration limit-cycled in the altitude-hold next
   mode (ThO 0.0 <-> 1.0 at ~1 Hz) and stopped the instant the pilot took
   Stabilize.

## Admitted gaps

- The direction-of-travel yaw source (THROW_YAW_TYPE 1/2, source 1) has
  not been validated in flight. On the logged type-1 throws GPS showed
  5-9 m/s at release but the IMU-integrated direction never reached its
  1.5 m/s gate, so every one silently used the entry-yaw fallback (source
  3). THRO.TYaw/YSrc now log the resolved target and source; a re-fly with a
  deliberate horizontal component is needed to test direction finding on
  its own.
- The mid-stick arming exemption applies only with THROW_MOT_START=0. With
  motors idling (=1) a MicoAir743v2 quad was refused with "Throttle (RC3)
  is not neutral" although THROW never applies the stick to the motors
  before detection (t25 log, not committed). Not addressed in this PR.
- Five autotests that exercise the spin, tumble, yaw-absolute, next-mode
  and abort-restore paths exist on the SmallFastDrone branch and are not in
  the PR.
- VALT as a next mode is not upstream; the PR whitelists it only where
  built.

## An upward throw's position requirement follows THROW_NEXTMODE (2026-09-29, local)

Local on `pr-throw-mode-improvements`, not pushed: `1796d249cd` (fixup of
`e45c1a3cde`, "allow throw without GPS and add next mode options") and
`23b05a4f7d` (autotest ThrowUpwardNoPositionNextMode), on top of
`8b5882e6d1`. Found from #32514's review: that PR's EKF failsafe counts a
missing position whenever the mode's `requires_position()` is true, and an
upward throw returned true whatever it handed over to.

`requires_position()` was `throw_type != Drop`. It is now
`throw_type != Drop && nextmode_requires_position()`, the predicate run()
already used for its PosHold message (not STABILIZE, ALT_HOLD or ACRO),
moved into a helper. Upward detection reads vertical velocity and
earth-frame acceleration, so the throw itself never needed a horizontal
position; PosHold already ran without one when `position_ok()` was false.

SITL, tier 2, 2026-09-29: upward throw, THROW_NEXTMODE 2, THROW_SRC_INI 2
on a set with no horizontal source, armed in THROW for 20 s, then thrown.

| accessor | ekf_check | result |
|---|---|---|
| `throw_type != Drop` | master | refused at arming, "Arm: Need Position Estimate" |
| `throw_type != Drop` | #32514 `b1743055b1` | refused at arming, same |
| with next mode | master | passes; "EKF variance: position lost" and a report-only "EKF Failsafe", no mode change |
| with next mode | #32514 | passes, no EKF failsafe at all |

ThrowMode, ThrowModeNoGPS, ThrowSrcInitRestoredOnCompletion,
ThrowNextModeAcro, ThrowDropSourceSwitch and ThrowAbortRestoresSourceSet
pass with the change, alone and with #32514's ekf_check stacked. The 20 s
"no failsafe action" assertion cannot fail at either accessor on either
ekf_check (the old accessor never arms), so it guards against a later
change, not this one. The commit message of `e45c1a3cde` still says an
upward throw keeps the position requirement and wants rewording at the
squash.

Pushed 2026-09-29 as `5f333a9acb`: the fixup squashed into `a12635f77f`
(was `e45c1a3cde`) with its message reworded to match, then rebased onto
master (444 behind), nine commits. Copter builds at every commit; all 13
Throw* autotests pass at the head; mechanical gate clean. Nothing
re-measured beyond that; the table above was taken at `8b5882e6d1` plus
the change.

## What is here

```
32475/
  README.md                    <- this file
  self-review-2026-09-04.md    <- pre-submission review and the fixes it drove
  data/
    measurements.md            <- SITL harness results behind that review
    harness.diff               <- the throwaway autotest harness used
```

No real-flight logs committed: every measurement in this file is from a real
drop, and the SITL numbers live in `data/`.

## Reproduce

```
git checkout pr-throw-mode-improvements
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.ThrowMode,ThrowDoubleDrop
Tools/autotest/autotest.py --no-configure test.Copter.ThrowModeNoGPS,ThrowDropSourceSwitch
```

The spin gate can be exercised in SITL with the recipe used on the
SmallFastDrone branch: shove the vehicle to 50 m as ThrowMode does, apply
SIM_TWIST_Z=30 rad/s2 for 12 s (saturates the 35 rad/s gyro clamp before
the descent) with SIM_IMU_POS_X=0.05 so the spin becomes body-frame
centripetal acceleration, and assert zero "Throw: freefall lost, resetting"
messages between detection and recovery. Adding SIM_TWIST_X/Y tilts the
spin axis off vertical and defeats the earth-frame fallback, isolating the
body-frame ceiling.

## Branches and people

- `pr-throw-mode-improvements` - the PR branch. Development history on
  `SmallFastDrone-4.6-AltHoldv2` and `SmallFastDrone-4.7-beta`.
- Related open PRs: #32514 (EKF failsafe gate reset on source-set change,
  which THROW_SRC_INI needs on GPS vehicles), #32401 (pending arm, the
  other half of the log18 crash), #32391 (LEVEL arming check: "Arm:
  Leaning" blocked re-arming on the carrier in log32).

## THROW_SRC_INI / THROW_SRC_SET move no lane under SRC_PER_CORE (2026-10-03)

Found by inspection while checking the SmallFastDrone 4.7.2-beta
explainers, not flown or tested. Throw's source switches call
`set_posvelyaw_source_set()` without `select_lane`, so with
`EK3_SRC_OPTIONS` bit 3 they announce a source-set change and move no
EKF core. Recorded with the lane-selection change it belongs to:
`../34456/README.md`, "Known and deliberately not fixed here".


## 2026-10-30: AP-Review blockers fixed, spin tests made to recover (local)

Local, not pushed: eleven commits on `r1030/32475-2` on top of the PR head
`f7a5aeb84f`, from the AP-Review report of the same day (review 4).
`r1030/32475` holds a first copy of `97a2b42e8c` whose message misstated
the fall (4.7 m for about 3 m); the branch was rebuilt by cherry-pick
rather than amended, and the old one can go.

| commit | change |
|---|---|
| `97a2b42e8c` | Uprighting's descent gate ends with the 3 s uprighting timeout |
| `b9639677a5` | autotest ThrowDropArrestedShort |
| `e19dbe4b31` | a drop confirmation window that has run 500 ms unconfirmed restarts |
| `d2b31e2b2e` | the velocity-change confirmation applies in constant position mode |
| `9fa2492fb8` | autotest ThrowDropHeldSpinNoPosition |
| `b98c23a758` | requires_position() is true while PosHold runs NE control |
| `b4a0c300f8` | autotest ThrowDropEKFFailsafePosHold |
| `70499530b0` | completion settles the source set once, then waits for position_ok() |
| `c89b276f69` | autotest ThrowSrcSetHandoff |
| `2e8b37c671` | ThrowSpinDrop and ThrowSpinTumbleDrop end the twist at release, check recovery |
| `917e24aa96` | the early returns in throw_detected() close the confirmation window |

All four blockers reproduced in SITL at `f7a5aeb84f` (the bot had the
second and fourth by code and harness only), and every new test fails
there and passes at the tip:

- DCSND=5, a short toss released 2.8 m up that lands about 3 m below the
  release point: stuck in Uprighting on the ground until the harness
  gave up 12 s later; now leaves it 3.0 s after Uprighting starts.
- GPS-free (XKF4.SS bit 7 set throughout), held at 1g spinning at
  14 rad/s with a 3 cm IMU offset: detected as a drop 0.8 s into the
  spin; now not detected over 3 s, and the release detected 0.2 s
  after.  GPS-free drops in ThrowModeNoGPS and
  ThrowSrcInitRestoredOnCompletion confirm 0.16-0.18 s after their
  window opens, against 0.10-0.11 s on the timer alone (THRO is 10 Hz).
- GPS lost while a drop holds position in throw: report-only "EKF
  Failsafe"; now "changed to Land Mode".
- THROW_SRC_INI on a no-aiding set, NEXTMODE LOITER: "requires position"
  and no retry for THROW_SRC_SET 0 and 1, nothing restored with
  NEXTMODE 18; now restored or switched at completion and LOITER
  1.07-1.16 s later, when the EKF failsafe from the throw set clears.

Found on the way, and the reason for `e19dbe4b31`: the confirmation
window starts at the first low-g sample and never moved, and the
velocity test is cumulative from it.  A spin above about 9 rad/s opens
it while the vehicle is still held, so a release after a few seconds'
hold has to make up the whole held time at half a g.  At the PR head this
was already live on the aided path: GPS, held 2.6 s spinning, then let
go - never detected, ground at 17 m/s.  Removing the constant position
exemption alone would have carried it there too (measured: same result,
GPS-free).  The restart length copies the upward path's 500 ms window.
A restart every 100 ms was tried first and misfired on the held vehicle,
but only after the AHRS had diverged, so SITL cannot choose between the
two; a window judged every 100 ms gives a jostled, spinning vehicle five
times the chances, which is a judgement, not a measurement.  The restart
also cut ThrowSpinDrop's height loss from 24 m to 5 m, since that test's
twist starts while the shove still holds the vehicle.

The SITL AHRS does not survive a sustained spin with an IMU offset.
With GPS it left the true attitude 1.6 s into a 24 rad/s hold, 5.1 s
into 28 rad/s and 3.5 s into 14 rad/s; GPS-free it lasted 6.5 s at
25 rad/s and stayed true through 5-6 s at 14 rad/s.  The EKF vertical
velocity follows the attitude.  The held-spin test therefore runs
GPS-free at 14 rad/s for 3 s and checks the attitude at the end; a
detector built on the AHRS cannot be judged past that.

The two spin tests ran their twist for 12 s, driving the spin past the
35 rad/s gyro clip (AHRS 231 and 339 deg off truth) into ground strikes
at 16 and 18 m/s that they passed through.  With a 1 s twist they lose
5 m and 17-18 m from 52-56 m and hold height in LOITER.  Teeth kept: with
no spin term in the body ceiling TumbleDrop fails ("freefall lost") and
SpinDrop passes on the earth-frame fallback; with that fallback gone
too, both fail.

Fix 6 is not reproduced: an ATTITUDE_VALID or VERT_POS gap while a
window is open needs a multi-second height-source loss or all three
innovation tests failing at once.

All 17 Throw autotests pass at `917e24aa96` (binary
f782a074235cc04c8e54756d855eaae7); mechanical gate one note (diff size),
branch conventions clean.  Not done, as asked: the THROW_ALT_DCSND
meaning, the stale XY latch on rearm, the THPH OSD overwrite, and the
SIM_IMU_POS reboot comments.  The PR description still does not say
that THROW_ALT_DCSND is now measured from the release point.  Draft
description in `description.md` alongside.

## 2026-10-30: follow-up to a cold read of those commits (local)

A cold read of the eleven commits found nothing blocking and six
should-fix items.  All verified against the code before changing it;
ten more commits on `r1030/32475-2`:

| commit | change |
|---|---|
| `85c188352e` | per-throw state reset when throw is armed again |
| `2217a01b9d` | autotest ThrowDropTwiceWithoutReentry |
| `c7a4fab88c` | GPS-free windows with no spin in them keep to the timer |
| `2b6da5c316` | held-spin test: spin checked at the end of the hold, 0.6 s bound |
| `7b7f554b30` | PosHold drops to level before a GPS-free next mode; nextmode() helper |
| `068e06e4fb` | autotest: failsafe into ALT_HOLD reports, staying in throw lands |
| `dee6af0092` | the handoff's wait for a position is announced and capped at 5 s |
| `3b5e6d3f4d` | autotest: wait and refusal; SRC_SET 3 instead of 1, anchored match |
| `1db73d5496` | THROW_UPRIGHT_TIMEOUT_MS shared; THROW_ALT_DCSND documents the cap |
| `1d74f34a28` | autotest: spin tests assert the spin rate at detection |

- Stale latch: reproduced at `917e24aa96`.  A short toss ending on the
  ground in throw, disarm, re-arm with no horizontal aiding and
  NEXTMODE ALT_HOLD: "Internal Errors 0x100000" (flow_of_control,
  AC_PosControl line 707), no handoff, "PreArm: Internal errors" after.
  With the reset on Disarmed to Detecting: ALT_HOLD, arming fine.
- Plain GPS-free windows: instrumented builds show both the timer path
  and the velocity path confirm ThrowModeNoGPS and
  ThrowSrcInitRestoredOnCompletion 100 ms after the window opens.  The
  0.16-0.18 s against 0.10-0.11 s in `d2b31e2b2e`'s message was THRO's
  10 Hz logging, not a slower confirmation; the change guards against
  an unaided vertical velocity that SITL does not make drift.
- Failsafe into a GPS-free mode: with FS_EKF_THRESH dropped during a
  slow yaw alignment, `b98c23a758`'s design went to LAND; now a
  report-only failsafe, demanded tilt from position control (up to
  0.37 deg) to level within 0.6 s, then ALT_HOLD.  nextmode() asks the
  mode itself whether it needs a position, so LAND no longer counts as
  one - an upward throw into LAND arms without a position.
- Handoff wait: completion on the no-aiding set with NEXTMODE LOITER
  gave no message and no refusal 20 s on; now "Throw: Loiter waiting
  for position" and "Mode change to Loiter failed: requires position"
  5.00 s later, staying in throw, which is what a refused handoff has
  always done.  With a position coming back, LOITER at 1.0-1.2 s.
- The held-spin release took 0.2-0.4 s over four runs: the release
  lands anywhere in a 500 ms window, worst case about 0.35 s, so the
  suggested 0.5 s bound would be flaky and 0.6 s is used.
- Not done: targeting MIN(release - DCSND, current) after the gate times
  out is a no-op, since release - DCSND is already below a vehicle that
  stopped short.  MAX would hold a landed or hand-caught vehicle at its
  height under hover thrust instead of driving it to minimum throttle;
  that is Andy's call.  `7b7f554b30`'s subject is 75 characters
  (pr_review note); left for the squash rather than rebuild the branch.

All 18 Throw autotests pass at `1d74f34a28` (binary
6bd22c7895683d9ddaef8aae87b1bfe9).  Mechanical gate: the diff-size note
and the subject-length note above; branch conventions, flake8 and
astyle on the new lines clean.

## 2026-10-30: round 3, a Codex cold read of round 2 (local)

Two blockers and four should-fix items, all verified against the code
first; eight more commits on `r1030/32475-2`:

| commit | change |
|---|---|
| `d7940a3310` | next-mode position need by mode number; throw refuses after the wait |
| `f19acb39fc` | autotest ThrowNextModeAutoStaleSubmode |
| `3204452cdb` | 100 ms settle after completion changes the source set |
| `5e72c35001` | per-throw setup (THROW_SRC_INI, direction capture) re-run on disarm |
| `f990fd5d1a` | autotest: re-armed throw back on its THROW_SRC_INI set |
| `b4e6b04158` | comments and THROW_ALT_DCSND doc match the code |
| `34163b2205` | autotest: held-spin release timed from the log; failsafe in throw |
| `f48024f489` | autotest: held-spin detection checked before the held-state checks |

- Stale AUTO submode (blocker): `7b7f554b30` asked the next mode's
  object, and AUTO last left in NAV_ATTITUDE_TIME says it needs no
  position until init() resets it - after set_mode() has already asked.
  An AUTO mission left by LAND in that submode, then a drop into AUTO
  with no aiding until completion: AUTO took over in the restore's loop,
  a second before the EKF had a position, at the PR head and at
  `1d74f34a28`; now throw waits and AUTO takes over 1.1 s later.  The
  wait's end no longer calls set_mode(), whose check reads the same
  stale answer; throw says "no position for X, staying in throw".
- Same-loop source set (blocker): measured, and the settle cannot change
  the case the finding names.  Aided through the throw, THROW_SRC_SET to
  an unaided set, NEXTMODE LOITER: LOITER at +0.00 s before, +0.10 s
  with the settle, and in both the EKF reports a dead-reckoned position
  until 6.8-7.0 s after the switch, then the EKF failsafe lands it.
  Only checking the completion set's configured sources would stop that,
  which means vehicle code reading EKF source configuration (ARCH-3).
- Re-arm setup: the disarm now runs entry's setup, so the second throw
  is back on THROW_SRC_INI (A/B: set 2 not reapplied before) and its
  completion restores again, covering completion_started.  The entry
  velocity, yaw and direction integrator are re-captured with it but no
  test reaches them, and the drop_confirm_start_ms reset is not covered.
- The held-spin test had measured the parameter round trips, not the
  detector: from the test side the delay read 1.00 s once the time was
  taken before the release, and the earlier 0.2-0.4 s readings were
  taken after detection had already happened.  From the log, SIM_SHOVE_Z
  to 0 against THRO leaving Detecting: 0.2-0.4 s over four runs.
- At the PR head every new or changed test fails; the failsafe test's
  ALT_HOLD case passes there, as the PR head only ever reported for
  drops.

All 19 Throw autotests pass at `34163b2205` (binary
2aa5d219b82ff0120eb95e20187fb7f1); `f48024f489` only reorders one test,
which passes.  Gate: diff size, and subjects over 72 characters on
`7b7f554b30` (75) and `f19acb39fc` (73), left for the squash; branch
conventions, flake8 and astyle on the new lines clean.  The reviewer's
body-ceiling point on `1d74f34a28` is kept as a note, as asked.

## 2026-10-30: round 4, last small round (local)

The round-3 cold reads called the same-loop source set check blocking
again; that is the aided-to-unaided case already measured, left as
Andy's decision and not changed further.  Three should-fix items, three
commits on `r1030/32475-2`:

- `f9ab87b101`: throw_setup()'s early return while the THROW_SRC_INI set
  is still in use also skipped the direction integrator and recovery
  target reset, which do not depend on the set.  A throw detected with
  THROW_YAW_TYPE 3 and disarmed in the air, then re-armed: the new
  Detecting stage logged the aborted target (YSrc 4, TYaw 90) at
  `f48024f489`, none with the fix.  Test leg in
  ThrowDropTwiceWithoutReentry (`15001ff83f`).
- `20f3216987`: ThrowNextModeAutoStaleSubmode collects only from the
  drop's detection, checks throw still holds when the wait is announced,
  and checks from the log that AUTO came only after the EKF failsafe
  cleared (0.89 s after the wait began).  ThrowDropHeldSpinNoPosition
  checks for a false detection again after its attitude checks.  Both
  fail before their fixes at the intended check.

All 19 Throw autotests pass at `20f3216987` (binary
9e1f5623d089300901ea6463d1b53b04).  Gate unchanged: the diff-size note
and the two long subjects; branch conventions, flake8 and astyle clean.

Pushed to andyp1per f7a5aeb84f -> 60cee67154 (a fast-forward from
r1030/32475-4, rebuilt by cherry-pick with three messages reworded, one
test commit split and four commits added; r1030/32475-2 at 20f3216987 is
kept). Open for Andy: the hand-off to a next
mode that needs a position after THROW_SRC_SET switches to an unaided set.
EKF3 keeps reporting a dead-reckoned position for about 7 s after the
switch, so the 100 ms settle (3204452cdb) cannot hold the hand-off. LOITER
takes over and the EKF failsafe then lands it. Closing it means throw
reading the completion set's source configuration (ARCH-3).

## 2026-10-30: round 5, final state on `r1030/32475-3` (local)

None of `r1030/32475-2` was pushed, so the final state is a fresh branch,
`r1030/32475-3`, cherry-picked from `f7a5aeb84f`; `-2` is kept as it was.
The 31 commits up to the aborted-throw test carry over with identical
trees; three messages changed: the two long subjects (now 66 and 70
characters) and `f9ab87b101`'s, which now says only the integrator half
of that reset can change a flight, that no SITL test reaches it (the
first held-still sample re-anchors it), and that entry velocity and yaw
survive an aborted throw by design.  `20f3216987` is split into its two
test fixes, ending on the same tree.

On top, from a Claude cold read (Codex out of quota):

- `f65c724730`: the "freefall lost, resetting" path now resets the
  direction integrator too.  Not reproducible: a vehicle caught during
  spool-up is held still and re-anchors at once either way.
- `041de0484b`: the stale-AUTO test's assert_mode('THROW') was
  tautological and raced the 1 Hz heartbeat (AUTO 0.9-1.0 s after the
  message); gone, and the log check requires MODE.Rsn THROW_COMPLETE.
- `c2e8e0e66a`: the held-spin log loop fails on any THRO stage past
  Detecting before SIM_SHOVE_Z reaches 0, covering the whole hold; with
  the earlier checks taken out it alone catches the PR head's false
  detection.  The redundant statustext recheck is gone.
- `3904522d78`: the aborted-throw leg claims only what it can see (the
  logged target), checks no source set message came between abort and
  re-arm (so setup's early return ran), and waits for arming checks
  after the impact.  Still fails before the reset, passes after.

The same-loop source set point raised again by two reads is the
aided-to-unaided case already measured; left as Andy's decision.

All 19 Throw autotests pass at `3904522d78` (binary
5decdef9ecf455e6bdc14813fe8f27d0).  Gate: the diff-size note only;
branch conventions, flake8 and astyle clean.

## 2026-10-30: round 6, two small fixes after the last cold read

A cold read of the round-5 commits found f65c724730's spool-up reset left
the logged yaw target (THRO TYaw/YSrc), which throw_setup() cleared, and
the aborted-throw leg could pass if the aborted throw never set a target.
`cda0e8e8a2` clears the target in throw_dir_reset() so both callers reset
the same state (both run before the next detection recomputes it, so only
the log changes), and `4386dcd0e7` makes the leg require the aborted throw
to have logged YSrc 4 / TYaw 90 first. All 19 Throw tests pass at
`4386dcd0e7`. The reviewer's process points (fold c6e6484b22+041de0484b,
978b3999af+c2e8e0e66a, 1911cf40be+3904522d78 at the squash) stand.

A last cold read found the new comment's reason wrong for three of the
four yaw sources (only ImuDirection derives from the integrator; the
target belongs to the abandoned detection) and that no test reaches the
spool-up abort path, only the disarm path. Comment and message corrected
in place on `r1030/32475-4` (`9de2b82fbe`, `60cee67154`); the abort path
stays log-only and untested, as the commit now says.
