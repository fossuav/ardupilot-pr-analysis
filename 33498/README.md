# PR #33498 - inhibit Z gyro bias from optical flow when there is no yaw source

Analysis archive for [ArduPilot/ardupilot#33498](https://github.com/ArduPilot/ardupilot/pull/33498).
Branch `pr-gyro-z-unobservable-without-yaw` (andyp1per fork), base `master`.
All evidence is from real flights on a 4-inch optical-flow quad (MatekH743,
ARK Flow, no compass in the flow source set); numbers are cited inline and no
logs are committed.

## Status (one line)

One-commit correctness fix, flight-validated on the airframe that exposed it
and reconfirmed on a later flight; no SITL reproduction yet (see Reproduce).

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
