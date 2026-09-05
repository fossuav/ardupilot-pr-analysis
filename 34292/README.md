# PR #34292 - optical flow minimum focus height (FLOW_HGT_MIN)

Analysis archive for [ArduPilot/ardupilot#34292](https://github.com/ArduPilot/ardupilot/pull/34292).
Branch `pr-flow-hgt-min` (andyp1per fork), base `master`, head `84ec31a99d`
(2026-09-05). The head was `292ec09fef` when this record was opened; two
review rounds have moved it since, and the sections below say what changed.

Split out of #33484 on 2026-09-04 after rmackay9 reviewed the parameter there
and asked for it to live in the flow library. The mechanism is unchanged from
the version flown on that branch; what moved is where the parameter lives and
how its value reaches the filter.

## Status

Mechanism flight-validated on the 4-inch quad as `EK3_FLOW_MIN_H` (log67, see
#33484's README). Re-implemented as `FLOW_HGT_MIN` in the flow library and
re-verified in SITL; the re-implementation itself has not been flown.

Under review. tridge's automated pass has run twice (2026-09-04 and
2026-09-05) and peterbarker requested changes on 2026-09-04. Both rounds are
recorded under "Review" below, including the findings that were rejected.

**One open question is unresolved and it bears on the flight evidence.** See
"Open question: was the flown value inside the rangefinder floor?".

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
`NavEKF3::writeOptFlowMeas()` -> `of_elements.minHeight`, and into the DAL so
Replay feeds the filter the value the flight used. Reading it out of the flow
library's parameters from EKF code would not replay.

`AP_NavEKF2` gains no behaviour but has to round-trip the field. Both
estimators write back through `AP_DAL::writeOptFlowMeas`; if only EKF3 passed
the value the two writes would differ on every sample and
`WRITE_REPLAY_BLOCK_IFCHANGED` would log two records per sample, which replay
would feed back as two samples.

### Superseded 2026-09-05: it rides in a new ROFM record, not in ROFH

The original implementation added `minHeight` to the existing `log_ROFH` DAL
record. That is wrong and tridge's first automated review caught it:
`AP_LoggerFileReader::update()` sizes its buffer from the format stored in the
log being replayed, while `MSG_CREATE` copies `offsetof(log_X, _end)` bytes
from the compiled struct. Growing the struct makes the copy run past the
record, and every field after the insertion point shifts.

Measured on `../../analysis/logs/logm2_log4.bin` (ROFH `len=40`,
`fmt=ffffIffffB`) against a build that had grown `log_ROFH` to 44: flow
quality read a constant 89 where the true per-sample values were 70-102, and
`minHeight` read -1.15e14. It happened to be harmless on that log, because
quality is only tested for `> 0` and a negative height can never trip a
`rng < minHeight` cutoff, so the EKF output was bit-identical. Which way it
falls is up to the stack, not the design.

The review's suggested fix, `log_##sname msg{};`, does not work: the memcpy
overwrites the zeroed bytes. The fix used is a new message, `ROFM`, beside
`ROFH`, following `97b5b0448a` which split `RISJ` out of `RISI` for exactly
this reason. Old logs have no `ROFM` and replay with the height at 0, which
is the disabled behaviour.

The paragraph above is left in place because the "travels with the sample"
argument is still why the value is in the DAL at all, rather than read from a
parameter inside the EKF.

## Default

0, off, in the manner of `VISO_QUAL_MIN`. Sensors do not share a focus height.

The check only has effect above `RNGFNDx_MIN`, because below that the
rangefinder stops returning `Good` samples, `rngValidMeaTime_ms` goes stale
and the 500 ms freshness gate fails. With the `RNGFNDx_MIN` default of 0.20 m
a floor below that can never fire. The airframe this was flown on had a
rangefinder valid to 1 cm, which is why 0.1 m worked there - it is a property
of the rangefinder fitted, not a safe global default.

### Added 2026-09-05: there is a second floor, `RNGFNDx_GNDCLR`

Derived from the source, not measured. `NavEKF3_core::readRangeFinder()`
clamps the range the filter ever sees:
`rangeDataNew.rng = MAX(storedRngMeas[...], rngOnGnd)` with
`rngOnGnd = MAX(_rng->ground_clearance_orient(ROTATION_PITCH_270), 0.05f)`
(`AP_NavEKF3_Measurements.cpp:29` and `:85`).

`RNGFNDx_GNDCLR` defaults to **0.10 m** (`RANGEFINDER_GROUND_CLEARANCE_DEFAULT`
in `AP_RangeFinder.h:39`). So on a default airframe the comparison can never
see a range below 0.10 m, and any `FLOW_HGT_MIN` at or below that is a silent
no-op. The useful setting is above both `RNGFNDx_MIN` and `RNGFNDx_GNDCLR`,
which is now what the parameter description says.

Note the parameter is `RNGFNDx_GNDCLR`, not `RNGFNDx_GNDCLEAR`. It was renamed
and converted from cm to m; the old name reads as absent rather than as an
error, which is the trap the root playbook records under "Dead parameter names
read as absent".

## Open question: was the flown value inside the rangefinder floor?

Unresolved as of 2026-09-05. Not an argument against the mechanism - an
argument about whether log67 measured it.

log67 flew `EK3_FLOW_MIN_H=0.1` and descended through RFND 0.115 -> 0.054 m.
For the gate to have fired at all, that airframe's `RNGFND1_GNDCLR` must have
been below about 0.075. If it sat at the 0.10 m default, `rngOnGnd` clamped
the range to 0.10, `0.10 < 0.1` is false, and the floor never ran - which
would mean the improvement recorded in
`../../analysis/topics/optflow_horizontal_velocity_lockout.md` had another
cause.

What is known: `../../analysis/vehicles/FPV-4C.md:45` records
`RNGFND1_GNDCLR=0.075`, but on a *forward-declared* sensor
(`RNGFND1_ORIENT=0`) that the EKF never consumes, and `FPV-4C-J1.md:17`
records no rangefinder at all. The JK-4Inch's setting is not recorded in
`../../analysis`, and log67 is not in either repo.

**To settle it:** read `RNGFND1_GNDCLR` (or `RNGFND1_GNDCLEAR` on that
firmware vintage) from log67's parameter dump. Until then, quote the SITL
evidence rather than the flight evidence for this PR.

## Evidence

Flight (as `EK3_FLOW_MIN_H`, 4-inch quad, log67, descent through the floor at
rangefinder 0.115 -> 0.054 m): `FIX/FIY` +/-2000-6700 -> +/-200-500, `NI`
pinned 255 -> 3-40, phantom `VN/VE` +/-0.5 -> +/-0.1 m/s, DesRoll/Pitch
+/-14 -> +/-2 deg. Operator: "althold type behaviour close to the ground but
no sudden lean". See the open question above before quoting this.

SITL (`Copter.OpticalFlowFocusHeight`, three runs, **branch head 292ec09fef**,
the RC-descent version of the test): hover in an asserted altitude band below
the floor on flow-only nav, inject a one-axis flow rate offset with
`SIM_FLOW_OFS_X`. Peak EKF groundspeed 0.029-0.031 m/s with the floor set
against 0.90-1.22 m/s without it.

### Re-measured 2026-09-05 at head 84ec31a99d

The test was rewritten (guided descent, third subtest) so these are not the
same measurement as the numbers above, which are left alone. The hover is now
held at 2.00-2.01 m rather than in a 1.5-2.5 m band, and there are three arms
rather than two. Peak EKF horizontal speed inside the injection window, across
two runs of the current code:

| `FLOW_HGT_MIN` | meaning | peak XKF1 speed |
|---|---|---|
| 3.0 | above the vehicle, floor fires | 0.261, 0.264 m/s |
| 0 | disabled: master's behaviour | 1.125, 1.489 m/s |
| 1.0 | below the vehicle, must not fire | 1.404, 1.564 m/s |

The floor-active arm runs the full 15.8 s window and stays inside
0.02-0.26 m/s. The other two exit as soon as they cross the test's 0.8 m/s
bound, at about 6 s, so their peaks are where the test stopped looking and not
where the divergence ended.

The third arm is the one worth keeping: a floor that fired at *every* height
rather than below its value would pass both of the original two subtests,
because the second disables the feature outright.

## Plots

`plots/flow_hgt_min_ab.png` - the original, head 292ec09fef. One binary,
`FLOW_HGT_MIN` 3.0 against 0. The figure plots EKF horizontal speed from
`XKF1` over the whole 30 s window and peaks at 0.04 m/s against 2.50 m/s.
Those autotest numbers (0.029-0.031 against 0.90-1.22) are the same runs
measured differently: `wait_groundspeed` reports the first sample crossing its
bound rather than the peak, so it reads lower on the diverging arm. Neither is
wrong; quote the autotest bounds when talking about the test and the peaks
when reading the plot.

`plots/flow_hgt_min_ab_2026_09_05.png` - head 84ec31a99d, all three arms,
regenerated by `plots/make_plots.py` from `data/ab-2026-09-05/`.

The floor is fully behind the parameter, so `FLOW_HGT_MIN=0` is master's
behaviour and no second build is needed for either figure.

## Known limit

Zeroed flow does not pin velocity against a continuous divergence force - a
1.5 m/s^2 accel bias ran to 27 m/s in an early test. That is not the
near-ground failure, which is bad flow on a nearly stationary vehicle, and is
what the lockout recovery in #33484 addresses.

## Review

### tridge automated pass 1, 2026-09-04 (head 292ec09fef)

1. Parameter metadata did not parse - the `_HGT_MIN` doc block sat between
   `_OPTIONS`' block and its own `AP_GROUPINFO`, so `param_parse.py` attached
   it to the wrong parameter and CI failed. Real, and the blocking one. Fixed
   by `d4d6cd08dd`.
2. `log_ROFH` grew a field and `MSG_CREATE` does not zero the struct. Real;
   see "Superseded 2026-09-05" above. The suggested fix was wrong.
3. Duplicate commits with #33484. Still open; see "Relationship to #33484".
4. The rangefinder height is taken at the IMU origin, so a large `FLOW_POS`
   biases the check. Real, documented in the parameter description.
5. "the EKF" where only EKF3 acts on the value. Fixed in the description.

Two claims in that review were wrong and are recorded here so they are not
re-raised: the suggested `log_##sname msg{};` does not fix the misparse
(memcpy overwrites the zeroed bytes), and "the first ROFH field whose garbage
value changes behaviour" is false - `heightOverride` was added identically in
2022 by `b15cb46d25` with the same `> 0` gate.

### tridge automated pass 2, 2026-09-05 (head 7d8ec8f344)

Its blocking finding was real, and it is the most valuable thing either review
produced. `AP_DAL::WriteLogMessage` returned early when `logging_started` was
false *without setting the `_end` retry flag*, so a record that is only written
when it changes is dropped and, because the struct has already latched the new
value, the memcmp matches forever and no record is ever written.

The first instance of this (before the first log opens) was fixed by
`7d8ec8f344`. The review found the second: a *later* log in the same power
cycle, because the struct stays latched across `stop_logging()`.

Reproduced, not just argued. Downloading a log between two flights in one
power cycle (`AP_Logger_File::get_log_data` calls `stop_logging()`):

```
log 2:  ROFH=2635  ROFM=1     flight 1, floor recorded
log 3:  ROFH=1302  ROFM=0     flight 2, floor absent
```

After the fix both logs carry `ROFM=1` with value 3.0. Note `LOG_DISARMED=0`
does *not* reproduce it: with `LOG_REPLAY=1` the rotate-on-disarm path in
`AP_Logger_Backend::vehicle_was_disarmed()` is explicitly suppressed, so both
flights land in one file.

Fixed generically, by setting `_end` on the `!logging_started` return, which
also answers peterbarker's `force_write` question below.

### peterbarker, CHANGES_REQUESTED, 2026-09-04 (head 7d8ec8f344)

- **"Isn't `force_write` supposed to take care of this?"** He is right that it
  should. It does not, because `force_write` is set and cleared inside a single
  `start_frame()` (`AP_DAL.cpp:46` and `:119`), so it only reaches records
  written from there. That is why `RISJ` escapes and a record written from a
  sensor callback does not.
- **NaN rather than 0 as the unused sentinel**, twice. Not taken: the
  `heightOverride` argument on the same call already means 0-is-unused, and
  the user-facing parameter documents "0 disables it". NaN would make the two
  arguments disagree.
- **"Why the rangefinder and not `terrainState`, like the block above?"** The
  choice is deliberate and the reasoning is now a comment in the code:
  `terrainState` is itself fused from optical flow, so gating flow on it is
  circular, and it is not updated at all when the rangefinder is the height
  source, which is a common flow-nav configuration. The block above gets away
  with it because it runs pre-takeoff.
- **"You check staleness where the above does not."** Necessary here:
  `rangeDataDelayed` holds its last value when the rangefinder stops
  reporting, which is exactly what happens below `RNGFNDx_MIN`.
- **"Tie into `gndOffsetValid`."** Not taken: 5 s staleness is far too loose
  for a sub-metre decision on a descending vehicle, and its
  `activeHgtSource == RANGEFINDER` disjunct is unconditionally true in the
  target configuration.
- **`DCM33FlowMin` ignored.** `tiltOK` added to the condition. It changes
  nothing today, since both consumers of the zeroed rates are already
  tilt-gated, but it makes the tilt projection in the comparison safe to read.
- **Autotest line splitting, and guided rather than RC.** Both taken; see the
  test note below.

## The SIGFPE this PR introduced, and the fix that was wrong

Found on 2026-09-05 after the second review round, from a report of four
crashed tests. Worth recording in full because the obvious fix is the wrong
one.

`ekf_ring_buffer::recall()` (`AP_NavEKF/EKF_Buffer.cpp:53`) only memcpys into
the caller's element `if (ret)`. On failure the local is left untouched, so
`of_elements ofDataDelayed;` in `SelectFlowFusion` is uninitialised stack
whenever `flowDataToFuse` is false - which is most IMU steps, since flow
arrives at about 10 Hz against a 400 Hz filter.

This PR's focus-height check read `ofDataDelayed.minHeight` *without* gating on
`flowDataToFuse`. SITL enables `FE_INVALID | FE_OVERFLOW | FE_DIVBYZERO`
(`AP_HAL_SITL/Scheduler.cpp:199-206`), and `>` and `<` are signalling
comparisons, so a NaN bit pattern in that slot is an immediate SIGFPE rather
than a wrong answer.

Demonstrated rather than inferred, by poisoning the struct with
`memset(&ofDataDelayed, 0xFF, sizeof(ofDataDelayed))` so it does not depend on
stack luck. Same build, one variable:

| gate | result |
|---|---|
| `flowDataToFuse &&` present | `Copter.OpticalFlowFocusHeight` passes, ~30 s |
| absent | `_sig_fpe (signum=8)` -> `SelectFlowFusion` at `AP_NavEKF3_OptFlowFusion.cpp:61` |

Master does not trip this on Copter: the only pre-existing read of the struct
(`MAX(ofDataDelayed.flowRadXY[0], flowRadXY[1]) > _maxFlowRate`, at
`AP_NavEKF3_OptFlowFusion.cpp:107`) sits behind
`_flowUse != FLOW_USE_TERRAIN` in a `||` chain, and `EK3_FLOW_USE` defaults
to 1 there.

**Zero-initialising the struct is the wrong fix, and was tried first.** `{}`
silences the crash but converts the UB into a deterministic fabricated
measurement: `MAX(0,0) > _maxFlowRate` is false, so `cantFuseFlowData` becomes
false where garbage would usually have made it true, and
`EstimateTerrainOffset` then fuses an invented zero flow rate into
`terrainState` whenever a rangefinder sample arrives without a flow one. That
path is live by default on Plane, where `EK3_FLOW_USE` defaults to **2**. The
fix shipped is the `flowDataToFuse` gate; the `{}` was reverted before the
branch was pushed a second time.

**Still open, and not this PR's bug:** line 107 reads the same uninitialised
struct and is reachable by default on Plane. Fixing it properly means gating
`EstimateTerrainOffset`'s flow branch on `flowDataToFuse`, which is a
behaviour change deserving its own PR and its own measurement.

**Also unexplained:** the report was of four crashed tests, but CI was green
on all 30 checks at `7d8ec8f344` and neither analysis repo records an FPE, so
that run came from somewhere else. If the test names were all Copter it is the
line 61 crash fixed here; if any were Plane it points at line 107 instead, and
that becomes urgent rather than a follow-up.

## Gotchas worth remembering

Adding `minHeight` to `log_ROFH` without updating the `"ffffIffffB"` format
string made the binary refuse to boot with `Config Error: Log structures
invalid`. It surfaced as autotest failing with "Failed to set RC values" and
as every ad-hoc SITL probe reading nothing, which looked like a broken
plumbing chain for some time. The format string, the field-name list, the
units and the mult strings all have to grow together.

A DAL record written with `WRITE_REPLAY_BLOCK_IFCHANGED` from a push-based
sensor callback needs its record count checked in a real log, with the feature
configured and at its default, and in a *second* log in the same power cycle.
The code is correct, the autotest passes, and the field is simply absent.
Counting records is what caught it; reasoning about `IFCHANGED` did not.

`ArduCopter`'s autotest `takeoff()` helper documents the trap the test hit:
"in a manual-throttle mode such as STABILIZE the vehicle climbs fast and can
blow way past altitude_min... If your test cares about the altitude the
takeoff finishes at, take off in GUIDED."

## Autotest note

`Copter.OpticalFlowFocusHeight` climbs in ALT_HOLD, because flow is not
healthy while stationary on the ground, then descends to the test altitude in
GUIDED, which holds it. The old RC descent flew through its target by an
amount that depended on the speedup; the guided version held 2.00-2.01 m
across all three arms and all runs.

The measurement window is deliberately back in ALT_HOLD. A position-controlled
mode would fly the phantom velocity away instead of leaving it in the
estimate, which removes the very thing the test is reading.

## Relationship to #33484

Both branches add a field to `of_elements` and extend `writeOptFlowMeas`, so
whichever merges second needs a small rebase. Otherwise independent and
reviewable in either order.

Two commits are the same patch on both branches under different SHAs, so a
rebase will drop them by patch-id but they are not literally shared commits:

| patch | on #33484 | on #34292 |
|---|---|---|
| `SITL: add SIM_FLOW_OFS optical flow rate offset for fault injection` | `9d8e218d67` | `25c7364cb5` |
| `AP_OpticalFlow: apply SIM_FLOW_OFS offset to the SITL flow rate` | `2e02161d1a` | `d70cb7a058` |

Whichever lands second needs them dropped. This is noted in #34292's PR
description and in `../33484/split-and-quality-gate.md`.

## Reproduce

The SITL arms, from an ArduPilot checkout on `pr-flow-hgt-min`:

```
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.OpticalFlowFocusHeight
```

It leaves three flight logs in `logs/`, one per subtest in order
(`FLOW_HGT_MIN` 3.0, 0, 1.0). Each is identifiable by its first
`PARM FLOW_HGT_MIN` value, and the injection window by the `PARM
SIM_FLOW_OFS_X` transitions to 1.0 and back to 0.

`data/ab-2026-09-05/*.csv` holds `XKF1` core 0 (`t_s,VN,VE,alt_m`) extracted
from those logs at head `84ec31a99d`, with the injection window in the header
comment. The full BINs are about 41 MB and are not committed; the CSVs are
44 KB and carry everything the figure needs.

```
python3 plots/make_plots.py
```

The replay-record checks:

```
Tools/autotest/autotest.py test.Copter.Replay
```

For the two-logs-in-one-power-cycle case there is no committed test. It was
reproduced with a throwaway autotest that armed, flew, disarmed, stopped
logging with a MAVLink `log_request_data` (which calls `stop_logging()`), then
armed and flew again, and counted `ROFM` records per log.
