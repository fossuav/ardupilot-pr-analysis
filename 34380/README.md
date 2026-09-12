# PR #34380 - AC_Avoid: do not back away from the optical flow height limit

Analysis archive for [ArduPilot/ardupilot#34380](https://github.com/ArduPilot/ardupilot/pull/34380).
Branch `pr-avoid-flow-ceiling-backup`, head `88277a54a7`, base master
`37ea692edb` (2026-09-12). Two commits. Opened 2026-09-12.

## Status (one line)

`adjust_velocity_z()` backed the vehicle down from the EKF optical-flow ceiling
the same way it backs away from a fence breach, so a climb demand became a
descent. Now the ceiling refuses the climb and the vehicle holds altitude; fence
and proximity backup unchanged. Pre-existing on master, not caused by #33568.

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
