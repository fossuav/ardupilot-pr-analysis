# PR #34584 - Record per-loop rate modifiers for the fast rate thread

Analysis archive for [ArduPilot/ardupilot#34584](https://github.com/ArduPilot/ardupilot/pull/34584).
Branch `pr-rate-thread-scale-reset` (andyp1per fork), stacked on #34583, base
`master`, head `36cd051312` (2026-10-02, rebased onto `cafe674577`). Draft
until #34583 merges; only the last two commits are its own. All SITL.

## Status (one line)

Opened 2026-10-02 as a draft. Two commits: AC_AttitudeControl gives the rate
controller a recorded copy of the per-loop modifiers, and Copter records it as
soon as `update_flight_mode()` has built them. Self-reviewed with /pr-review;
the torn-copy finding is accepted and left to #34208's mechanism. Not flown.

## The defect

Copter's fast tasks run `run_rate_controller_main` (task order 117, which calls
`rate_controller_target_reset()`) well before `update_flight_mode` (136), with
`read_AHRS` in between. The reset sets `_pd_scale`, `_i_scale`,
`_sysid_ang_vel_body_rads` and `_actuator_sysid` to identity; the mode rebuilds
them. With the rate thread, the rate controller runs in that window with no
landed gain reduction (`ATC_LAND_*_MULT`, all default 1.0), no acro I scaling
(`scale_I_to_angle_P()`) and no SystemID injection. Heli has no
`rate_controller_run_dt()` and QuadPlane no rate thread; both unaffected.
Found while reviewing #34583, not reported by anyone.

## The fix

- `_rate_modifiers` in `AC_AttitudeControl_Multi`, read only by
  `rate_controller_run_dt()`. `pd_scale` and `i_scale` default to {1,1,1}
  because the rate thread can run before the first record (zero would turn PD
  and I off).
- `record_rate_modifiers()`: public virtual, no-op in the base (Heli), called
  by `rate_controller_run()` just before it runs (non-thread path and
  QuadPlane unchanged), by the reset override before it clears (fallback for
  any vehicle that does not call it), and by Copter after `flightmode->run()`
  when `using_rate_thread`.

## Measurements (SITL, tier 2)

1 kHz rate thread, 400 Hz loop, temporary probes in `rate_controller_run_dt()`
(`apply_probe.py` in each data directory patches the tree and adds a throwaway
test; never committed to the branch).

Landed in STABILIZE with `ATC_LAND_R_MULT=0.5`, PD scale the rate thread used
on each run (`TPDS`), excluding the 2 s ramp-in and everything after disarm:

| Build | runs at 1.0 | runs at 0.5 |
|---|---|---|
| master `877c45cd6f` (`master.BIN`) | 786 of ~7400 (10%), 948 separate single-run dropouts | rest |
| record at reset only (`record-at-reset.BIN`) | 0 | all |
| final, record after mode run (`final.BIN`) | 0 of 7753 | 7753 |

`record-at-reset.BIN` shows 4.2% at 1.0 under the probe's own quarter-skip
filter; all of it is one run starting 2.5 s after disarm, when the landed
reduction stops applying. Not a race.

SystemID `SID_AXIS=7` (rate roll) chirp 0.5-5 Hz, delay from the mode setting
a sample (SIDD, logged in the mode) to the rate thread first applying it
(`TSID`), matched on exact value:

| Build | median | p10 | p90 |
|---|---|---|---|
| record at reset only (`sysid-lag-ab/record-at-reset.BIN`) | 2.50 ms | 2.50 | 3.33 |
| final (`sysid-lag-ab/final.BIN`) | 0.83 ms | 0.00 | 2.50 |

Only ~50 samples match per run: at 1 kHz the logger drops rows. The residual
0.83 ms is ModeSystemId logging RATE inside `run()` before the record (Codex
cold read). Recording only at the reset was the first design; it fixed the
gains but put sysid a loop behind the rate target, which a review agent caught
(about 18 deg of unmodelled phase at 20 Hz / 400 Hz), hence the Copter commit.

## Why no permanent autotest

Tried 2026-10-02 (`RateThreadLandedGainReduction`, dropped): counting RATE
against ATSC rows. At 1 kHz the logger drops RATE and ATSC independently, so
the counts never pair (master and fix both "failed"), and a raced sample has
every scale at 1.0, so ATSC is not written for it at all. The race is
invisible to the existing logs; only a probe sees it.

## Accepted residual: torn copies

`record_rate_modifiers()` copies four Vector3f with no synchronisation, so one
rate run can pair one loop's PD scale with the previous loop's I scale (Codex
flagged it must-fix twice). Accepted 2026-10-02: each value is a valid per-loop
value, it lasts one sample, and it replaces unscaled gains for 10% of runs.
#34208 publishes the rate target with an odd/even sequence counter; the same
mechanism should publish these once it lands. Do not re-raise without that.

## Relation to other PRs

- #34583: prerequisite. On master's code the record would be taken before
  `update_throttle_gain_boost()` multiplies `_pd_scale`, silently dropping the
  PD boost, so this cannot go in alone.
- #34208: trial merge clean. Its "sysid added downstream so chirps stay crisp"
  still holds; sysid now arrives with the record instead of mid-loop. After a
  rebase onto it, `rate_controller_run_dt()` must read
  `_rate_modifiers.sysid_ang_vel_body_rads` and keep `_rate_target_rads` after
  the sysid add.

## Files

- `data/landed-scale-ab/{master,record-at-reset,final}.BIN`, `apply_probe.py`
  (TPDS probe plus `TmpScaleRace` test, for the final code). `master.BIN`
  logged `_pd_scale.x` instead, as master has no recorded copy;
  `record-at-reset.BIN` logged the same copy under its earlier name.
- `data/sysid-lag-ab/{record-at-reset,final}.BIN`, `apply_probe.py` (TSID probe
  plus `TmpSysIdLag` test), `sysid_lag.py`.
