# RC_Channel: an aux function to select the EKF primary core

**Open as [#35366](https://github.com/ArduPilot/ardupilot/pull/35366)**,
opened 2026-11-24 from `pr-ekf-primary-aux` at `f47655a6df`, on master
`68b1a73ef2`. Asked for on #34456 by rishabsingh3003: an RC switch for
lane selection as its own aux function, with #34456 cut to refusing a
source set selection under `EK3_SRC_OPTIONS` bit 3.

## What it does

`RCx_OPTION` 188 (EKF Primary Core) sets `EK3_PRIMARY` with
`set_and_notify()`, for this boot only: low, middle and high select cores
0, 1 and 2. Disarmed the primary moves at once; armed it needs
`EK3_OPTIONS` bit 1, as a change to `EK3_PRIMARY` does. Refusals say why:
the EKF for a core that is not running or a change while armed without
bit 1, AHRS when EKF3 is not the configured estimator. AHRS passes the
live armed state (`hal.util->get_soft_armed()`), as the DAL holds it only
as of the last EKF update. Before the cores start a core `EK3_IMU_MASK`
names is taken; the DAL has not counted the IMUs then, and a core whose
IMU is missing falls back to 0, as `EK3_PRIMARY` does. Compiled out
without EKF3 (`AP_AHRS_NAVEKF3_ENABLED`).

Commits: `9a9d475d68` AP_NavEKF3, `f566f96e37` AP_AHRS, `0991d8ee4f`
RC_Channel, `f47655a6df` autotest.

## Evidence

- SITL, tier 2: `EKF3PrimaryCoreSwitch` passes 3 of 3 at the head. With
  the armed refusal removed it fails at the armed leg.
- Replay of the test's log (LOG_REPLAY on): the four primary core changes
  replay; of 312 XKF4 rows at matching times two differ, one at each of
  two changes, where Replay already shows the new core. A parameter
  changed in flight is applied by Replay up to one EKF update early.
- Flash against master `68b1a73ef2`: +392 bytes MatekF405, +440
  Pixhawk1-1M. Builds with `HAL_NAVEKF3_AVAILABLE` 0, and Plane and Rover
  build.

## Review before opening

Mechanical gate clean. Codex cold reads of each commit and of the whole
diff over four rounds. Taken: the pre-start core count, an explicit
`EK3_IMU_MASK` in the test, a test leg for another estimator, the
`AP_AHRS_NAVEKF3_ENABLED` guard, an index the EKF refuses for a switch
position that matches no case, and the live armed state. Declined:
- A build without GCS logs no parameter change, so Replay cannot follow
  this or any other parameter changed in flight there.
- A call through Lua's `rc:run_aux_function()` writes the parameter on
  the scripting thread, as every aux function and Lua's `param:set()`
  already do.
- AHRS's configured estimator is cached for one AHRS update.
- Each successful selection is announced; an RC switch selects only on a
  change, as `EKF_SOURCE_SET` does.

Note: `Tools/scripts/size_compare_branches.py` without
`--parallel-copies` checks branches out in the current directory and
deletes its `build/`; run it in a scratch worktree.

## 2026-11-27: rebased onto master after #34456 merged

Merged #34456 (2026-11-26) adds EKF3SRCPerCoreSelection at the place this
PR adds EKF3PrimaryCoreSwitch, which git split into alternating hunks.
Both kept whole, master's first, each identical to its source;
registration union. The PR's net added and removed lines match the old
head's, file by file.

SITL (tier 2): Copter builds; EKF3PrimaryCoreSwitch and
EKF3SRCPerCoreSelection pass. Pushed `626c4fc53d` -> `9dbd5880df` (force).
