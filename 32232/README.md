# PR #32232 - Range finder ground clearance fusion (EKF3)

Analysis archive for [ArduPilot/ardupilot#32232](https://github.com/ArduPilot/ardupilot/pull/32232).
Branch `ek3_gnd_clear` (rishabsingh3003 fork). Head `8bec444e50` (pushed
2026-09-11); the review work started from `a628150687`. Seven commits sit on
top of rmackay9's and rishabsingh3003's, neither of which was rewritten. All
numbers below are SITL; no hardware and no real-flight logs.

## Status (one line)

Review comments from IamPete1 and tridge answered and replied to on the PR,
an autotest added and A/B'd five ways, the PR body rewritten to the repo
template with the known-issues list below, and four defects recorded that are
in the original two commits rather than in the review responses.

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

## Final state (2026-09-07)

Squashed twice, each time verified with an empty `git diff` against a
pre-squash branch plus a `git range-diff` to confirm no fixup landed in a
neighbouring commit (the flat diff stays empty when it does, so the range-diff
is the check that matters). Final history, `a628150687..28cbfe4adf`:

    1fd080eb62  scope the range measurement to the sensor loop
    4b9e0bd25f  run the takeoff detector once per filter update
    e2d3fd727c  state the range term's data requirement
    318fc4bc0e  name the movement detector for what it measures
    bf646cdf78  bound the movement detector by height flown
    14334135e7  AP_NavEKF: say what bit 10 of the filter status now means
    28cbfe4adf  autotest: cover the range finder on-ground assumption

The Sub sign fix and the autotest tightening were folded into `bf646cdf78` and
`28cbfe4adf` respectively, so they no longer exist as separate commits.

Final leg numbers on the squashed branch: -0.01 m armed and stationary;
6.3/6.5 m coming into range; 6.4/6.5 m never in range; terrain offset 0.0 m;
10.3/10.5 m indoor. The indoor leg measures a 10 m climb rather than 6 m
because the lag without a vertical velocity source is roughly fixed in metres,
so a longer climb buys margin without weakening the assertion - at 6 m it was
1.1 m of error against a 1.5 m bound, which is inside the observed run-to-run
spread.

Three commit messages were corrected during review for claiming more than was
measured: a fall-through that could not happen, a freshness gate that changes
nothing, and "the estimate lags rather than freezes" stated as a general
property when it had only been measured with GPS aiding present. All three
were self-inflicted and all three were caught by running something rather than
by re-reading the code.

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

## Automated review round, and the head move to `8bec444e50` (2026-09-11)

The dev-call reviewer returned REQUEST CHANGES at `28cbfe4adf` on 2026-09-07:
one finding it called safety-critical, two autotest findings, and a handful of
smaller items. Triage: **1 refuted, 3 fixed, 2 declined.** Head is now
`8bec444e50` on `rishabsingh3003/ek3_gnd_clear`.

### Refuted - the "no escape from a false hold" finding

The argument: with `EK3_SRC1_POSZ=2` and a persistently `OutOfRangeLow`
sensor, all three release terms are simultaneously dead - gyro below 0.1
rad/s by assumption, the range term pinned by the substitution itself, and
`movedVertically` circular because `stateStruct.position.z` is driven by the
substituted measurement. It concluded the PR removes master's
`lostRngHgt` -> baro rescue with nothing to replace it, and proposed
`dal.get_time_flying_ms() > 5000` as a fourth term.

Both halves are already answered above, by measurement rather than by
argument:

- The circularity is the same claim recorded under "The GPS-denied
  objection, measured", where a reviewer predicted the state would freeze
  with the range finder as the only vertical observation. Measured in the
  indoor config: **10.3 m flown, 10.2 m estimated**. The IMU keeps driving
  `position.z` against a constant height observation, so it lags harder
  without velD but does not freeze.
- `get_time_flying_ms() > 5000` is the term recorded under "Bound chosen"
  as tried first, working, and rejected: Rover, Sub and Tracker set
  `likely_flying` from the armed flag so it degenerates to arming+5 s, and
  `AP_VEHICLE_ENABLED` guards it in the DAL.

The mechanism half of the finding is correct and was already known - the
substitution does refresh `rngValidMeaTime_ms` (`Measurements.cpp:109`),
which is why the freshness gate on the range term is recorded above as a
no-op. What does not follow is that nothing releases.

No code change. Posted to the PR on 2026-09-11 at 12:15Z, taking the findings
in turn; the reply gives the indoor leg as 10.3 m climbed against 10.5 m
estimated, which is the squashed-branch figure from "Final state" rather than
the 10.2 m recorded above at the pre-squash head. Both are 5 Hz numbers and
both are superseded by the soak below.

### Fixed - the autotest was measuring three of its five legs at 5 Hz

`reboot_sitl()` calls `initialise_after_reboot_sitl()`, which calls
`set_streamrate(self.sitl_streamrate())`, and Copter's `sitl_streamrate()`
returns 5. The `set_message_rate_hz('LOCAL_POSITION_NED', 20)` was applied
once after the first reboot only. The reboots sit *inside* legs 3, 4 and 5,
after their `start_subtest` banners, so those three legs flew at 5 Hz.

This is a finding about the measurements in this file, not just about the
test. The "Sampling note" above records that at 5 Hz the never-in-range leg
read 6.4/5.9 and at 20 Hz it read 6.4/6.5 - but that leg is leg 3, which the
structure above says was running at 5 Hz. The two cannot both be true of the
same tree. **The recorded numbers for legs 3, 4 and 5 should be treated as
of uncertain provenance until re-run at `8bec444e50`**, which now restores
the rate after every reboot. Leg 4 is the least affected: its statistic is
the `TOfs` floor read from the dataflash log, not from a streamed message.

Also fixed: leg 5 took `reboot_sitl()`'s default 1 m `startup_location_dist_max`
while following the longest climb in the test, where the other two
uncontrolled-XY legs allow 2 m.

### Fixed - the range term did not carry the Sub sign split

The height term beside it splits on `APM_BUILD_ArduSub` (recorded above as a
post-squash fix); the range term kept the copter sense for every vehicle.
`detectFlight()` twenty lines up tests `(rng - rngAtStartOfFlight) < -0.5f`
on Sub because a Sub moving away from the surface closes the range to the
bottom. Both terms now match that convention. By inspection only - there is
no Sub job in the CI matrix.

### Declined

- **Dead initialiser `float range_distance = 0.0f;`.** Every path reaching
  the store assigns it, but the house rule requires explicit initialisation
  of stack locals, so it stays.
- **Master's `onGround` fallback deletion, the disarmed-substitution note,
  and the landing half.** All three are accurate and all three are already
  in "Open defects" or the PR body; they are description work, not code.

### Owed - discharged 2026-09-11

Re-run the five-leg set at `8bec444e50` and replace the leg numbers above
with 20 Hz figures throughout. Until then the branch carries a test whose
sampling changed, which is exactly the kind of change that moves a margin
without moving a mechanism.

Done, as a 20-iteration soak: see "Soak at `8bec444e50`" below. Following the
repo's own rule, the numbers above keep their values and the head they were
taken at; the soak is a separate measurement, not a correction of them. It
does resolve the provenance question this section raised - leg 3 at 20 Hz
reads 6.4/6.6, consistent with the 6.4/6.5 in "Sampling note" and not with
the 6.4/5.9 of the 5 Hz set.

## Soak at `8bec444e50` (2026-09-11)

20 iterations of `Copter.EKF3RangeFinderOnGround`, 19 passed. This is the set
the "Owed" section above asked for: the first head at which the test holds its
20 Hz `LOCAL_POSITION_NED` rate across all four reboots, so all five legs are
sampled at the same rate for the first time. Error is estimate minus truth;
the bound is a quarter of the climb commanded.

| leg | error over 19 passing runs | fails at |
|---|---|---|
| 1 armed and stationary, baro drifting 0.3 m/s | -0.01 m, every run | 1 m |
| 2 sensor comes into range on the climb | -0.4 to -0.5 m | 1.5 m |
| 3 sensor never in range | +0.1 to +0.3 m | 1.5 m |
| 4 terrain path, baro as the height source | 0.0 m, every run | -2 m |
| 5 indoor, no vertical velocity source | -0.3 to +0.7 m | 2.5 m |

Leg 5 is the leg the refuted finding turns on. Worst case 0.7 m of error
against a 10.3 m climb, where a pinned estimate would read near 0 - four times
the failure bound away, which is the same conclusion the 10.3/10.2 measurement
reached at the pre-squash head and the 10.3/10.5 one reached after the squash.
Three measurements, three heads, one conclusion.

Leg 2's -0.4 to -0.5 m is systematic rather than spread: the estimate lags the
truth by about half a metre through the climb in every one of the 19 runs. It
is the largest error in the test and it sits in the leg that passes either way.
Worth knowing that leg 2 was **never** affected by the stream rate - it lies
between the first and second reboots - so the movement between the 5 Hz set and
this one is not all attributable to the rate fix. Some of it is run-to-run
spread, which is what motivated running 20 rather than 1.

`soak.sh` in this directory runs the set and prints the per-leg table. One
iteration is about 11 s of wall clock for 10.3 minutes of sim time.

### The one failure was the harness, not the test

Iteration 17 failed at `arducopter.py:15376`, the reboot before leg 3:
`reboot_sitl()` -> `detect_and_handle_reboot()` raised "Did not detect reboot"
after `get_parameter(STAT_BOOTCNT)` returned None. SITL had restarted and
accepted the connection; the parameter fetch stalled, and the sim clock jumped
from 3.2 to 268 minutes while the harness waited. No position assertion and no
EKF assertion was involved.

This is **not** the flake the automated round predicted. That one was leg 5
taking `reboot_sitl()`'s 1 m startup-location default after the longest climb,
it is fixed in code at `8bec444e50`, and it did not recur in 20 runs. What the
soak found instead is that four reboots give this test about four times a
normal test's exposure to a reconnect stall - a property of the harness, not of
anything this PR changes. One observation in 20; no rate attached to it.

The round asked for roughly 100 iterations before merge. 20 were run.

## Posted (2026-09-11)

- 12:15Z, comment answering the automated round: headline finding disputed, the
  two test findings reported fixed, the `get_time_flying_ms()` alternative
  declined.
- 18:15Z, PR description patched via `gh api -X PATCH repos/.../pulls/32232`
  (`gh pr edit` still fails against this repo on the deprecated projectCards
  field): testing table restated from the soak, and the three accepted points
  added to the known-issues list.
- 18:2xZ, comment with the soak figures and the reboot-stall failure.

The "Declined" triage above records master's `onGround` fallback deletion, the
disarmed substitution and the landing half as "already in Open defects or the
PR body". They were in neither - the Open defects list has the dual range
finder, the mid-air re-arm, the gyro sample rate and the fixed-wing case, and
the PR body had the same four. They are now in the PR body, which is what the
12:15Z comment promised.

A worktree is left at `../pr-32232`, detached at `8bec444e50` and built, so the
next round does not pay for the clone and submodules again.

## Still open after this round

- The soak is a fifth of what the round asked for.
- @rmackay9's 2026-02-26 replay-test request is unanswered. The subtest 4 row
  above shows a -10.7 m terrain-offset delta with the release disabled, so "no
  impact on baro vehicles" is not self-evident.
- @tridge's 2026-03-23 CHANGES_REQUESTED is still live: two of its three points
  are addressed, the `optFlowTakeoffDetected` rename was answered by going the
  other way.
- The four defects under "Open defects" are untouched.
