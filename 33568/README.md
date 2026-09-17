# PR #33568 - Fall back to relative aiding when optical flow replaces lost GPS (EKF3)

Analysis archive for [ArduPilot/ardupilot#33568](https://github.com/ArduPilot/ardupilot/pull/33568).
Branch `pr-flow-aiding`. PR head `9e04d0e0a7` (pushed 2026-09-15, rebased
onto master `bf08027404`); before that `4bb2ef3583`. Base master 23 Jun 2026,
1364 commits behind on 2026-09-15 but `git merge-tree` against master is still
clean.

## Status (one line)

Adds the missing AID_ABSOLUTE -> AID_RELATIVE edge so a GPS-booted vehicle that
later flies on flow gets the flow control limits. The 2026-09-12 automated
review's headline BUG - that the new edge teleports the NE position to the EKF
origin - **did not reproduce when measured**.

**Superseded 2026-09-15:** it was measured hovering. Moving at 5.4 m/s through
the fall back the estimate stepped 21.0 m and 5.9 m/s; fixed by skipping both
resets on that edge and pushed as `9e04d0e0a7`. See the 2026-09-15 sections.

**Superseded 2026-09-15:** it reproduces on a vehicle that is still moving
when the fall back fires (21 m and 5.9 m/s steps at 5.4 m/s); the 2026-09-12
runs hovered through it. Fixed locally in `05d1db1b9d`, and the per-cycle GPS
guard in `8627ddedc6`. See "Moving through the fall back (2026-09-15)".

## The claimed BUG, and what the measurement says (2026-09-12)

The review's chain is real as source:

- the new edge sets `PV_AidingMode = AID_RELATIVE` (`Control.cpp:406-408`)
  without writing `lastKnownPositionNE`
- the mode-change block always calls `ResetPosition()` (`Control.cpp:510-511`)
- `ResetPosition()` with `PV_AidingMode != AID_ABSOLUTE` assigns
  `stateStruct.position.xy = lastKnownPositionNE` (`PosVelFusion.cpp:122-125`)
- `lastKnownPositionNE` is written in exactly one place, on entry to AID_NONE
  (`Control.cpp:429-430`), and zeroed at `core.cpp:243`

All four verified by reading. The predicted consequence is that a vehicle far
from the origin snaps to it at the fallback.

**It does not happen.** The PR's own test scenario, with the vehicle first flown
89 m from the origin and then switched to the flow source set:

| | |
|---|---|
| AID 0 -> 2 | t = 88.04 s |
| vehicle position at the transition | PN -0.3, **PE -89.3 m** |
| logged position reset delta (`XKF4.OFN/OFE`) | **+0.13 / -0.05 m** |
| largest \|OFN\| over the whole flight | **0.17 m** |
| position after the transition (t = 93.84) | PN -0.2, PE -89.4 m |

The position does not move. A teleport to the origin would have shown as an
~89 m reset delta and an ~89 m step in `XKF1.PN/PE`; neither is present.

### What is not yet established

Which of the two possibilities holds: the reset is not taken on this edge, or it
is taken and `lastKnownPositionNE` already holds the current position (an
AID_NONE entry shorter than the 10 Hz `XKF4` logging interval would hide the
write). Distinguishing them needs one more instrumented run, and the
instrumentation has to be `::fprintf(stderr, ...)` rather than `GCS_SEND_TEXT` -
see the traps below.

Either way the review's stated consequence is refuted for this scenario, and the
suggested fix (write `lastKnownPositionNE` before setting AID_RELATIVE) should
not be applied on the strength of the review alone.

### Superseded 2026-09-15 by a run moving through the fall back

"For this scenario" was the whole of it: the vehicle hovered for the 10 s
between the source switch and the fall back. Kept moving across it, the
position steps 21 m. Mechanism and numbers in "Moving through the fall back
(2026-09-15)". The table above is left as measured because it is right for a
hovering vehicle, which is what it was.

## Traps this cost, worth not repeating

- **`GCS_SEND_TEXT` from EKF probe code is lossy.** Three runs' worth of probe
  output was missing or misleading because statustexts were dropped around the
  source switch. `::fprintf(stderr, ...)` survives and lands in the autotest log.
  The dataflash (`XKF1.PN/PE`, `XKF4.OFN/OFE`, `XKF4.AID`) is better still.
- **`self.reboot_sitl()` means two SITL instances per run**, so early stderr
  lines can belong to the pre-reboot instance and read as if the transition
  happened at the origin. Correlate against the dataflash, not the console.
- **`fly_guided_move_local(100, 0, 8)` silently did not move the vehicle** in
  one run - "Reach distance (0.51)" with `endpos == startpos`. RC translation is
  cruder but cannot no-op silently.
- **Print both components.** A probe printing `stateStruct.position.x` alone
  read as "at the origin" while the vehicle was 89 m east.

## The other review findings, untested

Not examined here, and none of them depend on the BUG above:

- the PR silently enables `getHeightControlLimit()` on GPS loss, which AC_Avoid
  will use to command a vehicle down to ~20 m AGL with a 30 m rangefinder
- `!readyToUseGPS()` is a per-cycle flag, so under a sustained GPS rejection the
  edge fires and blocks the in-place glitch recovery
- the bit-identical velocity claim in the description cannot hold if
  `ResetVelocity()` zeroes the horizontal velocity on the transition
- the added test hovers at home, where the position question is invisible; the
  fly-out above is the fix for that regardless of the outcome

### Superseded 2026-09-15

All four were measured on 2026-09-15; see "Remaining review findings,
measured (2026-09-15)". The height limit one was measured on 2026-09-12 below.

## The height control limit does not command a descent either (2026-09-12)

The review's third finding: because `getHeightControlLimit()` gates on the same
`AID_RELATIVE`, the fallback silently switches on the EKF height limit, and
"a copter that loses GPS at 100 m will now be commanded down to ~20 m AGL".

Measured. LOITER at 39.4 m, `SIM_TERRAIN 0` so `terrain_srtm_alt_valid` cannot
suppress the limit, analog range finder at its 40 m default, so the limit would
be `40*0.7 - 1 = 27 m` - twelve metres below the vehicle. Switch to the flow
source set and watch for 30 s:

    altitude before 39.4 m
    t+05s 39.5   t+10s 39.5   t+15s 39.5
    t+20s 39.5   t+25s 39.5   t+30s 39.5
    net change +0.1 m

**No descent.** The mode change to AID_RELATIVE is confirmed in the same run.

The descent path itself is real: Copter calls the four-argument
`adjust_velocity_z()` (`ArduCopter/mode.cpp:993`), and that overload does fold a
non-zero `backup_speed_cms` into the climb rate
(`AC_Avoid.cpp:396-405`). So something upstream is not publishing the limit.

The most likely gate is `flowDataValid` in `getHeightControlLimit()`
(`AP_NavEKF3_Outputs.cpp:94`): at 39.5 m with a 40 m range finder the flow
measurements are at or past the edge of validity, and that is the same regime
the review's own "loses GPS at 100 m" scenario assumes. If so the finding is
partly self-cancelling - the limit only engages where flow is still valid, which
is where the vehicle is low enough not to be driven down far. **Not confirmed**,
and confirming it needs the limit itself in the dataflash rather than a console
probe.

## Instrumentation: console probes are not trustworthy here

Recorded because it cost several runs and produced two wrong intermediate
conclusions.

`GCS_SEND_TEXT` is dropped under load. Switching to `::fprintf(stderr, ...)`
fixed the loss but not the ordering: SITL's stderr and the harness's stdout are
separate streams merged into one capture, and the test reboots SITL partway, so
a line printed by the pre-reboot instance can appear *after* a harness line from
the post-reboot one. That made a transition that the dataflash places at
PE = -89.3 m read as happening at the origin.

Anything that has to be correlated with vehicle state belongs in the dataflash.
`XKF1.PN/PE`, `XKF4.OFN/OFE` and `XKF4.AID` were right every time and disagreed
with the console every time.

So the open question from the section above - whether the reset is skipped on
this edge, or taken with `lastKnownPositionNE` already current - is still open,
and the way to settle it is a temporary log field, not another print.

## Both questions answered with a dataflash probe (2026-09-12)

A temporary `PRBE` message written from `Log_Write()` carrying, per core:
`lastKnownPositionNE`, `stateStruct.position`, `PV_AidingMode`, `flowDataValid`,
`useVelXYSource(OPTFLOW)`, `terrain_srtm_alt_valid`, and the return and value of
`getHeightControlLimit()`. That settled in two runs what four console-probe runs
could not.

### The teleport is impossible, not merely absent

`moveEKFOrigin()` (`AP_NavEKF3_core.cpp:2273`) moves `EKF_origin` onto the
vehicle **at 1 Hz** whenever there is a valid origin and GPS is in use, and
subtracts the delta from `stateStruct.position`, `outputDataNew`,
`outputDataDelayed` and every entry of `storedOutput`. The comment says it
plainly: "move the EKF origin to the current position at 1Hz. The public_origin
doesn't move."

So `stateStruct.position` is held near zero by construction while on GPS. The
absolute position is carried by `public_origin.get_distance_NE(EKF_origin)`,
which `getPosNE()` adds back (`AP_NavEKF3_Outputs.cpp:263`) - which is why
`XKF1.PN/PE` reads -90.6 m while the state itself reads -0.0.

Measured, vehicle 90.5 m from the origin at the fallback:

| t | XKF1 PN,PE | stateStruct PN,PE |
|---|---|---|
| 70.0 | -0.1, -47.6 | -0.0, -0.1 |
| 80.0 | -0.2, -90.6 | -0.0, -0.0 |
| 90.0 | -0.1, -90.6 |  0.0,  0.0 |

`ResetPosition()` assigning `stateStruct.position = lastKnownPositionNE` is
therefore a move between two near-zero numbers. The review's "a vehicle 1 km
downrange jumps 1 km to the EKF origin" requires the state to hold the full
kilometre; it cannot, because the precondition for this edge is that the vehicle
*was* navigating on GPS, which is exactly when the origin is being re-based.
**The finding is refuted at the root and no fix is needed.**

#### Superseded 2026-09-15: the origin stops following 4 s before the edge

The re-base above is gated on `filterStatus.flags.using_gps`, which is
`(imuSampleTime_ms - lastGpsPosPassTime_ms) < 4000 && AID_ABSOLUTE`
(`AP_NavEKF3_Control.cpp:812` at `8627ddedc6`). After the source switch no GPS
position passes, so the origin stops following the vehicle 4 s later, while
the fall back only fires at `posRetryTimeUseVel_ms` = 10 s. For the 6 s in
between `stateStruct.position` accumulates whatever the vehicle flies, and
`ResetPosition()` then throws exactly that away. The 2026-09-12 table is
right: that vehicle hovered through the window, so there was nothing to throw
away. "Refuted at the root" was wrong, and so was "no fix is needed".

### The height limit finding is real, and worse than stated

The EKF publishes the limit exactly as the review says. At 39.4 m with a 40 m
range finder: `AID=2 FDV=1 VXY=1 SRTM=0 HOK=1 HCL=27.0`. My earlier guess that
`flowDataValid` was gating it was **wrong** - `FDV=1`.

The reason a hovering vehicle is not driven down is `AC_Avoid.cpp:418-421`:

    // do not adjust climb_rate if level
    if (is_zero(climb_rate_cms)) {
        return;
    }

`adjust_velocity_z()` exits before it looks at the limit when the climb demand
is zero. So the consequence needs a pilot input - and then it is severe:

| | altitude |
|---|---|
| on GPS, full-up throttle 8 s | 39.5 -> **50.5 m (+11.0)** |
| on flow, limit 27 m, **same** full-up throttle | 50.5 -> **32.3 m (-18.1)** |

The vehicle descends 18 m while the pilot holds full climb. Not "it will be
commanded down to ~20 m" but "the next climb input becomes a descent", which is
a worse failure to meet in the air and is not mentioned in the PR description.

This is the finding on this PR that needs addressing.

### Scope: it is AC_Avoid only, but AC_Avoid is on by default

`AC_Avoid.cpp:459` is the **only** consumer of `AP_AHRS::get_hgt_ctrl_limit()`
in the tree; everything else is AHRS plumbing over the two EKF backends. So the
limit reaches the vehicle through avoidance or not at all.

Confirmed by measurement - same 40 m flight, same full-up throttle after the
fallback:

| AVOID_ENABLE | result |
|---|---|
| default (3) | 50.5 -> **32.3 m (-18.1)** |
| 0 | 39.4 -> **46.8 m (+7.4)** |

That is not much comfort, for three reasons:

- `AVOID_ENABLE` defaults to `AC_AVOID_STOP_AT_FENCE | AC_AVOID_USE_PROXIMITY_SENSOR`
  (`AC_Avoid.h:19`), so it is on out of the box.
- The height-limit block is **not** gated by either bit. Only the function-level
  `if (_enabled == AC_AVOID_DISABLED) return;` guards it, so a user who enabled
  avoidance purely for the fence gets the optical-flow ceiling as well.
- It is reached from every pilot-controlled altitude path -
  `get_avoidance_adjusted_climbrate_ms()` is called by ALT_HOLD, LOITER,
  POSHOLD, FLOWHOLD, CIRCLE, ZIGZAG, AUTOTUNE and GUIDED's velocity control.

So the exposure is "any vehicle with default parameters, in any normal flight
mode, the first time the pilot asks for a climb after GPS is lost".

## Moving through the fall back (2026-09-15)

Same test scenario as 2026-09-12 (fly out ~100 m on GPS, switch to the flow
source set), but with roll stick held from 3 s to 12 s after the switch, so
the vehicle is moving when the fall back fires at about 10 s. Numbers from
`XKF1` core 0 and `POS` against `SIM` truth.

| | PR head `4bb2ef3583` | with `05d1db1b9d` |
|---|---|---|
| speed at the transition | 5.4 m/s | 5.5 m/s |
| largest position step between XKF1 samples | **21.0 m** | 0.6 m (own motion) |
| largest velocity step | **5.9 m/s** | 0.06 m/s |
| EKF position error 0.5 s before | 0.6 m | 0.6 m |
| 0.5 s after | **23.6 m** | 0.6 m |
| 3 s after | **30.6 m** | 0.5 m |
| just before GPS returns | **32.7 m** | 0.2 m |

A slower first probe (2.5 m/s, pitch stick) showed the same shape: VE -2.44
to -0.01 m/s against a true -2.51, still 2.0 m/s wrong 1.1 s later, and a
4.5 m position step. The error keeps growing after the step because the
zeroed velocity has to be re-learnt from flow.

Both halves come from the mode change block calling `ResetVelocity()` and
`ResetPosition()` on every mode change. With `PV_AidingMode` already
`AID_RELATIVE`, the first zeroes the horizontal velocity and the second
assigns `lastKnownPositionNE`. Right when relative aiding starts from
AID_NONE, wrong on this edge, where flow has been aiding the states all
along.

### The fix, and the alternative the review suggested

`05d1db1b9d` skips both resets on the AID_ABSOLUTE -> AID_RELATIVE edge only.
The review suggested writing `lastKnownPositionNE` from the state before
setting AID_RELATIVE instead. That fixes the position but not the velocity,
which `ResetVelocity()` still zeroes (the 5.9 m/s step above), so it was not
taken. Derived from the source, not measured separately.

### Replay: is the velocity estimate bit-identical?

The PR body says a replay of the real flight gave a "bit-identical" velocity
estimate. That flight is not named anywhere in this archive or in the flight
analyses, so it could not be re-run (a `REPLAY_LOGS.md` row is owed). The same
phrase appears in the #33585 flight record for log308, about a different
change, so it may have been carried across. Tested instead on the SITL log of
the 2.5 m/s probe (`LOG_REPLAY=1`), replayed by three Replay builds. Core 100,
flight 40-83.5 s:

| comparison | max \|dV\| | max \|dP\| | first difference |
|---|---|---|---|
| Replay at head vs the flight | 0.000 | 0.00 | none (faithful) |
| head vs master's `Control.cpp` | **2.480 m/s** | **9.58 m** | 69.84 s, the fall back |
| `8627ddedc6` vs master's `Control.cpp` | 0.101 m/s | 0.02 m | 83.04 s, GPS returning |

So the claim is false for the PR as submitted and true for the flow segment
with the fix. The residual difference at 83.04 s is the return to GPS
resetting velocity and position through the mode change, where master
recovers in place.

## Remaining review findings, measured (2026-09-15)

### `!readyToUseGPS()` under a sustained GPS rejection - real, fixed

`readyToUseGPS()` includes `gpsDataToFuse`, true only on cycles with a GPS
sample at the fusion horizon. Probe: hover on GPS with flow velocity fused
(`EK3_SRC_OPTIONS=1`, `EK3_SRC2_VELXY=5`), then `SIM_GPS1_GLTCH_X` stepped
0.00045 deg (50 m) every 5 s for 60 s. Window glitch start to 40 s after it
ends:

| build | AID changes (core 0) | "started relative aiding" / "is using GPS" | EKF position error at +20/+40/+60 s |
|---|---|---|---|
| master `Control.cpp` | 0 | 0 / 0 | 100.2 / 300.6 / 501.0 m |
| PR head | **12** (6 round trips, 0.2 s each) | **7 / 7** | 100.2 / 300.6 / 501.0 m |
| `05d1db1b9d` | 12 | 7 / 7 | 100.2 / 300.6 / 501.0 m |
| `8627ddedc6` | 0 | 0 / 0 | 100.2 / 300.6 / 501.0 m |

Position following is identical in every build (the glitch is followed
either way; recovery after it ends took the same ~20 s), so the round trips
bought nothing but messages and, before `05d1db1b9d`, a velocity zeroing on
each one. `8627ddedc6` replaces `!readyToUseGPS()` with "GPS is the
configured position source and a 3D fix arrived within
`gpsNoFixTimeout_ms`" (`lastTimeGpsReceived_ms` is only written for a 3D
fix).

