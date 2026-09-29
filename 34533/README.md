# PR #34533 - SITL: SIM_FLOW_OFS optical flow rate offset for fault injection

Analysis archive for [ArduPilot/ardupilot#34533](https://github.com/ArduPilot/ardupilot/pull/34533).
Branch `pr-sitl-flow-ofs` (andyp1per fork), base `master`, head `c70437775c`,
opened 2026-09-29. SITL-only change; no logs committed.

## Status (one line)

Open. Split out of #34292 at the 2026-09-23 dev call's request. Two
commits; OpticalFlow passes at `c70437775c` (2026-09-29).

## The problem

SITL has no way to put a rate offset on the simulated optical flow, so a
flow fault (a sensor reporting motion that is not there) cannot be injected
into an autotest.

## The conclusion and why

Two new SIM parameters, `SIM_FLOW_OFS_X` and `SIM_FLOW_OFS_Y` (rad/s), at
SIM `var_info` indices 37 and 38 (checked unique). The offset is added
after the scale factor, not subtracted as a body rate, so it reads as a
flow-rate error rather than a gyro error.

## Key findings

- Default 0 is a no-op; OpticalFlow passes at `c70437775c`.
- The consumer is #34292's OpticalFlowFocusHeight, which sets
  `SIM_FLOW_OFS_X` 1.0 rad/s (see `../34292/`).

## Shared commits

#34292 and #33484 carry the same two commits, patch-identical, until this
PR merges (see `../34292/` and `../33484/split-and-quality-gate.md`, which
list their hashes on those branches). A change to the injector here has to
be carried to both.

## What is here

```
34533/
  README.md    <- this file
```

## Reproduce

```
git checkout pr-sitl-flow-ofs
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.OpticalFlow
```

## Branches and people

- `pr-sitl-flow-ofs` - the PR branch (two commits).
- Author: @andyp1per.
