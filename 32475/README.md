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

### Superseded 2026-11-11 by log32's own ARM and EV records

"A false LAND_COMPLETE disarmed it in the air" is wrong. Re-read from
the log, all three disarms are `ARM` Method 2 (AUXSWITCH, the pilot's
arm switch), at 506.25, 529.55 and 544.15 s. LAND_COMPLETE (EV 18)
appears only at the same timestamp as each disarm, after EV 11: a
disarmed copter is marked landed. LDET.Count stayed 0 through all
three attempts. The private analysis repo's note on the flight says
the same. The land detector did not disarm it; the three false throw
triggers are unaffected. The bullet above is left as written because it
is what this README has said since the PR was opened.

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
  before detection (Q25 log, not committed). Not addressed in this PR.
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

## 2026-10-30: the refresh12 failures were four test problems, not a code clash

refresh12 (#32475 at `60cee67154` on the 4.7.2 stack with #32514) failed
ThrowDropTwiceWithoutReentry and ThrowNextModeAutoStaleSubmode every time
and ThrowSrcSetHandoff sometimes. The refresh record put all three down to
#32514 no longer raising the EKF failsafe on a source set with no
horizontal source. That was one of four causes, and the other three were
in the tests; the throw code behaves correctly on both stacks.

1. The first leg of ThrowDropTwiceWithoutReentry ("the aborted throw never
   set a yaw target") is flaky on #32475 alone too (1 of 2 on master).
   Autotest sets LOG_FILE_RATEMAX 10 and THRO is a streaming message, so
   the logger drops the stage-change record at detection: the previous
   10 Hz record is 40-45 ms older. Throw resets its own log timer anyway,
   so the target is first logged about 100 ms after detection, and the leg
   force-disarmed 60-125 ms after it. Passing run: detection 46.867 s,
   Stage 2 / YSrc 4 / TYaw 90 at 46.970, disarm 46.992. Failing run:
   detection 45.922, disarm 45.982, no Stage 2 record. The next stage
   message comes only after the toss lands (Hit ground 59.68 s,
   "Stabilizing throw height" 61.41 s in the completed toss), so the leg
   now waits 0.3 s of sim time before disarming. This was introduced by
   `60cee67154`, the last commit of round 6.
2. Its last leg waited for the failsafe's "position lost" to know the EKF
   had no position. #32514 does not count a missing position where the
   mode and the set need none, so it never comes. Now it waits for
   EKF_STATUS_REPORT to clear EKF_POS_HORIZ_ABS and EKF_PRED_POS_HORIZ_ABS,
   which is what Copter's ekf_has_absolute_position() reads while
   disarmed.
3. ThrowNextModeAutoStaleSubmode required "EKF Failsafe Cleared" before
   AUTO. Measured after the completion restore (XKF4.SS of the primary
   core, horiz_pos_abs set and const_pos_mode clear): on #32475 alone the
   EKF reports a position at +0.072 s, the wait message is at +0.100,
   "EKF Failsafe Cleared" at +0.972 and AUTO at +0.975. With #32514 AUTO
   took over at +0.100 with no wait, so position_ok() was already true
   (the first logged XKF4 with a position is at +0.115). The wait was
   guaranteed only by master's failsafe hold. The test
   now uses THROW_SRC_SET 2, so no position comes: throw must say "Auto
   waiting for position", then "no position for Auto, staying in throw".
4. ThrowSrcSetHandoff required "Loiter waiting for position" in its two
   LOITER drops, which is the same race. With #32514, LOITER waited in 7
   of 10 such drops and took over at +0.100 in the other 3. On #32475
   alone it always waited and took over at +0.93 to +1.12 s. The message
   is now required only in the drop where no position comes; LOITER
   cannot take over without one either way.

A/B with the new tests on the commit before each fix they guard (built in
scratch worktrees at `5e6c1af447` and `e46becb2f1`, the test file
replaced):
- ThrowDropTwiceWithoutReentry before `1154bffa6c`: "re-armed throw kept
  the aborted throw's yaw target", 2 of 2.
- ThrowNextModeAutoStaleSubmode before `34ae6a25ad`: no wait message, 2 of
  2; the log has AUTO entered at +0.000 with reason THROW_COMPLETE and no
  position at any point.

After the fix, the three tests pass 5 of 5 each on refresh12 and on
#32475 alone (master), and every Throw test passes: refresh12's 19
twice, and the PR's 19 once on #32475 alone.

Commits, on top of `60cee67154` as `r1030/32475-5` (pushed to andyp1per
`60cee67154` -> `3d634e4a5f`, a fast-forward) and on refresh12 as `28223b9b5b`..`c0c0f45759`:

    d0b22fb813  autotest: let the aborted throw's yaw target reach the log
    c57f083d21  autotest: wait for the EKF itself to lose the re-armed throw's position
    c38b657b8c  autotest: check the stale-AUTO handoff where no position comes
    3d634e4a5f  autotest: let the throw LOITER handoffs take over without a wait

All test-only, so they can fold into their test commits at the squash
(`60cee67154`/`1911cf40be`, `182df1f14f`, `a58de9ac3f`/`041de0484b`,
`6c59cce12c`). This settles the "#32475 against #32514" decision: neither
PR's code changes, and #32475's tests now hold with and without #32514.
The THROW_SRC_SET aided-to-unaided hand-off (about 7 s of dead
reckoning, then the EKF failsafe lands) is still open for Andy; it is
unrelated.

Not changed: THRO's "log at 10 Hz or if the stage changes" loses stage
changes to LOG_FILE_RATEMAX on any vehicle that sets it, so a flight log
can skip a stage that lasted under 100 ms. That is upstream throw
logging, not this PR's.

## 2026-10-30: #33366 takes the same var_info2 indices

#33366 (robertlong13, open, added to SFD's prs.txt today) gives
TKOFF_CPU_AVG and TKOFF_CPU_PEAK `ParametersG2::var_info2` indices 60 and
61, which this PR uses for THROW_SRC_SET and THROW_DROP_CNF (at
`3d634e4a5f`; THROW_SRC_INI is 63). A build with both compiles clean and
panics at every boot ("Bad parameter table"), so whichever merges second
has to renumber. 30 and 31 are free on master. SFD keeps this PR's, which
shipped on the betas, and moves #33366's to 30/31 (refresh12 `40c9fdd94b`;
`Tools/SFD/check_param_tables.py` flags both pairs without it).

## 2026-10-31: AP-Review's blocker at 3d634e4a5f fixed

The bot's round at `3d634e4a5f` (REQUEST CHANGES) had one blocker: staying
in THROW never starts horizontal control once a position comes back. The
XY latch was set only on the way into PosHold, so with `THROW_SRC_INI` on a
set with no horizontal source and `THROW_NEXTMODE` THROW, the restored
source set's position was never used, and the same after a refused handoff.
Confirmed by reading the code; `nextmode_requires_position()` is true for
THROW itself, so the bot's suggested gate holds.

Fixed on refresh12 (`b12501f5af`, test `b1bfb811be`, `a05ce46d5b` for the
message macro) and ported as `r1031/32475c`: `ae9b93be1f` (Copter, the
two folded) and `16042bc083` (ThrowStayHoldsRestoredPosition). Pushed
2026-10-31: `3d634e4a5f` -> `16042bc083` (fast-forward).
In PosHold, once `position_ok()` and the next mode wants a position, start
NE control, set the latch and say "Throw position regained".

- A/B, SITL, 5 m/s wind: the new test drifts 120.5 m in 20 s with the code
  fix removed and 0.0 m with it (0.1 m on the PR alone). The bot measured
  82.6 m.
- All 20 Throw tests pass on refresh12 and on the PR alone (the PR has
  ThrowModeRPMMin where refresh12 has ThrowDropNextModeVALT).
- Quick review: Codex audit CLOSED. Its cold read raised a should-fix: a
  refused handoff to a mode that needs no position (STABILIZE, ACRO,
  ALT_HOLD, LAND) also leaves throw holding level. Not changed: the only
  refusal reachable for those from throw is RC failsafe (ACRO and STABILIZE
  refuse entry in it), and `failsafe.radio` is set only with
  `FS_THR_ENABLE`, whose action has already taken the vehicle out of throw;
  the other refusals (throttle too high when landed, no altitude estimate
  from a manual-throttle mode, fence recovery) cannot apply. Its minor, use
  `GCS_SEND_TEXT()`, is taken.
- Still open from the bot's round: `THROW_ALT_DCSND`'s changed meaning
  (Andy's call), the THPH OSD string overwritten after a handoff, the
  SIM_IMU_POS reboot comments, and the description.

The note above that SFD moves #33366's pair to 30/31 is out of date: since
2026-10-31 they are on 41/42, and VALT_POS_EXPO is back on 30 (refresh12
`8e2a1e6ce6`, `95ad9b9c37`).

## 2026-10-31: description and replies posted

Description replaced with the 10-30 draft, updated for the blocker fix (the position that comes back is held; ThrowStayHoldsRestoredPosition row; 20 Throw tests). The original body is kept in that session's scratchpad only; the PR history shows it.
Reply posted: https://github.com/ArduPilot/ardupilot/pull/32475#issuecomment-6548809950 (the blocker fixed in ae9b93be1f).

## 2026-10-31: squashed after the flight audit

Pushed `16042bc083` -> `8e931047e5` (force, 54 commits to 28, same tree; backup `pre-squash/32475-1031`). What folded and what stays on top, and why: `squash-audit-2026-10-31/squash_C.md`.

## 2026-10-31: THROW_ALT_DCSND's new meaning kept

Andy's decision on the bot's should-fix: keep THROW_ALT_DCSND measured from the release point (master measures it from where the arrest starts), and say so. The description gained a "Changed meaning" paragraph under the parameters: a drop now climbs back to THROW_ALT_DCSND below the release point after uprighting falls past it, so existing setups end higher than before. Reply posted: https://github.com/ArduPilot/ardupilot/pull/32475#issuecomment-6549128108. The rejected options were a new parameter with the old one kept, and an option bit.

## 2026-11-02: AP-Review at the squashed head

COMMENT at `8e931047e5` (round 8): no blockers. Should fix: `self.mav.location()` at arducopter.py:18484 and :18487 fails the location-ratchet job; use `self.get_location()`. Minors: return after a successful set_mode() so THPH leaves the OSD (owed), exit()'s source-set restore overriding a set picked during the throw (now reproduced in SITL), the SIM_IMU_POS reboot comments (owed), THROW_ALT_DCSND's meaning (a maintainer call, answered).

## 2026-11-02: the location-ratchet test lines, THPH and the SIM_IMU_POS comments

Four commits on top of `8e931047e5`, made on refresh12 first (branch `r1102/32475-r12c`: `a635a8250e`, `9ba96f2915`, `df52d2f013`, `caef8b3702`) and ported to `sq/32475-1102c` (`cfb802b43f`, `d14edd6e51`, `fc699dca1b`, `df174b0731`, the same changes):

- Copter: the regain block and the OSD/stage-message block run only while `copter.flightmode == this`. run() still goes on through its controller updates after a handoff.
- autotest: ThrowStayHoldsRestoredPosition reads its drift from SIMSTATE. `check_mavutil_location_ratchet.py --base-ref 5b36047100` failed before (0 -> 2 uses in arducopter.py) and passes after.
- autotest: the two "SIM_IMU_POS takes effect on reboot" comments dropped (AP_InertialSensor_SITL reads `imu_pos_offset` every accel sample). The reboots stay; nobody ran the tests without them.
- autotest: ThrowSrcSetHandoff reads each LOITER leg's log (handoff picked by MODE Rsn 16, THROW_COMPLETE) and fails on "Throw position regained" after the handoff. A leg that regained before its handoff does not test the handoff loop and says so; at least one leg must. Fails 2 of 2 on the baseline binary (twice, for each version of the check), passes on the fix; in 3 fixed runs all six LOITER legs waited for their position and handed over as it arrived, so both legs test it.

The bot's suggested fix, returning from run() after a successful set_mode(), was tried first (`7a634687f5`, `9cba642063`, superseded) and is wrong. A mode's init keeps a position controller that was updated in the last loop (`D_is_active()` is "updated within one tick"); returning skips throw's update in the handoff loop, so the incoming mode's first `D_update_controller()` finds it two ticks stale, re-initialises it and raises INTERNAL_ERROR(flow_of_control). ThrowDropTwiceWithoutReentry (handoff to ALT_HOLD) caught it: 2 of 2 failures with the return, 2 of 2 passes without it and with the guards. The commit message says why run() carries on, so the return is not suggested again.

The first get_location() version (`4dbeed48b7`, `aa2305e021`, superseded) read GLOBAL_POSITION_INT, the EKF's estimate, which a cold read pointed out would read still if the restored set never gave the EKF a position, the failure the test catches. SIMSTATE is the simulator's own position; GPS_RAW_INT, what mav.location() read, is close to it in SITL.

A/B on refresh12, throwaway harness (not committed): a drop with THROW_SRC_INI 2 handing over to LOITER, the OSD flight mode item read over MSP DisplayPort for 12 s after the heartbeat showed LOITER, as run lengths of the mode text. Before (`c46a09ec56`, 3 runs): `... THHT:7 THPH:119`, never LOIT, one "Throw position regained" at the handoff. After, guards (2 runs): `THPH:2 LOIT:115` both, no regain message. The screens lag the vehicle (buffered from connect), so the counts are of screens, not seconds. The OSD string itself has no autotest: the DisplayPort reader (`osd_displayport_rows`) comes with #34543 and master has none.

Codex was out of quota (until 2026-11-04), so the two cold reads were by Claude. The second's should-fix (the check passing on a leg that regained early) is the stronger check above; its minor that throw_apply_yaw_align() also runs in the handoff loop (it can send "Throw yaw aligned" there after a yaw-align timeout) is left, being outside what the commit claims. ThrowDropEKFFailsafePosHold failed once in a full throw run at `dcdf825f79` (yaw alignment finished and handed over to ALT_HOLD before the EKF failsafe came, so its assert_mode('THROW') found ALT_HOLD, a race in the test before any handoff) and passed 3 of 3 reruns; all 20 throw tests otherwise pass at the port head. Left as they were: exit()'s source-set restore overriding a set picked during the throw (carried), and THROW_ALT_DCSND's meaning (a maintainer call, answered 10-31).

## 2026-11-02: pushed

Pushed to `df174b0731` (refresh12 `b1093230e6` locks it). Reply posted: https://github.com/ArduPilot/ardupilot/pull/32475#issuecomment-6576455860.

## 2026-11-02 (later): exit() keeps a source set picked during the throw

Round 9's minor: `restore_source_set()` put back the pre-throw set even when
the pilot or a GCS had picked another one in throw mode, though its comment
said "if it is still in use". It now restores only while the set
THROW_SRC_INI applied (kept in a new `throw_source_set`) is still the active
one; a picked set is kept with "Throw: keeping EKF Source Set N", and when
the pre-throw set is already active (THROW_SRC_INI naming the set in use, or
a refused switch) it does nothing and says nothing. It returns whether it
changed the set, so the completion handoff with THROW_SRC_SET 0 waits out
THROW_SRC_SETTLE_MS only after a real change. THROW_SRC_SET 1-3 at
completion still overrides a pick: it is the user's standing instruction for
the next mode, while the restore only undoes THROW_SRC_INI's temporary
switch; THROW_SRC_SET's description and the commit message say so.
THROW_SRC_INI's description says a set selected while in throw mode is kept.
The stale comments that said exit() always restores are corrected.

Tests: ThrowAbortRestoresSourceSet's second leg picks set 3 disarmed in
throw mode, then leaves throw; ThrowSrcInitRestoredOnCompletion's second leg
picks set 3 after arming in throw mode (before release, so the pick cannot
race completion), drops, and completes with THROW_SRC_SET 0. Both assert the
"keeping" message, no "restored" message, and XKFS.SS 2 for core 0. On
refresh12 both fail without the fix (the log shows "Throw: restored EKF
Source Set 1" over the pick) and pass 2 of 2 with it; the plain restores
still pass.

Commits: refresh12 `r1102b/32475-r12c` (on `b1093230e6`): `4259cf259d`
Copter, `6f156daabf` autotest. Port `sq/32475-1102f` (on `df174b0731`):
`a096419ed8` Copter, `9149e72d4f` autotest. Superseded local branches:
`r1102b/32475-r12`, `r1102b/32475-r12b`, `sq/32475-1102d`, `sq/32475-1102e`.
Cold reads: one by the worker, one by a fresh reviewer (Codex out until
11-04); the reviewer's six points are all taken. Not pushed.

Pushed 2026-11-02 (afternoon) to andyp1per with a lease: `df174b0731` -> `9149e72d4f` (refresh12 `df341758a7` locks it). Reply: https://github.com/ArduPilot/ardupilot/pull/32475#issuecomment-6580087409.

## 2026-11-07: two test fixups squashed, pushed

No flight since 2026-10-31 entered Throw (SFD-O4 logs 73-88, the Q25 on
topup9 and topup11), so the two fixes stay on top, each with its test.
Pushed `9149e72d4f` -> `e730ee0cd6` (force, 34 commits to 32, same tree;
backup `pre-squash/32475-1107`). The test fixups `d14edd6e51` and
`fc699dca1b` fold into `8e931047e5`, now `8f308f83ec`. The hand-over fix
is `af058e18d5` and the source set fix `0be31dc2ed`.

## 2026-11-07 (evening): AP-Review at `e730ee0cd6`, a compiled-out next mode (open)

AP-Review (COMMENT) found that with THROW_NEXTMODE set to AltHold or Acro
in a build without that mode (master's MODE_ALTHOLD_ENABLED,
MODE_ACRO_ENABLED), nextmode() returns nullptr and the vehicle stays in
throw, but nextmode_requires_position() still answers false, so
requires_position() is false: the EKF failsafe does not act in throw's
position hold and the XY controller does not restart after a position
loss. Confirmed from the source. Proposed, not made: return true when
nextmode() is nullptr, as its own commit on top.

## 2026-11-10: three drops on a customer quad (tier 1)

A customer quad on the beta `7b00f3b5` (one IMU, ARK Flow on DroneCAN, no
GPS), `THROW_TYPE` 1 (drop), `THROW_NEXTMODE` 29 (VALT), logs 18, 20 and
22 (1245450/46, /47, /49).

- Detection 0.244-0.250 s after release (THRO stages 1-5). All three were
  upward tosses flown as drops: VelZ +6.33, +3.98 and +3.35 m/s at
  detection.
- Upright from 128, 137 and 69 deg to under 5 deg in 0.94, 0.80 and 0.65
  s; HgtStabilise 1.58, 0.97 and 1.18 s. Motors peaked 1594-1741 of about
  1950. Yaw within 0.4 deg of its target.
- The beta's own VALT hand-off (not part of this PR) counted VALT as
  needing a position. log20's drop had none ("Throw height achieved, lost
  position", "Throw: VALT Hold waiting for position"): it held level for
  1.73 s at 0.13-0.33 m with no horizontal control and the sticks ignored,
  and after 5 s would have stayed in THROW. Fixed on the beta; see the
  2026-11-10 entry in the SFD fork's `Tools/SFD/FLIGHT_VALIDATION.md`.
- log22 103.67 s: a flow lockout reset during PosHold (#33484) stepped the
  velocity to 3.2 m/s at -54 deg roll and the hand-off waited; the pilot
  took LOITER 1.7 s later.
- Medium confidence, not followed up: with `THROW_YAW_TYPE` 1 the yaw
  target looked far from the EKF track (256 against 10-14 deg on log22,
  251 against 295-314 deg on log18).

## 2026-11-11: THROW_ALT_DCSND 0 hands a toss back where it stops (`fix1111/32475-dcsnd0d`, 2 commits on `e730ee0cd6`)

A customer's flow quad, three hand tosses with THROW_TYPE 1 and
THROW_ALT_DCSND 0 into VALT: each was released on its way up, uprighted
at 3.2-3.8 m after the top of its climb, and flown back down at up to
3.9 m/s to the release point, which is where the toss's low-g window
began (the hand), before the hand-over: 1.7-3.4 m of descent, ending
0.13-0.47 m above the ground on two of them.

- `f4fcfb44ba` Copter: with 0, the HgtStabilise target is the higher of
  the release point and the height uprighting ends at, and when the stage
  ends (normally the vertical speed arrested) the target moves to the
  higher of the release point and the height reached, so PosHold and a
  next mode that keeps the vertical target (ALT_HOLD, LOITER) hold it. A
  vehicle uprighted below the release point still climbs back to it.
  DCSND above 0 takes neither branch. The parameter text says so.
- `3f8d1623ee` autotest: ThrowZeroDescentStopsAboveRelease, a 0.5 s
  SIM_SHOVE_Z -30 toss with MOT_SPOOL_TIME 1.0 so it is uprighted after
  its top, as a tumbling hand toss is. Handed over 1.5 m below the 5.9 m
  top and held within 0.06-0.09 m for 5 s in ALT_HOLD; with the release
  point as the target it is handed over 2.9 m below the top, and without
  the second change ALT_HOLD climbs back past 0.5 m.

Tried and dropped: the position controller's stopping point as the
target (its P-gain term put it about 2 m below a 3.5 m/s fall; handed
over 2.6 m below the top), and a v^2/2g term for a vehicle still
climbing (Codex: the controller already carries the upward velocity into
the target, so it counted the climb twice). A second leg for a drop
caught below the release point was dropped too: a drop hands over once
its vertical speed is arrested, so the hand-over height cannot show the
climb back.

All 21 throw tests pass on the PR branch and all 22 on a beta copy
(`fix1111/32475-dcsnd0d-beta`, `01f474c138`, `9d2cdae5a1` on `413d62782b`).
Quick review: gate clean, two Codex reads; the first found the double
count and the climb back after the hand-over (both fixed), the second
only wording, now corrected. The bot's last review (COMMENT at
`e730ee0cd6`) lists THROW_ALT_DCSND's meaning as a maintainer call: this
makes 0 behave as upstream's 0 does for a vehicle above the release
point (target the height uprighting ends at), with the release point as
a floor.

EKF height and vertical velocity, which both targets and the hand-over
rest on. Against the tilt-corrected range finder on the three tosses:
the EKF height was 1.8 m low in the hand on one (0.1 m on another), so
its release point, the old target, sat 1.8 m too low, which is why that
toss was taken to 0.47 m; it was 0.1-1.3 m low just after uprighting and
0.4-0.7 m low when the vertical speed was judged arrested, and the EKF
then read about 0.5 m/s of descent against 0.6-0.9 m/s. Earlier records
put velD errors after a clipped impact or tumble at 1-6 m/s for 6-16 s
on flow vehicles with no velZ source, a velD gate firing 1.2 m short of
its target, and spool-up baro spikes of 6-10 m; throw mode turns off the
takeoff baro compensation (`baro_ground_effect.cpp`), so those spikes
reach the EKF at full weight. Both new targets are MAX(release point,
EKF height), never below the old target, so for any EKF error the
vehicle is held no lower than before. What changes is the direction: an
error in the height read after uprighting is held and comes out as a
climb or sink of that size as the EKF corrects, where the old target
turned the same error into a descent towards the ground. The velD gate
is unchanged but is reached 1-3 s sooner, so the pilot takes over while
those errors are larger. THROW_ALT_DCSND's description is rewritten
around 0 and given a range of 0-20 m.

Pushed 2026-11-11: `pr-throw-mode-improvements` `e730ee0cd6..3f8d1623ee` (fast-forward). Description updated the same day: the new test in its table, and a paragraph on what 0 means and the EKF height errors.

## 2026-11-11: a compiled-out THROW_NEXTMODE holds a position (`fix1111/32475-nextmode`, 1 commit on `3f8d1623ee`)

The 2026-11-07 minor, raised again at `3f8d1623ee`, made as proposed:
nextmode_requires_position() returns true when nextmode() is nullptr
(`9a0a72406d`). SITL compiles every mode, so no test reaches it (a Codex
minor, left); ThrowNextModeAcro, ThrowUpwardNoPositionNextMode,
ThrowStayHoldsRestoredPosition and ThrowZeroDescentStopsAboveRelease pass.
On the beta as topup6, whose nextmode() lists VALT, so THROW_NEXTMODE 29
is unchanged. The maintainer call on THROW_ALT_DCSND above 0 stays open.

## 2026-11-12: five hand tosses into VALT on a TBS_LUCID_H7 quad (tier 1, 1b)

log13 (3408138/71), SFD refresh15 (`66fe7b62`): two IMUs, ARK Flow MR and
its 15 m range finder on DroneCAN, GPS, compass. THROW_TYPE 1,
THROW_ALT_DCSND 0, THROW_NEXTMODE 29 (VALT), THROW_SRC_INI 3 (a set with
no horizontal or yaw source), THROW_SRC_SET 2 (flow), THROW_YAW_TYPE 1.
Five upward tosses, the last a lob off a raised platform that fell about
1.5 m below the hand. GPS is logged but not used by the flow set, so it
is the reference. Replays to float rounding; no internal error.

- Detected 0.245-0.250 s after release at +1.6 to +3.6 m/s vertical; no
  false trigger in 10-18 s of carrying before each.
- Upright from 22-129 deg in 0.29-0.65 s; motors at most 1384.
- Yaw within 1-3 deg of the target on all five; the target within about
  5-35 deg of the GPS course after release.
- THROW_ALT_DCSND 0 took both branches: throws 1-4 stopped where
  uprighting ended, above the release point; the lob climbed back to its
  release point.
- After the hand-over at the top of the arc the vehicle sank 0.6-1.3 m by
  GPS on throws 2-4. The throw's throttle there was 0.034-0.065 against a
  0.078 hover, from stopping the climb, and the EKF (baro height, no
  vertical velocity source) saw about 1 m/s less of the fall than GPS
  (throw 4: -0.9 against -1.9 m/s). ThrowZeroDescentStopsAboveRelease held
  within 0.1 m in SITL ALT_HOLD; this is the first flight against it, and
  the EKF's vertical estimate is part of the difference.
- Throw 1: with no yaw source in THROW_SRC_INI's set and the vehicle armed
  while carried, the EKF reset its yaw to GPS velocity during the wind-up
  and was 176 deg off (241 against 65 deg DCM, 63 deg compass). The target
  had been taken before it and stayed right, but the compass reset at the
  switch to THROW_SRC_SET then had the vehicle spin about 180 deg onto it,
  and the hand-over came 1.96 s after detection against 0.85-1.30 s. The
  target is an absolute heading that nothing adjusts for an EKF yaw reset
  (derived from the source, not measured).
- The flow set started at about zero horizontal velocity (constant
  position on set 3) while the toss carried 3-6 m/s, and stayed 3.5-6.2
  m/s wrong until a #33484 lockout reset 0.5-2.8 s later. VALT has no
  horizontal control; a position next mode would have handed over within
  0.2 s of the switch, as position_ok() is true as soon as relative
  aiding starts.
- Throw 2's hand-over at 1.2 m was followed by a descent to the ground
  (range finder under 5 cm for 0.4 s): the baro read 2-3 m high after the
  throw and VALT held the EKF height. Throw 1's baro fell 4.5 m in a
  second in PosHold and the vehicle was climbed about 5 m. Airframe baro,
  not this PR; Replay with the flow set's height on the range finder
  (EK3_SRC2_POSZ 2) tracks both.

Proposed, not done, for a throw into a flow position mode: hand over only
once the vertical speed has stayed arrested for a settle time rather than
at its first zero; rotate the yaw target by any EKF yaw reset; switch to
THROW_SRC_SET once upright, so the flow set converges while the throw
still holds height; and gate a position next mode on the flow being fused
on both axes rather than on position_ok().

## 2026-11-12: log14, the same quad with compass yaw while waiting (tier 1, 1b)

log14 (3408138/74), the same quad on refresh15's code (not topup1), with
log13's settings plus `EK3_SRC3_YAW` 1 (the compass on THROW_SRC_INI's
set) and `EK3_RNG_USE_HGT` 24. Six upward tosses into VALT, handed over
0.7-1.3 s after detection (release-to-detection latency not measured
on this log). Replays to float rounding through refresh15's Replay.

- No "yaw aligned to GPS velocity". EKF yaw against DCM at the switch to
  THROW_SRC_SET: -12, +11, -3, -6, -2 and +12 deg. Measured the same way,
  log13's five were -178, +2, +77, -59 and -5: throws 3 and 4 had throw
  1's fault on a smaller scale, and after the switch the vehicle turned
  74 and 53 deg (commanded 151 and 126 deg/s), as well as throw 1's 30
  deg at 207 deg/s, in the first 3 s. On log14 no heading moved more than
  12 deg in the 3 s after the switch. With a compass in the waiting set
  there is no reset at the switch for the yaw target to follow; the
  topup1 change still matters for a waiting set with no yaw source
  (inferred from the two logs, not replayed).
- Sink after the hand-over, by GPS over 3 s: 0, 1.17, 1.74, 0.75, 0 and 0
  m (log13 up to 1.27 m). The settings do not touch it; topup1's settle
  wait is for this.
- EKF horizontal velocity within 1 m/s of GPS (and staying so for 0.5 s)
  after the switch: 0.26-2.51 s across both cores, peaks 1.4-7.0 m/s;
  log13 by the same measure 0.55-2.63 s. This measure does not reproduce
  the flight card's 0.55-4.34 s for log13, so compare topup1's flights
  against these two rows rather than that figure.

## 2026-11-12: logs 15-16 on topup1, into VALT and flow Loiter, and the flow check's fail-open (tier 1, 1b)

log15 (3408138/78): six tosses into VALT; log16 (3408138/81): three into
LOITER (`THROW_NEXTMODE` 5), the first throws onto a position mode on
this quad. topup1's code (`4da1f0c1`), log14's settings with
`EK3_RNG_USE_SPD` 4. Both replay to float rounding through topup1's
Replay.

- The flow check held all three LOITER hand-overs until the flow agreed:
  "flow settling" then "Loiter waiting for position", "lost position"
  then "position regained", "flow settling" then "position regained";
  hand-over 2.39, 1.66 and 1.63 s after detection, 0.51, 0.43 and 0.83
  m/s off GPS. LOITER carried on 3.5, 2.8 and 1.5 m by GPS and then held
  within 0.6-0.7 m with the sticks centred.
- The settle wait: no sink after the hand-over on nine of ten throws
  (0.73 m on one); hand-overs 1.45-1.72 s after detection into VALT. The
  sink moved before the hand-over: at each LOITER hand-over the throw's
  height target was 0.65-1.0 m above the vehicle, which had sunk 0.5-0.8
  m by the range finder in the last second, and LOITER then climbed
  1.3-2.1 m. Open.
- log15's first throw struck the ground. Armed 11.5 s before the throw
  after a GPS flight, the EKF was still in absolute aiding, dead
  reckoning, and reported a relative position. The flow had not fused,
  so the check had no innovations and passed: "good position" 0.55 s
  after the switch to THROW_SRC_SET, 1.08 s before the first flow
  fusion. The throw's position hold braked a 5.7 m/s toss at 22 deg of
  roll on a velocity 2.3 m/s out; 0.2 s later the IMU read 11-14 g. The
  vertical estimate was also wrong (the EKF at 1.5 m and level, GPS 1.5
  m below the release point and falling, the range finder in No Data).
- Fixed on the SFD beta as topup2. The EKF now stops aiding at once on
  THROW_SRC_INI's set (see 33484), so no throw has a dead reckoned
  position to pass. The check also fails closed (`6af11a5edb`): on a
  vehicle with a flow sensor, a set that does not use GPS for position
  needs flow innovations the EKF reports, and restarts the average when
  they lapse; the test is the set's GPS use (`ahrs.using_gps_for_pos()`),
  not the position flags. That covers flow aiding that starts and then
  loses the flow, which the EKF keeps for 5 s.
  ThrowTossFlowLostHoldsPosition turns the flow off as relative aiding
  starts: the throw waits and hands over 0.12 m/s out once the flow is
  back; with the change removed it regains a position on the stale
  flow.


## 2026-11-12: #35105 and the THROW wait (tier 3, and AP-Review's SITL)

#35105 (rmackay9, head `3993abc2e6`) treats an armed Copter with
`land_complete` set as on the ground, which covers the whole THROW wait
(carrier drops up to 152.8 s at 31 m in the 2026-11-11 scan in
`../35105/`). AP-Review measured ThrowDoubleDrop at that head with no
in-flight yaw or field alignment, against two per flight on master.
From the source, the compass is also fused past its gate through the
wait. Clearing the flag on entering `Throw_Detecting`
(`ahrs.set_vehicle_landed(false)`) restored the alignments in
AP-Review's SITL. If #35105 merges, this branch needs that line unless
#35105 takes it. See `../35105/README.md`.

## 2026-11-12: topup1 and topup2 ported to the PR, with two review rounds, pushed `fc0fa3d4db`

Branch `fix1112/32475-g`, 22 commits on the PR head `9a0a72406d`, a
fast-forward. From the SFD beta's topup1 and topup2: the yaw target
follows an EKF yaw reset (`800f7108c3`), the switch to THROW_SRC_SET
once upright (`fcc1ca9b72`), the THROW_ALT_DCSND 0 settle wait
(`45f74c3fa7`), the flow agreement check (`e5450885f3`) and its
fail-closed form (`194fc6d1ab`), each followed by its test.

Adapted for master:
- the reset is detected from `ahrs.get_yaw_reset_count()`, as master
  reports no reset angle;
- `ahrs.has_status()` is `configured_backend_has_status()`;
- the beta's `using_gps_for_pos()` is SFD-only; a new AHRS accessor
  passes on the backends' existing `configured_to_use_gps_for_pos_XY`;
- `ThrowTossFlowLostHoldsPosition` needs the EKF to stop aiding on an
  empty set, which master does not; `ThrowTossWithoutFlowHoldsNoPosition`
  turns the flow off before the toss instead, the master case the fail
  closed check is for.

Review round 1 (six Claude reviewers and a Codex cold read): two
must-fix, both text (the parameter docs still described the hand-over
switch; THROW_FLOW_NIS_TC_S cited #33484's lockout window, absent from
master). Fixes on top, all unflown:
- the flow check applies where the active set takes its horizontal
  velocity from the flow and its position from no GPS (new EKF3 and
  AHRS accessors), not on any non-GPS set, which held ExtNav, beacon,
  wheel encoder and EKF2 sets with a flow sensor fitted until "staying
  in throw";
- the flow average runs through the throw and starts again on any
  change of source set, not at every completion (0.8-1.1 s of level
  hold on every flow throw before);
- a hold the flow stops agreeing with is released, at the EKF's flow
  gate level (THROW_FLOW_NIS_GATE, 18), so it does not toggle at 3.7;
- the settle run starts at the arrest and the wait ends 3 s after it
  began (THROW_DROP_ARREST_MAX_MS), not 3 s into PosHold;
- the drop's release height follows EKF height resets;
- the completion set comes in once actually upright, not on
  uprighting's timeout;
- a target taken from the entry velocity, a GPS course, is not turned
  by a yaw reset (round 2).

THROW_FLOW_NIS_AGREES 3.7 re-derived (derived from the source, not
measured): the average is an exponential one spanning about ten
independent samples of 10 Hz flow, so a filter that agrees stays under
3.7 98.8% of the time (99.9% at 20 Hz), not the 95% of a 5-sample
boxcar the comment gave.

SITL at the final tree (26 throw tests pass), each new or changed test
shown to fail without its change:

| test | with | without |
|---|---|---|
| ThrowYawFollowsEKFYawReset | turned 2.4 deg | 88.2 deg |
| ThrowZeroDescentSettlesBeforeHandover (now read from the log) | handed over 0.87 s into the arrest, VelZ up to 0.12-0.13 m/s | 0.37 s in, 3.11 m/s |
| ThrowHeightSourceSwitchNoClimb (GPS 15 m below the baro) | climbed 0.00 m | 4.16 m |
| ThrowTossWithoutFlowHoldsNoPosition | held, handed over 0.03-0.06 m/s out | "good position" with no flow, LOITER within 3 s |
| ThrowTossIntoFlowLoiter | "flow settling", 0.17-0.22 m/s out | "good position" at once (velocity alone does not discriminate) |

Untested, derived from the source only: the gate on the set's flow
velocity, the average restart on a source set change, the release on a
flow lapse, the upright gating and the entry velocity change.

Known limit, in the fail closed commit's message: a completion set with
no horizontal source at all is left to the EKF, which on master can
report a dead reckoned position on it for up to 15 s; #35146, which
stops aiding on such a set at once, covers it.

Not posted to the PR, by decision: no comments on #32475.

## 2026-11-13: the flow-lost position requirement flew into an RTL, the LAND fix, the fold (tiers 1, 2)

AP-Review's blocker at `fc0fa3d4db`: a drop whose hold holds level
because the flow stopped agreeing lost its position requirement with
the controller flag, so once relative aiding stopped the EKF failsafe
only reported and the vehicle held level with no horizontal control.
The requirement now holds from the first time the hold has held a
position (`77dfbb8635`); ThrowDropFlowLostFailsafe lands on the EKF
failsafe with it and gets only "EKF Failsafe" without it, on master and
on the beta (tier 2). From the port's review, the hold counts only while
throw runs, as set_mode() asks before init(); no SITL setup reaches that,
as a disarmed copter keeps a predicted relative position.

Flown on the beta's refresh16 topup1, the throw quad's log19 third throw
(tier 1): the hold sank to the ground on the baro height with the range
finder out of the height fusion; on the ground the flow stopped ("Throw
flow lost, holding level"), drag fusion made the EKF report dead
reckoning, and the dead-reckoning failsafe (`FS_DR_ENABLE` 2) switched
THROW to RTL at once, which climbed to 20 m. Without the change no
failsafe reaches the level hold. Kept: the hold now takes the failsafes
a Loiter would; the vehicle's card sets `FS_DR_ENABLE` 0.

AP-Review's should-fix: with `THROW_NEXTMODE` LAND the hand-over did
not wait for the flow, and LAND's init takes a position whenever
position_ok() is true, so it landed under position control on the
velocity the throw had rejected. A hand-over to LAND before the flow
agrees now tells LAND to land level (`3276864e54`).
ThrowTossIntoLandWithoutFlow: 244 velocity PID records in LAND without
the change, none with it (tier 2). ThrowTossWithoutFlowHoldsNoPosition
failed 5 of 9 runs on AP-Review's machine (none of 6 here, old or new):
the flow now comes back as the hand-over starts its 5 s wait
(`3e45c3b2f5`). All 28 throw tests pass on master.

The squash audit of the 11-12 and 11-13 flights folded (each pair
flown and analysed): the hand-over guard into "hold a position that
comes back", and its check into "cover the throw mode fixes"; the
fresh-flow check, the flow-lost level hold and the flow-lost position
requirement into "throw waits for the flow to agree", its three AHRS and
EKF accessor commits moved ahead unchanged and the tests into its test;
the two test fixes for the switch once upright into one. The running
throw guard is its own commit again, as nothing showed it acting. 62
commits to 55, `fe3213222c`, tree unchanged. The zero-descent hold into
the hand-over where it stops (both flown) is left optional; 21 unflown
commits stay on top. Nothing is posted on the PR.
