# PR #35312 - EKF3 keeps a landed flow lane's velocity variance honest

Analysis archive for [ArduPilot/ardupilot#35312](https://github.com/ArduPilot/ardupilot/pull/35312).

Opened 2026-11-20 at `6b8a26e145`, branch `pr-flow-lockout-landed`,
stacked on #35307 (`80e1cb5824`): `78944cda59` (AP_NavEKF3) and
`6b8a26e145` (autotest). On by default, as a fix for a divergence.

## What it does

While a flow lane is armed, the vehicle reports it has landed, takeoff is
not detected, the range is current and reads within 0.1 m of the ground
clearance, the horizontal velocity variance is held at
`sq(MIN(EK3_NOAID_M_NSE, 1))` (the stationary zero velocity noise) or the
squared speed estimate if more, capped at 1e3. The velocity is never set.

## Why

On the ground the flow is scaled by the ground clearance and, before
takeoff detection, replaced by zero, which is fused at the flow's own
noise. A touchdown that leaves a few tenths of a m/s of error then
predicts several rad/s; one axis is rejected until disarm while an accel
bias walks the velocity away. Since #35105 a landed Copter is on the
ground while armed, which clears takeoff detection, so #33484's lockout
recovery does not run there.

## How the design got here

1. Letting the recovery reset while landed (first version): review found
   it opened on the bench (landed holds disarmed) and that the reset set
   the velocity from the landed flag alone, as the flow is already zeroed
   there: a fabricated measurement from a flight-state flag.
2. Raising the variance only while an axis was locked out: cleared 6 of 7
   replayed landed runaways, missed one whose AGL KF restart never
   confirmed under the beta's floor hold (gate required a Good range
   state) and whose error was already 7-12 m/s at landing (1 m/s variance
   too small), and made a hopping log worse in flight: once unlocked, the
   zero flow at 5 cm collapsed the variance to about 1 cm/s and the next
   liftoff rejected the real flow.
3. Final: hold the variance for as long as landed (not only in a
   lockout), accept any non-stale range, cover the speed estimate.

## Evidence

- SITL: two legs (AGL KF off and on), landed and armed, accel bias pulse
  3 m/s^2 then 0.3 residual. Without the change the axis is shut out and
  both cores reach 5.2 m/s in 12 s; with it the flow is never shut out
  and the velocity is back within 0.3 m/s 1.5 s after the pulse (peak
  0.91 m/s during it). The other 15 Copter flow tests pass.
- Fleet Replay (tier 1b, 423 logs, landed flag rebuilt from each log's EV
  LAND_COMPLETE/NOT_LANDED, since none carries RFRN Flags2): of 117 lanes
  landed and armed for over 3 s, 7 exceeded 0.5 m/s on the ground (worst
  15.3); with the change 0. GPS p95 lower on 7 cores, higher on 8, summed
  -1.2 m/s. One hopping log 2.86 -> 3.84 m/s p95: its flow lane is
  rejected through most hops in both builds, differences between hops.

## Found along the way

- #35307 bug, fixed in `80e1cb5824`: a pending height source switch let
  the recovery scale by the baro's height for one update when the range
  finder came back as the height source (about one SITL run in five).
- Not covered here: a lane quality-latched into AID_NONE before landing
  drifts on the ground when idling motors keep onGroundNotMoving false.
- A range finder that reads below its minimum on the floor needs #32232's
  substitution; on master its range is stale and nothing is held.

## 2026-11-20: restacked, pushed `64196a8a82`

Carried onto #35307's `0fec57455e` with no change of its own. With
#33484's new-reading test, an assumed or held range now reads stale here
too, so nothing is held on one.
