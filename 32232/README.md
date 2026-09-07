# PR #32232 - Range finder ground clearance fusion (EKF3)

Analysis archive for [ArduPilot/ardupilot#32232](https://github.com/ArduPilot/ardupilot/pull/32232).
Branch `ek3_gnd_clear` (rishabsingh3003 fork). PR head at the time of this
work was `a628150687`; the local branch carried nine further commits
answering review. Commits 1-2 are rmackay9's and rishabsingh3003's and were
not rewritten. All numbers below are SITL; no real-flight logs.

## Status (one line)

Review comments from IamPete1 and tridge answered, an autotest added and
A/B'd, and four defects found that are in the original two commits rather
than in the review responses.

## What the PR actually does

Not what its description says. On the base branch the on-ground
substitution was **unreachable** for an out-of-range-low sensor:

```cpp
if ((orientation == PITCH_270) && (status == Good)) { ...store... }
else { continue; }              // <- OutOfRangeLow leaves here
...
} else if (onGround && ((imuSampleTime_ms - rngValidMeaTime_ms) > 200)) {
```

The `else if` was only reachable with status `Good` and fewer than three
fresh samples. So `757de98a10` **adds a new fusion path** (synthetic range
on `OutOfRangeLow`) and `a628150687` re-gates it; the PR body describes it
as moving an existing gate. Reached independently by two reviewers and by
reading `git show 4572849674:...Measurements.cpp`.

## SITL A/B (autotest EKF3RangeFinderOnGround, 2026-09-07)

Subtest 1 arms, sits stationary, and walks the baro away at 0.3 m/s for
20 s with `EK3_SRC1_POSZ=2`, `RNGFND1_GNDCLR=0.4`, `RNGFND1_MIN=1.0`.

| Build | EKF height while armed on the ground |
|---|---|
| Branch (`!movedSinceArming` gate) | **-0.01 m** |
| Gate reverted to `onGround` (pre-PR) | **+4.61 m**, follows the baro |

The revert fails the test with `EKF followed the drifting baro on the
ground (z=-4.61m, want<1m)`. 4.6 m of separation against a 1 m bound.

Mechanism for the revert case: `calcFiltBaroOffset()` runs only while the
active height source is not baro (`PosVelFusion.cpp:1337`), so when
`fallback_to_baro` fires the offset freezes and all subsequent drift enters
`hgtMea = baroDataDelayed.hgt - baroHgtOffset`.

Subtests 2 and 3, same run: sensor coming into range on the climb gave
6.5 m true / 6.9 m estimated; sensor never in range (`RNGFND1_MIN=50`) gave
6.4 m true / 5.9 m estimated. Subtest 3 is the dangerous direction - a
pinned estimate would read ~0.4 m.

## Tried and rejected

**`!inFlight` as a second release term.** Proposed as belt-and-braces,
withdrawn before it was written. `AP_NavEKF3/CLAUDE.md:500`: the
fly-forward branch of `detectFlight()` needs GPS ground speed > 5 m/s, so
on a GPS-denied plane `inFlight` never becomes true for the whole flight.
The belt would have been absent exactly on the vehicle class tridge raised
the rename against, and a Copter-only autotest cannot see the difference.

**`optFlowTakeoffDetected` as the rename** (tridge's literal suggestion).
Would have needed a second, near-identical motion latch for the range
finder consumer, since the flag now has two. Renamed to
`movedSinceArming` instead - EKF2 already gates the same substitution on
the same flag (`AP_NavEKF2_Measurements.cpp:99`), so it was never purely
optical flow state.

**A `rngValidMeaTime_ms` freshness gate on the range term** (commit
`234ab3d60a`, answering tridge's "relies on valid rangefinder data").
It is a no-op and should be dropped: `detectFlight()` refreshes
`rngAtStartOfFlight` from `rangeDataNew.rng` on every on-ground cycle
(`VehicleStatus.cpp:423`), so both operands hold the same stale value when
the sensor is quiet, and the substitution itself sets `rngValidMeaTime_ms`
(`Measurements.cpp:109`), so the gate reads "the buffer was written
recently", not "the sensor has data".

## Chosen: get_time_flying_ms() as the independent release

The gyro term is taken on the DAL's **10 Hz filtered** rate
(`AP_DAL_InertialSensor.cpp:68-78`, deliberately independent of
`INS_GYRO_FILTER`), so 0.1 rad/s is 5.7 deg/s of smoothed body rate, and
the range term cannot fire while the substitution runs. That left one
threshold between the filter and a pinned height estimate.

`dal.get_time_flying_ms()` is already recorded in `RFRH` (`AP_DAL.cpp:56`),
so no DAL struct grows and Replay is unaffected. It is driven from the
vehicle's own land detector, so unlike `inFlight` it is set on every
vehicle type - though on Rover, Sub and Tracker `set_likely_flying()` is
just the armed flag, so it reduces to 5 s after arming there. The term only
ever releases the substitution earlier, so it cannot make the estimate
worse than the arming-time gate it replaces.

## Bound chosen, and the objection to it that was refuted (2026-09-07)

The third release term is the height flown since the last on-ground sample,
`(posDownAtTakeoff - stateStruct.position.z) > 1.5f`.

`get_time_flying_ms() > 5000` was tried first and works, but is not the same
thing on every vehicle: Rover, Sub and Tracker set `likely_flying` from the
armed flag, so it reduces to 5s after arming, and `AP_VEHICLE_ENABLED` guards
it in the DAL (`AP_DAL.cpp:56`), leaving it 0 when that is off.

**The circularity objection to `posDownAtTakeoff` was measured and refuted.**
The argument against it was that the substitution corrupts the very height
estimate the bound reads, which is what Rishabh gave for rejecting `inFlight`
on this PR. It does not hold: the estimate lags, it does not freeze. With the
detector disabled entirely a 7.5 m climb still moved the estimate 4.9 m, so
1.5 m is crossed early in any real climb. Measured with the gyro and range
terms made unreachable so this term acted alone, `EK3_SRC1_POSZ=2`,
`RNGFND1_MIN=50`: 6.4 m climbed, 6.5 m estimated. Do not re-propose the
circularity argument without a measurement behind it.

## SITL matrix, autotest EKF3RangeFinderOnGround (2026-09-07)

Four subtests. Numbers are the branch build unless the row says otherwise.

| Subtest | Branch | Release disabled |
|---|---|---|
| 1 armed, stationary, baro drifting 0.3 m/s for 20 s | -0.01 m | n/a (passes either way) |
| 1, gate reverted to `onGround` | - | **+4.61 m**, fails |
| 2 sensor comes into range on the climb | 6.4 true / 6.7 est | passes either way |
| 3 sensor never in range, `SRC1_POSZ=2` | 6.4 true / 6.5 est | **7.5 true / 4.9 est**, fails |
| 4 terrain path, `SRC1_POSZ=1`, sensor short throughout | TOfs floor **0.0 m** | TOfs floor **-10.7 m**, fails |

Subtest 4 answers the coverage gap #33585 left behind. Its first version
asserted peak `XKF5.HAGL > 5 m` and was **not** coverage - it passed on both
builds. HAGL is `terrainState - position.z` and peaks before the damage: the
substitution walks `terrainState` down to stay consistent with a range that
never changes, and HAGL only sags afterwards. The floor of `TOfs` is the
statistic that moves. Recorded because the same trap catches any assertion
written from a mental model of the failure rather than from its mechanism.

Subtest 3's separation is real but narrower than subtest 1's, and it grows
with climb length rather than sitting at zero, because GPS and the IMU keep
pulling the estimate along even while the range observation is constant.

## Post-squash review round (2026-09-07)

Two defects found in the review responses themselves, both in code already
called verified once:

- **The height term was sign-inverted for ArduSub.** `(posDownAtTakeoff -
  position.z) > 1.5f` tests "moved up"; a Sub moves away from the surface by
  increasing depth, and `detectFlight()` twenty lines above already carries an
  `APM_BUILD_ArduSub` branch for exactly this. Sub takes the non fly-forward
  path and sets `likely_flying` from the armed flag, so the gyro term was the
  only survivor there. Fixed.
- **The autotest's climb bound was a fraction of the climb achieved.** A
  vehicle flying a lagging estimate over-throttles, so a broken build widened
  its own allowance; the margin was scale-invariant at 1.39x against ~0.6m of
  run-to-run spread. Now bounded by the climb commanded.

**The GPS-denied objection, measured.** A reviewer argued the circularity
refutation was confounded, because `EK3_SRC1_VELZ` defaults to GPS
(`AP_NavEKF_Source.cpp:53`) and GPS velD was moving the height state
throughout. The prediction was that with the range finder as the only vertical
observation the state would freeze and all three release terms would be dead.
Measured in the indoor config (optical flow for XY, range finder for Z, no GPS
- `configure_EKFs_to_use_optical_flow_instead_of_GPS()` already sets
`EK3_SRC1_VELZ=0`): the estimate tracked, 10.3m flown against 10.2m estimated.
The IMU keeps driving `position.z` against a constant height observation, so
it lags harder without velD but does not freeze. The strong form is not
reproduced; the direction was right, and the config is now a permanent leg.

Also corrected from the earlier record: `find_instance()`
(`AP_RangeFinder.cpp:750-760`) returns the first downward backend **whose
status is Good**, falling back to the first downward backend. So with one Good
and one out-of-range sensor, `rngOnGnd` is taken from the *Good* sensor and
written as the other one's measurement, then corrected with the wrong body
offset. Defect 1 below is worse than first recorded.

Sampling note for anyone repeating these runs: Copter streams
`LOCAL_POSITION_NED` at 5Hz, which lags the truth sample by most of a metre in
a 2.5m/s climb. At 20Hz the same leg moved from 6.4/5.9 to 6.4/6.5.

## Open defects, in the original two commits

1. **Dual range finder.** The loop writes the shared `rangeDataNew` and
   pushes per sensor. A sensor reading `Good` at 2.0 m and a second still
   `OutOfRangeLow` both push, so the synthetic `rngOnGnd` can overwrite a
   real climbing value. `rngOnGnd` comes from
   `ground_clearance_orient()` -> `find_instance()`, the **first** downward
   backend (`AP_RangeFinder.cpp:808-815`), and the body-offset correction
   at `PosVelFusion.cpp:1234-1240` then applies sensor 1's geometry to
   sensor 0's clearance. Fixing it needs per-instance clearance, which is
   not DAL-recorded: `log_RRNH` carries one global `ground_clearance` and
   `log_RRNI` has only `PX,PY,PZ,Dist,Orient,Status,I`. Growing `RRNI` is
   forbidden (old logs misparse), so this needs a new DAL message.
2. **Mid-air disarm and re-arm.** `onGround` clears the latch and
   `timeAtArming_ms` resets, so the substitution is live for >= 1 s after a
   re-arm. Backends that clamp a lost return to 0 classify as
   `OutOfRangeLow` (`AP_RangeFinder_Backend.cpp:72-81`), so that status is
   not exotic in flight. Impossible on the base branch.
3. **Gyro term sampled ~40x more often**, having moved from flow rate to
   `controlFilterModes()`. More exposure to a vibration spike latching
   while still on the deck. SITL models no gyro noise
   (`SIM_GYR1_RND` and `SIM_VIB_MOT_MAX` both default 0), so no autotest
   can see this - it needs a real log, windowed arm to +10 s, computing
   `max(|Gyr|)` of the 3-vector.
4. **Fixed wing gains almost nothing.** The fly-forward branch also sets
   `onGround = false` at arming, so a plane's latch trips on ground-roll
   gyro at arming+1s, close to base behaviour.

## Coverage not claimed

Copter only - says nothing about the fly-forward branch of
`detectFlight()`. No coverage of premature release from vibration (see 3).
No real-vehicle data.
