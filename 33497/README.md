# PR #33497 - FLOW_HF_RATEF: correct a HereFlow node's output rate

Analysis archive for [ArduPilot/ardupilot#33497](https://github.com/ArduPilot/ardupilot/pull/33497).
Branch `pr-hflow-scale` (andyp1per fork), base `master`. Evidence is from
real flights on a 4-inch optical-flow quad (MatekH743, ARK Flow over
DroneCAN, downward rangefinder, GPS carried as truth); no logs are committed.

## Status (one line)

One-parameter driver fix, flight-validated (sensor rate slope 0.52 -> 1.00);
no SITL reproduction is possible without a DroneCAN flow node in SITL.

## The problem

Flow-based velocity read about half the GPS-implied translation on both axes
(logs 48/49). The obvious conclusion, "set both `FLOW_FXSCALER`/`FYSCALER` to
~+700", is wrong, and the onboard FlowCal said "no better scalar".

## The conclusion and why

The node clocks its whole output at half rate. Regressing the node's reported
body rate (`ROFH.GX/GY`) against the flight-controller IMU gyro during
rotation gives a slope of 0.48 (corr 0.93-0.99): flow and the node's own gyro
are both half of truth, by the same factor. The HereFlow driver forms both as
`integral * (1 / integration_interval)` with the interval taken verbatim from
the CAN message, so one ~2x-too-large interval halves both.

That is why everything pointed the wrong way. FlowCal fits flow against the
node's own gyro, both halved, so it is perfectly self-consistent and
structurally blind to a common rate error. And a `FLOW_*SCALER` cannot fix
it: it scales `flowRate` but not `bodyRate`, so +700 corrects translation
while injecting phantom flow on every rotation (2 * half_flow - half_gyro is
not zero). `FLOW_HF_RATEF` scales `integralToRate`, correcting flow and gyro
together so the EKF gyro compensation stays valid. Default 1.0 is a no-op.

## Key findings

### It is in the node firmware, not a node setting

Raising the node's `IMU_INTEG_RATE` 200 -> 400 did not move the ratio
(log50: slope 0.52, publish rate unchanged ~47 Hz). The 2x is baked into the
reported `integration_interval`; the flight-controller-side correction is the
practical fix while the node vendor is informed.

### Height was ruled out first

A height error masquerades as a flow scale error (ratio ~ height_used /
true_height). Comparing dRFND/dt against the GPS-Doppler climb rate,
independent of terrain and flow, gave a slope of 0.93 on both logs: the
rangefinder is right. The baro climb was inflated 1.5-2x near the ground, so
baro/EKF altitude must not be used as the height reference for this check.

### Not inherent to the sensor model

An earlier outdoor grass Loiter on a different ARK Flow vehicle returned
flow/ideal 0.97. The half-rate is specific to this unit/configuration.

### Validation

Flown on the 4-inch quad, log52 (not committed), `FLOW_HF_RATEF` 1.0 -> 1.92:
sensor-rate slope 0.52 -> 1.00, flow/ideal 0.50 -> ~1.0 on both axes,
cross-axis 1-2%. The next flight, the first flow-only Loiter on the airframe,
had no flyaway and exposed the separate yaw-drift trap in #33498.

### How to measure it

Set `FLOW_HF_RATEF = 1 / slope`, where slope is the node body rate regressed
against the FC IMU gyro during rotation. The flow-cal check used here rotates
GPS NED velocity into body axes via yaw, divides by the height the EKF uses
(AGL-KF height, else rangefinder), fits that against the gyro-compensated
flow over fast-motion samples per body axis, runs the sensor-rate check
first, and suppresses any scaler suggestion when the slope is not ~1.0. One
mixed forward/back plus strafe flight calibrates both axes; strafe means
translate sideways without yawing the nose into the travel.

## What is here

```
33497/
  README.md    <- this file
```

No logs committed; logs 48, 49, 50 and 52 are cited by number only.

## Reproduce

Not reproducible in SITL: the SITL flow backend is not the HereFlow driver,
and the fault is the node's reported integration interval. The parameter is
a scalar on `integralToRate` in `AP_OpticalFlow_HereFlow.cpp`; the check that
matters is the sensor-rate regression above on a real log.

## Branches and people

- `pr-hflow-scale` - the PR branch (one commit).
- Author: @andyp1per. No review yet.
- Open question for the description: it names both an "Holybro H-Flow" and
  an "ARK Flow"; the flights here were on an ARK Flow.
