# PR #34292 - optical flow minimum focus height (FLOW_HGT_MIN)

Analysis archive for [ArduPilot/ardupilot#34292](https://github.com/ArduPilot/ardupilot/pull/34292).
Branch `pr-flow-hgt-min` (andyp1per fork), base `master`, head 292ec09fef.

Split out of #33484 on 2026-09-04 after rmackay9 reviewed the parameter there
and asked for it to live in the flow library. The mechanism is unchanged from
the version flown on that branch; what moved is where the parameter lives and
how its value reaches the filter.

## Status

Mechanism flight-validated on the 4-inch quad as `EK3_FLOW_MIN_H` (log67, see
#33484's README). Re-implemented as `FLOW_HGT_MIN` in the flow library and
re-verified in SITL; the re-implementation itself has not been flown.

## What it does

An optical flow sensor cannot focus close to the ground and what it returns
there is not motion. Below the sensor's minimum focus height the EKF treats
the flow as zero motion rather than dead reckoning a phantom velocity from it.
The check is driven by the rangefinder, which keeps reporting where the flow
does not.

## Why the parameter moved

The height is a property of the sensor, not the estimator, and belongs beside
the mounting position and `FLOW_HGT_OVR` where someone configuring a flow
sensor will look.

The *decision* did not move with it, for two reasons found while doing the
work:

- The flow library has no height above ground - no rangefinder dependency and
  nothing beyond rover's static `FLOW_HGT_OVR`. Doing the comparison there
  needs its own rangefinder access and tilt correction, which is a second and
  worse answer to a question the EKF already answers at the fusion time
  horizon.
- Suppressing the sample in the library is not the same behaviour. Quality 0
  makes the filter stop fusing and dead reckon, which is the failure being
  prevented. Zeroing the rate leaves the body rate term in `flowRadXYcomp`
  (`ofDataNew.flowRadXYcomp = flowRadXY + bodyRadXYZ`), so the filter sees
  apparent motion equal to the gyro.

So the sensor states "this sample is untrustworthy" and the estimator decides
"therefore assume zero motion".

## How the value reaches the EKF

As data travelling with the sample it describes, exactly as `FLOW_HGT_OVR`
already does: `AP_OpticalFlow::update()` -> `AP_AHRS::writeOptFlowMeas()` ->
`NavEKF3::writeOptFlowMeas()` -> `of_elements.minHeight`, and into the DAL
`ROFH` record so Replay feeds the filter the value the flight used. Reading it
out of the flow library's parameters from EKF code would not replay.

`AP_NavEKF2` gains no behaviour but has to round-trip the field. Both
estimators write the shared `ROFH` record; if only EKF3 passed the value the
two writes would differ on every sample and `WRITE_REPLAY_BLOCK_IFCHANGED`
would log two flow records per sample, which replay would feed back as two
samples.

## Default

0, off, in the manner of `VISO_QUAL_MIN`. Sensors do not share a focus height.

The check only has effect above `RNGFNDx_MIN`, because below that the
rangefinder stops returning `Good` samples, `rngValidMeaTime_ms` goes stale
and the 500 ms freshness gate fails. With the `RNGFNDx_MIN` default of 0.20 m
a floor below that can never fire. The airframe this was flown on had a
rangefinder valid to 1 cm, which is why 0.1 m worked there - it is a property
of the rangefinder fitted, not a safe global default.

## Evidence

Flight (as `EK3_FLOW_MIN_H`, 4-inch quad, log67, descent through the floor at
rangefinder 0.115 -> 0.054 m): `FIX/FIY` +/-2000-6700 -> +/-200-500, `NI`
pinned 255 -> 3-40, phantom `VN/VE` +/-0.5 -> +/-0.1 m/s, DesRoll/Pitch
+/-14 -> +/-2 deg. Operator: "althold type behaviour close to the ground but
no sudden lean".

SITL (`Copter.OpticalFlowFocusHeight`, three runs): hover in an asserted
altitude band below the floor on flow-only nav, inject a one-axis flow rate
offset with `SIM_FLOW_OFS_X`. Peak EKF groundspeed 0.029-0.031 m/s with the
floor set against 0.90-1.22 m/s without it.

## Plot (`plots/flow_hgt_min_ab.png`)

One binary, `FLOW_HGT_MIN` 3.0 against 0 - the floor is fully behind the
parameter, so 0 is master's behaviour and no second build is needed.

The figure plots EKF horizontal speed from `XKF1` over the whole 30 s window
and peaks at 0.04 m/s against 2.50 m/s. The autotest numbers above
(0.029-0.031 against 0.90-1.22 m/s) are the same runs measured differently:
`wait_groundspeed` reports the first sample crossing its bound rather than
the peak, so it reads lower on the diverging arm. Neither is wrong; quote the
autotest bounds when talking about the test and the peaks when reading the
plot.

## Known limit

Zeroed flow does not pin velocity against a continuous divergence force - a
1.5 m/s^2 accel bias ran to 27 m/s in an early test. That is not the
near-ground failure, which is bad flow on a nearly stationary vehicle, and is
what the lockout recovery in #33484 addresses.

## Gotcha worth remembering

Adding `minHeight` to `log_ROFH` without updating the `"ffffIffffB"` format
string made the binary refuse to boot with `Config Error: Log structures
invalid`. It surfaced as autotest failing with "Failed to set RC values" and
as every ad-hoc SITL probe reading nothing, which looked like a broken
plumbing chain for some time. The format string, the field-name list, the
units and the mult strings all have to grow together.

## Relationship to #33484

Both branches add a field to `of_elements` and extend `writeOptFlowMeas`, so
whichever merges second needs a small rebase. Otherwise independent and
reviewable in either order.
