# NEW PR (not opened) - EKF3: log XKF5 and XKFA for every core

Prospective PR against master. Implemented on branch 2026-09-09, no PR
opened yet. See "Implemented" below.

Target: master `371990d846` (2026-09-05). Both the primary-only guard and
the `XKFA` message are upstream, so this is a gap in merged code.

## Status (one line)

`XKF5` and `XKFA` are logged for the primary core only, which makes the
non-primary lane unmeasurable exactly when a per-core source
configuration is what is being tested; found while analysing a flight
that could not answer its own question because of it (log7, not
committed, 2026-09-09).

## The problem

`AP_NavEKF3_Logging.cpp:188`:

```cpp
void NavEKF3_core::Log_Write_XKF5(uint64_t time_us) const
{
    if (core_index != frontend->primary) {
        // log only primary instance for now
        return;
    }
    ...
```

`XKFA` (the AGL Kalman filter: height, velocity, accel-Z bias, validity,
velD fusion state) is written inside that function, so it inherits the
guard. Between them the two messages carry the optical-flow innovations
and test ratio, the terrain offset, the range being fused, and the entire
AGL KF state. None of it exists for a non-primary core.

That was tolerable while every core ran the same sources. It is not now.
`EK3_SRC_OPTIONS` bit 3 (`SRC_PER_CORE`) maps core N to source set N, so
a vehicle can fly a GPS lane and an optical-flow lane side by side on one
airframe - which is the best available way to measure the flow stack,
because both lanes see the same IMU, baro and rangefinder at the same
instant. The primary is the GPS lane. The flow lane, the one under test,
logs none of this.

Concretely, on the 2026-09-09 flight: the flow lane's terrain state, flow
innovations, range fusion and AGL KF are all absent, so whether
`AglKfVelForVelD` ever fused on that lane cannot be answered from the log.
Every `XKF5`/`XKFA` number in that flight's analysis is the GPS lane's,
which had to be stated as a caveat on each one. `XKF7` has no guard and is
the only reason a third velocity reset was visible at all; two of the
three were rate-limited out of the statustext stream.

## The proposed change

Not written. Drop the guard on `Log_Write_XKF5`, or gate it on the option
rather than on primacy.

Dropping it outright doubles these two messages on a two-lane vehicle.
`XKF5` is 10 Hz and `XKFA` is written at the same rate and only when
`AglKfForOptflow` or `AglKfVelForVelD` is set, so the cost is small in
absolute terms, but `../32472/`-class airframes already run tight
dataflash budgets and the logging rate is not free. Options, in order of
preference:

1. Log all cores unconditionally. Simplest, matches `XKF1`-`XKF4` and
   `XKF7`, and removes a footgun rather than adding a condition to
   remember.
2. Log all cores only when `sources.option_is_set(SRC_PER_CORE)`.
   Cheapest, but leaves the same hole for anyone comparing lanes for a
   different reason (`EK3_AFFINITY`, a lane-switch investigation).
3. A `LOG_*` bit. Most control, most parameter surface, and nobody will
   set it before the flight where they needed it.

Preference is 1, with 2 as the fallback if a reviewer objects on bandwidth.
The comment says "for now", which suggests the guard was expedient rather
than designed; the same guard is on `Log_Write_Beacon`,
`Log_Write_BodyOdom` and `Log_Write_State_Variances`, and the argument for
changing those is weaker, so leave them.

## Validation

Not a behaviour change, so the cascade barely applies - but the claim
"the data appears" is still a claim.

- **SITL**: fly `EK3_SRC_OPTIONS=8` with two cores and confirm `XKF5` and
  `XKFA` both carry `C=0` and `C=1`, and that the values differ where the
  lanes differ (the flow lane's `XKF5.rng` should freeze when its
  rangefinder stops fusing while the GPS lane's does whatever it does).
  Two messages appearing is not enough; identical content on both cores
  would mean the split is not real.
- **Dataflash**: record the logging rate before and after on the same
  SITL run, so the bandwidth argument is answered with a number rather
  than an estimate.
- No autotest proposed. A test that asserts a message exists is the kind
  of test `../32972/` records as discriminating nothing.

## Implemented 2026-09-09

Option 1 above, the unconditional version. `SmallFastDrone-4.7.1-beta`
commit `e825b34855`, on base `fd37f6f5fa`. The guard is gone from
`Log_Write_XKF5`; `Log_Write_Beacon`, `Log_Write_BodyOdom` and
`Log_Write_State_Variances` keep theirs as argued above.

The "no autotest proposed" position above is withdrawn. It was aimed at a
test that asserts a message exists, which discriminates nothing; a test
that also requires the two cores to *differ* does discriminate, and that
is what was written. `EK3_PerCoreOptflowLogging` in
`Tools/autotest/arducopter.py` flies the `EKF3SRCPerCore` configuration
(GPS on core 0, VICON on core 1 via `EK3_SRC_OPTIONS=8`) with
`EK3_OPTIONS` bit 3 set so `XKFA` is written at all, glitches VICON to
force the lanes apart, and then requires both messages to carry `C=0` and
`C=1` and their `HAGL`/`HAgl` series not to be a prefix of one another.

Measured on that test, 2026-09-09, at the commits above:

| | `XKF5` cores | `XKFA` cores |
|---|---|---|
| base `fd37f6f5fa` | `[0]` | `[0]` |
| with `e825b34855` | `[0, 1]` | `[0, 1]` |

The test fails on the base commit with "XKF5 was not logged for both
cores (saw [0])", so it discriminates.

**Still outstanding:** the dataflash rate before and after on the same
SITL run. The bandwidth argument above is still an estimate, and the
fallback to option 2 has not been costed. Do that before opening the PR,
because it is the one objection a reviewer is likely to raise.

## What is here

```
new-ekf3-percore-optflow-logging/
  README.md    <- this file
```

The code is on `SmallFastDrone-4.7.1-beta` (`e825b34855`) with its
autotest in `Tools/autotest/arducopter.py`.

## Related

- `../33484/` - `XKF7`, which is per-core and proved the point.
- `../33478/`, `../33507/` - the AGL KF state that `XKFA` carries.
