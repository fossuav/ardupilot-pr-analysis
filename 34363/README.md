# PR #34363 - EKF3: log XKF5 and XKFA for every core

Analysis archive for [ArduPilot/ardupilot#34363](https://github.com/ArduPilot/ardupilot/pull/34363).
Branch `ekf3-percore-optflow-logging` (andyp1per fork), two commits, head
`38f4f2d1ee`, base master `5b6115d65d`. Opened 2026-09-10.

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

### The bandwidth number, measured 2026-09-10

The outstanding item above is answered. Measured on the same autotest with
and without the guard: **21.9 kB/s of log becomes 22.5 kB/s**, +597 B/s for
the two messages, 2.7% of the log.

Sizes are 45 B for `XKF5` and 29 B for `XKFA` on disk. Copter writes them at
10 Hz, or 25 Hz with `MASK_LOG_ATTITUDE_FAST`, so per additional core the
ceiling is +450 B/s (XKF5 at 10 Hz), +1.13 kB/s at 25 Hz, plus +290 B/s for
XKFA where `EK3_OPTIONS` bit 3 is set. Three cores at 25 Hz with both
messages is +3.70 kB/s, the worst case.

Small-board risk is low. `LOG_FILE_BUFSIZE` is 16 kB on the smallest boards,
so +740 B/s is about 4.5% of one second of buffer; the rate limiter takes one
decision per message id per tick and applies it to every instance, so a
budget-limited user drops both cores together rather than one core starving
the other; and `EK3_LOG_LEVEL=1` still removes `XKF5` outright. Option 1
stands.

### Two corrections from review, 2026-09-10

**The differ-check in the first version of the test discriminated nothing,
and its rationale was wrong.** It required the two cores' height series not
to be a prefix of one another, to guard against "logging the primary twice".
That cannot happen: `C` is written from `DAL_CORE(core_index)`, so a
duplicated primary carries the same `C` and the both-cores assertion already
catches it. Worse, the check passes on any two cores merely because they run
different IMUs - measured at 19.8% of samples differing with both cores on
the *same* source set - and for `XKFA` the field is a float, where exact
equality between two independently integrated cores is effectively
impossible, so that half could never fire. Replaced with an `XKFS` assertion
that the two cores are on different source sets, which is the premise the
test actually needs.

**`LogStructure.h` described `XKF5` as "(primary core)"** and that feeds the
generated log documentation. Corrected. `XKV1` and `XKV2` still say it and
are still right, because those keep the guard.

**Any FAILED transcript for this test in an old buildlogs tree is a stale
binary, not the fix failing.** In those runs the first boot log already shows
`XKF1` carrying both cores while `XKF5` carries only core 0, which is the
unfixed code path.

## What is here

```
34363/
  README.md    <- this file
```

The code is on `SmallFastDrone-4.7.1-beta` (`e825b34855`) with its
autotest in `Tools/autotest/arducopter.py`.

## Related

- `../33484/` - `XKF7`, which is per-core and proved the point.
- `../33478/`, `../33507/` - the AGL KF state that `XKFA` carries.
