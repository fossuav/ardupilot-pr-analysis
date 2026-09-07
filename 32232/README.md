# PR #32232 - AP_NavEKF3 ground clearance fusion fix

Analysis of [ArduPilot/ardupilot#32232](https://github.com/ArduPilot/ardupilot/pull/32232),
`rishabsingh3003:ek3_gnd_clear`, open, head `a628150687` (2 commits) read
2026-09-07. Not our PR. Recorded here because #33585 stacks over it and
#33585's autotest is what found this.

## Status (one line)

The `OutOfRangeLow` -> `rngOnGnd` substitution is scoped by `!takeOffDetected`,
a flag that can stay false for a whole flight, and when it does the EKF fuses
a 0.1 m range while the vehicle climbs, dragging the terrain state up with it.

## What the PR does

`readRangeFinder()` used to consume only `Status::Good` data, with a separate
branch that pushed `rngOnGnd` when the vehicle was `onGround` and no sample had
arrived for 200 ms. The PR replaces that with a single path: `Good` gives the
measured distance, `OutOfRangeLow` gives `rngOnGnd` while `!takeOffDetected`,
anything else is skipped. It also moves `detectOptFlowTakeoff()` out of
`writeOptFlowMeas()` and into `controlFilterModes()` as `detectTakeoff()`, so
takeoff detection now runs every filter step rather than only when flow data
arrives.

The second commit is what changed the guard from `onGround` (Randy's original,
which is what our local copies of this work carry) to `!takeOffDetected`. That
is the change this note is about.

## The defect

`detectTakeoff()` sets `takeOffDetected` from two criteria: a gyro rate above
0.1 rad/s, or the range finder reading more than 0.1 m above its value at the
start of flight. With the range finder dead the second is unavailable - the
substitution feeds back a constant `rngOnGnd`, so it can never rise - and a
SITL climb does not reach 0.1 rad/s. `takeOffDetected` then stays false for the
entire flight and the substitution never stops.

Measured on Copter SITL, `EK3_IMU_MASK=1`, range finder killed
(`RNGFND1_MIN` above `RNGFND1_MAX`, so every reading is `OutOfRangeLow`),
vehicle climbing to 5-10 m in ALT_HOLD, PR at `a628150687` plus #33585:

- `XKF4.SS` bit 10 (`takeoff_detected`) never sets after the second arming.
- `XKF5.rng`, the range being fused, holds 0.1 m throughout.
- `XKF5.TOfs` walks from +0.09 m to -3.0 m: the terrain state is being pulled
  up with the vehicle, because each fused sample asserts the ground is
  `rngOnGnd` below it.
- `XKF5.HAGL` peaks at 2.9 m, reached at the point the leg has held the
  vehicle between 5 and 10 m.
- `XKF4.SS` bit 6 (`terrain_alt`, i.e. `gndOffsetValid`) never clears, because
  `gndHgtValidTime_ms` is restamped by every one of those fusions.

Flow-derived velocity is scaled by `terrainState - position.z`, so a terrain
state that follows the vehicle scales flow velocity by roughly the wrong
factor for as long as the sensor stays dead. `gndOffsetValid` staying true also
means nothing downstream can tell that the terrain estimate is unobserved -
`EKF_POS_VERT_AGL` reports valid, and on #33585 that alone keeps
`EKF_POS_HORIZ_REL` up.

This is the trap `libraries/AP_NavEKF3/CLAUDE.md` already records for
`takeOffDetected`: a gate that reads as an observability test can reduce to a
constant. Here it reduces to constant false in exactly the case the
substitution is riskiest - no working range finder.

## Suggested fix

Add the flight-state term the scope actually needs:

```c
} else if (!inFlight && !takeOffDetected && sensor->status() == AP_DAL_RangeFinder::Status::OutOfRangeLow) {
```

`inFlight` latches on a 1.5 m climb (or 5 s of `time_flying`) and does not
depend on the sensor being substituted, so it bounds the substitution even when
takeoff detection cannot fire. Measured with this term added, same leg: the
terrain offset stops being restamped at the `inFlight` latch, `TOfs` freezes at
-0.25 m (the drag accumulated over the 1.5 m climb) and `terrain_alt` clears
5 s later, as it does on master.

`onGround` alone - reverting to the first commit - would also bound it, at the
cost of the pre-takeoff window the second commit was added to get.

Untested alternative, noted so it is not re-proposed as new: gating on
`rngValidMeaTime_ms` freshness instead. It does not help, because the
substitution is itself what keeps that timestamp fresh.

## What this costs #33585

#33585's `gndOffsetMeasured` guard is independently too weak, so the two
compound and its autotest leg "The assumption does not carry over from an
earlier flight" fails on the stack until both are fixed. The four-way
measurement is in `../33585/`, under the 2026-09-07 heading. Neither PR alone
fails that leg.

## Reproduce

In an `ardupilot-dist` checkout on `pr-optflow-flat-ground` (#33585):

```
gh pr diff 32232 | git apply
./waf configure --board sitl && ./waf copter
python3 .claude/skills/autotest/run_autotest.py test.Copter.EK3_OptflowAssumeFlatGnd
```

The leg fails with "Flat-ground assumption carried over from a previous
flight". Decode the flight with

```
python3 .claude/skills/log-analyze/log_extract.py extract <log.BIN> \
    --types XKF5 --fields TimeUS,C,HAGL,TOfs,rng --limit 0
```

and read `XKF4.SS` bits 6 and 10 (`AP_Nav_Common.h`) for the two flags. Do not
try to kill the range finder by putting `RNGFND1_MAX` below the on-ground
reading: on the ground an analog range finder reads about 0, which with
`RNGFND1_MIN=0` is neither above the max nor below the min, so the backend
still calls it `Good`.

## What is here

```
32232/
  README.md          <- this file
```

No logs committed; the SITL runs behind the numbers above were scratch autotest
runs.
