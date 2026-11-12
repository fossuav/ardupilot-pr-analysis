# PR #32391: Copter: add separate LEVEL arming check for lean angle

Open upstream (branch `pr-imu-leaning`, head `504742adf1`, last updated
2026-09-30). Carried on the SmallFastDrone branches.

The lean-angle arm check ("Leaning", against `ATC_ANGLE_MAX`) sits under
the INS check, so the only way to arm a copter held on its side or nose
down for a throw or a bench calibration was to skip all of INS. This PR
gives it its own `ARMING_SKIPCHK` bit, Level, so it can be skipped
alone.

## The bit moved between SFD releases

| Branch | Commit | Level bit |
|---|---|---|
| SFD 4.7.0 and 4.7-beta | `1eb46d06d7` (2026-03-08) | 21, after OSD; `CHECK_LAST` moved to 22 |
| SFD 4.7.2-beta and the PR's head | `164f8406e0` (same date, rewritten) | 9, shared with Plane's AIRSPEED; `CHECK_LAST` stays 21 |
| upstream master | - | none |

Nothing migrates the old bit. A parameter file from a 4.7.0 build keeps
bit 21, which the 4.7.2 builds do not read, so the lean check comes back
without a word. The SFD refresh notes record the move ("A 4.7.0
parameter file does not mean the same thing here"); a released build used
the old bit, which is the case the root playbook's ARCH-6 asks to be
migrated.

## 2026-11-12: the lean check back on a 4.7.0 parameter file (tier 1)

log11 (3408138/67), SFD refresh15 (`66fe7b62`), a TBS_LUCID_H7 quad with
`ARMING_SKIPCHK` 2097420 (bits 2, 3, 8 and 21) and `ATC_ANGLE_MAX` 80,
held at -82 to -87 deg pitch to arm in ACRO for a baro thrust ramp. The
last of several refusals, at 58.3 s, was "Arm: Leaning": the check ran
under `check_enabled(Check::LEVEL)` with bit 9 clear. 780 (bits 2, 3, 8,
9) is what the old value meant on this build. The quad was then armed
level and rotated by hand, and ACRO's angle loop, holding the arming
attitude, drove the front motors to 1950 at zero stick once a throttle
blip cleared the landed flag (ACRO's angle loop and `ATC_THR_MIX_MAN` 4,
not this PR).

## Review findings still open

From the AI review (`Tools/SFD/PR_STATUS.md` in the SFD fork):

- It reuses AIRSPEED's bit 9, and the `ARMING_CHECK` to `SKIPCHK`
  conversion silently drops the lean check; in SITL it "arms while
  rolled 90 degrees".
- The failure is reported as `Check::INS`, not LEVEL
  (`check_failed(Check::INS, ...)` inside the LEVEL test in
  `AP_Arming_Copter.cpp`; derived from the source).

Not decided: a one-time migration of bit 21 to 9 on the SFD branches
(upstream never had bit 21), and whether the PR should take a free bit
rather than share 9.
