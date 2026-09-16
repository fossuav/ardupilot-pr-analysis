# PR #34380 - AC_Avoid: do not back away from the optical flow height limit

Analysis archive for [ArduPilot/ardupilot#34380](https://github.com/ArduPilot/ardupilot/pull/34380).
Branch `pr-avoid-flow-ceiling-backup`, head `88277a54a7`, base master
`37ea692edb` (2026-09-12). Two commits. Opened 2026-09-12.

## Status (one line)

`adjust_velocity_z()` backed the vehicle down from the EKF optical-flow ceiling
the same way it backs away from a fence breach, so a climb demand became a
descent. Now the ceiling refuses the climb and the vehicle holds altitude; fence
and proximity backup unchanged. Pre-existing on master, not caused by #33568.

### Superseded 2026-09-16 by the removal of the limit

rmackay9 proposed on #33585 (2026-09-15) making above-rangefinder-range flow
navigation the default and removing `get_hgt_ctrl_limit()` and the vertical
avoidance code this PR touched; the user agreed that this PR becomes that
removal. The backup-gating commits are dropped, since with no limit there is
nothing to gate. Local branch `pr-avoid-flow-ceiling-removal`, stacked on #33585
at `e18c7d6fc3`, unpushed; see "Repurposed as the height limit removal
(2026-09-16)". The status above is left because it records what the pushed PR
still says and why the backup was wrong.

## How it was found

Out of the #33568 review. That round claimed the relative-aiding fallback would
"command a copter that loses GPS at 100 m down to ~20 m AGL". Tracing it with a
dataflash probe (see `../33568/`) showed the EKF does publish the limit, that
`AC_Avoid.cpp:459` is its **only** consumer in the tree, and that nothing happens
at all in a hover because `adjust_velocity_z()` returns on a zero climb demand
(`AC_Avoid.cpp:418-421`). With a climb demand it was worse than the round said.

## The defect

`adjust_velocity_z()` collects a maximum-altitude limit from three sources - the
`ALT_MAX` fence, `AP_AHRS::get_hgt_ctrl_limit()`, and the proximity sensor's
upward distance - keeps the closest, and applies one response: clamp the climb
rate to zero, then compute a backup speed at `AVOID_BACKZ_SPD` (default 0.75 m/s)
that drives the vehicle back under the limit.

Backup is right for the fence and proximity, which the vehicle has entered and
should leave. The flow ceiling is a "do not go higher" constraint with nothing to
leave, so the backup turns a climb demand into a descent.

The fix records whether the binding source allows backup - set for fence and
proximity, clear for the EKF limit - and gates only the backup on it. The climb
clamp still applies to all three.

## Measurements

SITL copter holding station above the ceiling, full up stick for 8 s:

| build | altitude |
|---|---|
| master (default avoidance) | 25.3 -> **18.7 m** (and 50.5 -> 32.3 m in the #33568 rig) |
| this PR | 25.2 -> **25.2 m** |
| `AVOID_ENABLE = 0` | +7.4 m, climbs normally |

`MaxAltFenceAvoid` and `MinAltFenceAvoid` pass on the committed branch, which is
what holds the fence behaviour.

## The test

`FlowCeilingDoesNotBackUp` flies optical flow with **no GPS**, so the filter is in
AID_RELATIVE on master without needing #33568. It climbs to 25 m under a ceiling
derived from `RNGFND1_MAX = 60` (41 m), then drops `RNGFND1_MAX` to 20 in flight
so the ceiling (13 m) sits below a vehicle already established above it, and
applies full up stick.

Shrinking the range finder limit in flight is the essential trick: you cannot get
above the ceiling by climbing, because the ceiling is what stops the climb.

Fails on master with "flow ceiling drove the vehicle down against a climb demand
(25.3 -> 18.7 m)".

## Exposure, for reviewers who ask whether it matters

- `AVOID_ENABLE` defaults to `STOP_AT_FENCE | USE_PROXIMITY_SENSOR`
  (`AC_Avoid.h:19`), so it is on out of the box.
- Neither bit gates the height-limit block; only the function-level
  `_enabled == AC_AVOID_DISABLED` does. A user who enabled avoidance only for the
  fence inherits the flow ceiling.
- `get_avoidance_adjusted_climbrate_ms()` is called by ALT_HOLD, LOITER, POSHOLD,
  FLOWHOLD, CIRCLE, ZIGZAG, AUTOTUNE and GUIDED velocity control.
- #33568 widens the population: before it, only vehicles that boot without GPS
  reach AID_RELATIVE; after it, a GPS-booted vehicle that loses GPS does too.

## Rejected alternative

Narrowing the EKF gate in `getHeightControlLimit()` so the ceiling does not apply
after a GPS-to-flow fallback. Rejected because it removes the protection where it
is most needed (a vehicle that lost GPS high has no valid flow height), because
`getEkfControlLimits()` gates its speed limit and gain detune on the same
`AID_RELATIVE` and splitting them is incoherent, and because the designed escape
already exists - the ceiling is dropped when terrain data is valid. The defect is
the backup, not the ceiling.

## Repurposed as the height limit removal (2026-09-16)

Why: rmackay9's comment on #33585 (2026-09-15T23:30Z) proposed making the
behaviour of #33585's bit 5 the default and deleting the limit. The reply on
#33585 (2026-09-16 16:00Z) agreed, with three caveats (uneven ground under the
frozen terrain offset, EKF2 losing its limit with no above-range mode, and flow
sensor quality with height), and said this PR stacks on #33585 because removing
the ceiling first lets a default-configured flow vehicle climb into the failsafe.

### What is removed

`AC_Avoid::adjust_velocity_z()` was the only consumer of
`AP_AHRS::get_hgt_ctrl_limit()` anywhere in the tree (grep over all vehicles,
libraries, AP_Scripting bindings and docs, AP_DAL, Replay, GCS_MAVLink and
Tools found no other reference). Removed, one subsystem per commit, consumer
first so every commit builds:

| commit | what |
|---|---|
| `4b94a1b529` | AC_Avoidance: the EKF limit source in `adjust_velocity_z()`, and its now-unused `_ahrs` local; fence and proximity code unchanged |
| `645928ddff` | AP_AHRS: `get_hgt_ctrl_limit()`, the `control_height_limit_m/_valid` estimates fields, the NavEKF2/NavEKF3 backend writes and the commented placeholders in DCM, External and SIM |
| `0bc9d8351a` | AP_NavEKF3: `getHeightControlLimit()` (frontend and core); the EK3_OPTIONS bit 5 description loses its sentence about terrain data removing the limit. `terrainAltUsable()` stays, it has two other callers |
| `6fadf4e0bb` | AP_NavEKF2: `getHeightControlLimit()` (frontend and core) |
| `dc841b8fd1` | autotest: OpticalFlowLimits climbs past the rangefinder range; EK3_OptflowAssumeFlatGnd drops `AVOID_ENABLE 0` |

SITL builds of copter, heli, plane, rover, sub, blimp, antennatracker and Replay
are clean with no warnings. Mechanical gate clean.

### Measured (SITL, 2026-09-16)

Temporary probe test, not committed: flow-only copter with no GPS, default
`AVOID_ENABLE` (3), `RNGFND1_MAX` 40 (old limit 27 m), take off in ALT_HOLD, 10 s
in LOITER, full climb demand for 60 s or to 60 m, 25 s hold, LAND.

| build | EKF origin | max alt | relative position | outcome |
|---|---|---|---|---|
| #33585 head `e18c7d6fc3`, limit in place | no | 27.1 m | valid | capped |
| removal `6fadf4e0bb`, bit 5 clear | no | 60.2 m | lost at 49.7 m | no failsafe: `ekf_check()` returns without an origin |
| removal, bit 5 clear | yes | 53.1 m | lost at 49.5 m | "EKF variance: position lost", EKF failsafe to LAND at 51.4 m |
| removal, bit 5 set | no | 60.2 m | valid (flags 0x12f above range) | no failsafe |
| removal, bit 5 set | yes | 62.0 m | valid | no failsafe |

The bit-5-clear row with an origin is the reason for stacking on #33585.

OpticalFlowLimits at `dc841b8fd1` passes (highest altitude 59.5 m). Revert
evidence: the same test on #33585 alone fails "Climb stopped at 27.1m"; on the
removal with bit 5 cleared it fails "Relative position lost at 51.2m". Also
passing at `dc841b8fd1`: EK3_OptflowAssumeFlatGnd (now at default avoidance),
MaxAltFenceAvoid, MinAltFenceAvoid, OpticalFlow, and Copter Replay (its optical
flow bit flies OpticalFlowLimits). OpticalFlowGPSLossAiding is not on this stack.

### Open: LAND after a high flow climb did not disarm

Traced 2026-09-16 in `../34292/` ("The stuck flow landing" and "The hold and the ground clearance floor"): phantom flow fused below the ground clearance at touchdown after a long above-range flight, stuck 5 of 5; not avoidance (`AVOID_ENABLE 0` stuck 2 of 3 in wind); master fuses the same samples but disarmed 8 of 8 in-range. Fixed on #34292 at `6f1d116306` with no user settings: a floor 5 cm above the ground clearance plus a hold after the rangefinder drops out low, 5 of 5 disarmed on this stack (and 5 of 5 with `FLOW_HGT_MIN` 0.3 and `RNGFND1_MIN` 0.2, where the unheld gate stuck 2 of 5). The draft body's landing item now says so and recommends #34292.

Observed, mechanism traced from the dataflash, cause of the configuration split
not established (tier 2 symptom, tier 3 for why).

| build | avoidance | LAND after the 60 m climb |
|---|---|---|
| removal, bit 5 set, no origin | default | not disarmed in 180 s |
| removal, bit 5 set, origin | default | not disarmed in 150 s (2 of 2) |
| #33585 head, bit 5 set, origin | `AVOID_ENABLE 0` | disarmed after 58 s (3 of 3) |
| removal, bit 5 set, origin | `AVOID_ENABLE 0` | disarmed after 58 s |

In a stuck run the descent was normal, but at touchdown the EKF position
estimate stepped about 1.4 m east (PE -7.62 to -8.99 m) while the LAND target
stayed at -7.42 m. The horizontal controller demanded up to 30 deg of pitch on
the ground, and `update_land_detector()`'s `large_angle_request` (above 15 deg)
reset the counter every cycle, so `land_complete_maybe` never set and
`NE_soften_for_landing()` (`ArduCopter/mode.cpp:785`) never relaxed the target.
In the good run the step was smaller, the target was softened within about 1 s
and the vehicle disarmed. The land path makes no avoidance call, and these SITL
runs are close to deterministic (the trajectories agree to centimetres), so the
3-against-4 split is weak evidence that avoidance is involved. The #33498 round
of 2026-09-15 saw the same symptom (a 30 deg demand held on the ground, no
disarm) in LAND with a flow scale error on an unrelated branch. It is not caused
by the removal code, but the removal makes high flow flights with avoidance on
reachable, so it needs tracing before this merges.

### Drafts (not posted)

Title "AC_Avoidance: remove the EKF optical flow height limit", body and a
repurpose comment in the session scratchpad.