Rejected alternatives:

- `getPosXYSource() != GPS` (the review's first suggestion): stops the churn,
  but also stops the fall back for a GPS set whose receiver dies while flow
  is fused, which the PR head does handle. With `8627ddedc6` and
  `SIM_GPS1_ENABLE=0` the fall back still fires 10.6 s after the last fix
  (69.4 -> 80.04 s) and returns to GPS on re-enable. Not measured on the
  review's variant; it follows from the code.
- `!gpsIsInUse` (the review's second): `gpsIsInUse` is set false two lines
  above the test, so it is always true there. Derived from the source.

Not changed, same class: `readyToUseRangeBeacon()` and `readyToUseExtNav()`
are per-cycle as well (`rngBcn.dataToFuse`, `extNavDataToFuse`), so a rejected
beacon or ExtNav source would bounce the same way. Derived from the source,
not measured; the review raised GPS only.

### The test - extended

`6c6339bd41`: fly ~100 m out, keep moving across the fall back, assert the
transition happened more than 50 m out and above 3 m/s, and that the largest
XKF1 position and velocity steps are under 2 m and 1.5 m/s. Reboots at the
end. Fails at the PR head (21.0 m), passes with the fix (0.6 m, 0.06 m/s),
and fails with master's `Control.cpp` on "did not fall back to
AID_RELATIVE".

### Declined or already done

- XKF4's format string at the 16-character limit: no comment added.
  `CHECK_ENTRY` asserts the limit at startup, so the next field added fails
  loudly, and the macro block carries no comments to match.
- "Autotest included" checkbox: already ticked in the body by 2026-09-15.
- The height limit and #34380: already in the body by 2026-09-15.

### Side effects of AID_RELATIVE - derived from the source, not measured

At `8627ddedc6`, what else changes when this edge is taken:

- `FuseDeclination()` runs with 3-axis mag fusion (`MagFusion.cpp:440`),
  as for any vehicle that flies on flow from boot. In the Replay above it
  made no difference to velocity or position on the flow segment, but that
  SITL flight may well have been on simple yaw fusion.
- `badMagYaw` (`MagFusion.cpp:161`) needs AID_ABSOLUTE, so the
  velocity-innovation yaw reset is off, as for flow-from-boot vehicles.
- `getTerrainAltVariance()` (`Outputs.cpp:619`) starts reporting the terrain
  variance while `flowDataValid`, and `getHeightControlLimit()` (`:94`)
  starts publishing the limit (#34380).
- `status.flags.gps_glitching` and `using_gps` (`Control.cpp:812-813`) clear.

### Branch

Three commits on top of `4bb2ef3583`, unpushed. The branch is 1364 commits
behind master; the merged tree has the same 16-character XKF4 format and the
test helpers it uses. A rebase is worth it before CI is trusted again, and is a
force push.

### Reproduce (2026-09-15)

`data/2026-09-15/probe_tests.py` holds the three temporary probe tests
(velocity through the transition with `LOG_REPLAY`, sustained glitch, GPS
switched off). `glitch_stats.py <log> <glitch start> <glitch end>` and
`moving_stats.py <head log> <fix log>` produce the tables above;
`replay_compare.py` compares three Replay outputs of one log
(`build/sitl/tool/Replay <log>` per build, run from separate directories).

## Pushed 2026-09-15

Rebased onto master `bf08027404` and force-pushed as `9e04d0e0a7`. The first
rebased candidate failed OpticalFlowGPSLossAiding at 4.5 s with a TypeError:
master now requires `delay_sim_time(seconds, reason)`, and the PR's test
calls predate that. `reason` arguments were added in the two autotest commits
that introduce the calls; nothing else changed. On the pushed head the test
passes: transition at 105.5 m from the origin and 5.5 m/s, largest step
0.59 m and 0.06 m/s. OpticalFlowLimits also passes.

| measured on | pushed as |
|---|---|
| `06dcc8660b` drop to relative aiding | `cb29b3b4c1` |
| `0da9da2b2e` log AID in XKF4 | `b52fb278dd` |
| `4bb2ef3583` autotest (plus `reason` arguments) | `809cb35af7` |
| `05d1db1b9d` keep the states on the fall back | `bdef1ff967` |
| `6c6339bd41` fly through the fall back (plus `reason` arguments) | `16a019c608` |
| `8627ddedc6` do not fall back on a rejected GPS | `9e04d0e0a7` |

Reply posted 2026-09-15 11:23Z
(https://github.com/ArduPilot/ardupilot/pull/33568#issuecomment-5679359949) conceding the
teleport, correcting the "bit-identical" claim with the Replay A/B, and
covering the `readyToUseGPS()` guard, the fly-out test and #34380. The PR body
was rewritten the same day: the fall-back guard described without the old
per-cycle test, a paragraph on why the states are not reset, the corrected
bit-identical sentence, and the new test. `AIReview` was already on; the
2026-09-12 round is stale from the push.

## Round 3: drag dead reckoning and the ExtNav bounce (2026-09-17)

The 2026-09-15 automated round at `9e04d0e0a7` found two regressions from the
new ABS->REL edge, both reproduced here in SITL (tier 2), both fixed.
Not pushed. Working branch `pr-flow-aiding` at `ef6bab1803`; the tidied
branch for pushing is `pr-flow-aiding-tidy` at `816db9a9b0`, tree
byte-identical to `ef6bab1803`, same base `bf08027404`.

Rig (probe on local branch `r3-probe-33568`, never pushed): the PR's flow
source set (SRC2 POSXY none, VELXY flow, POSZ baro, YAW compass, RC8 switch),
analog range finder, FS_DR_ENABLE 0 and FS_EKF_ACTION 0 so the EKF is seen
raw, take off 10 m in LOITER, 30 s on GPS, then ALT_HOLD moving at pitch
1400. Error is GLOBAL_POSITION_INT against SIMSTATE. Variants: head
(`9e04d0e0a7`), edge disabled (`false &&` on the transition, master
behaviour), `fix1` (drag and airspeed check only), `fix2` (everything below).
The harness needed SERIAL1 moved to tcp:4 locally: port 5762 is held on the
Windows side.

### Drag dead reckoning thrown away

Drag coefficients 9.5/9.5, MCOEF 0.082. Error 40 s after flow stops:

| scenario | head | edge disabled | fix1 | fix2 |
|---|---|---|---|---|
| flow stops 5 s after the GPS->flow switch | 45.7, 45.5 m (REL then NONE) | 29.2 m (ABS) | 31.9, 29.0 m (ABS) | 31.6 m (ABS) |
| flow stops 15 s after the switch | 47.7, 46.4 m (REL then NONE) | 27.1 m (ABS) | 26.3, 27.7 m (ABS) | 26.2 m (ABS) |

With drag coefficients zero, fix1 behaves as head (45.5 m, REL then NONE),
so the change only affects drag or airspeed vehicles. Noted, not changed:
with no drag the edge-disabled build ended at 18.7 m against 45.1 m for fix2,
because master stays ABS on inertial dead reckoning until the attitude aiding
timeout while REL drops to NONE after 5 s of stale flow. SITL's IMU is near
ideal, so master's number flatters it.

### ExtNav bounce

SRC2 POSXY ExtNav (SIM vicon on serial5), VELXY flow, drag off. It only
reproduces with no GPS fix (SIM_GPS1_LCKTIME 30000 after the switch;
SIM_GPS1_ENABLE 0 stalled the harness for 11 minutes) and no ExtNav velocity
(SIM_VICON_TMASK 1), because `ResetVelocity()` otherwise resets to GPS or
ExtNav velocity and nothing visible happens. 1000 m glitch applied at
111.35 s moving at 2.6 m/s:

| build | transition | largest XKF1 speed step |
|---|---|---|
| head | REL at 121.41 s, ExtNav again at 121.44 s | 2.63 m/s (to 0.00) |
| edge disabled | none | 0.01 m/s |
| fix2 | none | 0.01 m/s |

The position follows the glitched fix (~1007 m error) in all three, as on
master. The beacon half of the guard is by reading only (tier 3).

### posTimeout on the edge

By reading: NONE->REL clears posTimeout through `ResetPosition()`; the edge
skipped the reset, so posTimeout and velTimeout stayed set and a flow dropout
cleared `horiz_vel`. Measured, a 2.5 s flow dropout after the fall back (drag
off), EKF_STATUS_REPORT horizontal velocity flag clear over the dropout plus
5 s: head 5 of 29, fix2 0 of 28, edge disabled 0 of 30 (stays ABS).

### The fix, and the new test

`b98e7b1da2` (squashing `cb29b3b4c1`, `9e04d0e0a7` and the two new guard
commits `b8e3cb25ef`, `9792ce3d0f`): the edge now needs no GPS, ExtNav or
beacon source configured for position that delivered a measurement within
gpsNoFixTimeout_ms (2 s), flow or body odometry used, and neither drag nor
airspeed used. `8a9d37773c` (squashing `bdef1ff967` and `1f80b12bac`) also
clears posTimeout on the edge.

`OpticalFlowFallbackKeepsAbsolute` (`816db9a9b0`): a 20 s stepped GPS glitch
with EK3_SRC_OPTIONS 1, then a drag leg with flow stopping 5 s after the
switch; both legs must never reach AID 2 after the first AID 0. Revert
evidence: head fails the drag leg; a build with `readyToUseGPS()` back in the
condition fails the GPS leg; fix2 passed 3 of 3, about 13 s wall. Two traps
met writing it: the filter can start in relative aiding on flow before GPS is
ready, and XKF4 logs AID 0 before the filter initialises, so the check starts
only after the first absolute sample that follows a non-zero one.

Tests at `ef6bab1803`: OpticalFlowGPSLossAiding, OpticalFlowFallbackKeepsAbsolute,
OpticalFlowLimits, OpticalFlow, DeadReckoningInWind, PAUSE_CONTINUE_GUIDED,
BeaconPosition, GPSViconSwitching, VisionPosition all pass; copter and plane
build; every AP_NavEKF3 commit on the tidied branch builds on its own; the
mechanical gate is clean on the tidied branch.

Minor items from the round: the stray `do_RTL(timeout=120)` change is gone
(folded into `202da19a57`); the first commit's message no longer describes the
superseded `readyToUseGPS` guard. Not acted on: the height limit still
engaging on the fall back (#34380, on hold on #33585).

Reply draft and body update are in the session scratchpad, not posted.
