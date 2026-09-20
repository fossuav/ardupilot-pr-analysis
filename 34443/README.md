# PR #34443 - AP_Param: enforce @READONLY defaults over stale stored values

[ArduPilot/ardupilot#34443](https://github.com/ArduPilot/ardupilot/pull/34443),
branch `andyp1per/pr-param-readonly-defaults`, opened 2026-09-20 at
`d70e7b5c23` on master `368dc0c428`. One commit, AP_Param only.

## What it does

`@READONLY` in a board's `defaults.parm` did not survive a stored value.
`load_all()` reads storage unconditionally, so a value written by an earlier
firmware won at every boot. The storage scan now re-applies the read-only
default as soon as it finds the parameter among the overrides, and a sweep at
the storage sentinel catches parameters that are not in storage at all. The
in-loop pass is also what runs when storage carries no sentinel and the sweep
is never reached.

## Why it matters more than it looks

`AP_Param::allow_set_via_mavlink()` returns false for a read-only parameter, so
the stale value cannot be corrected over MAVLink either: the board is stuck
short of erasing storage.

Sixteen board directories ship `@READONLY` defaults, thirteen of them released
before this branch. The ODID variants are the sharp case - `CubeOrange-ODID`
and the rest lock `DID_ENABLE`, `DID_OPTIONS` and `DID_MAVPORT` under a comment
saying the lock is there "to ensure the integrity of the RemoteID system",
which a stale stored value silently defeats.

## Evidence

- SITL and CubeOrange build clean at `d70e7b5c23`.
- The refusal path was read rather than assumed: `allow_set_via_mavlink()`
  (`AP_Param.cpp:1463`) returns false when `is_read_only()`.
- The board count is from the tree: `grep -rl '@READONLY'
  libraries/AP_HAL_ChibiOS/hwdef/*/defaults.parm` gives 16, of which Laurel,
  RPI_UAVFC and RPI_UAVFC-SimOnHardWare come from #32995.
- **Owed:** a hardware or SITL demonstration of the failure it fixes - store a
  value for an `@READONLY` parameter, reboot, and show which one wins before
  and after.

## Where it came from

Split out of [#32995](../32995/), which carries the same commit and drops it
when this merges. The 2026-09-19 automated review on that PR asked for it to be
separated, since it changes behaviour on thirteen released boards.
