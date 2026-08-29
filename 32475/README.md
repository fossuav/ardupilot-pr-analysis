# PR #32475 - Throw mode improvements (drop detection, uprighting, yaw, sources)

Analysis archive for [ArduPilot/ardupilot#32475](https://github.com/ArduPilot/ardupilot/pull/32475).
Branch `pr-throw-mode-improvements` (andyp1per fork), base `master`,
supersedes #32393. Every number here is from real drops on the SmallFastDrone
branches; no logs are committed. Vehicles are named by board.

## Status (one line)

Open since 2026-06, awaiting review. Ten commits, six new parameters
(THROW_DROP_AG, THROW_DROP_CNF, THROW_SRC_INI, THROW_SRC_SET, THROW_YAW_TYPE,
THROW_YAW_DEG). Flown across roughly thirty drops on six airframes, from
hand drops at 1 m to releases from a carrier aircraft. Two SITL tests are in
the PR; five more that cover the spin, tumble, yaw and abort paths exist on
the SmallFastDrone branch and are not yet in the PR (see Reproduce).

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

## What is here

```
32475/
  README.md          <- this file
```

No logs committed: every measurement above is from a real drop. No SITL
BINs yet; see Reproduce for what could be archived.

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
