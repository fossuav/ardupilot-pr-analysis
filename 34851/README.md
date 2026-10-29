# AP_NavEKF3: count range finder height as a ground measurement

**Open as [#34851](https://github.com/ArduPilot/ardupilot/pull/34851)**,
opened 2026-10-22 from `andyp1per/pr-ekf3-rng-hgt-ground` at
`da86aaa70f`, two commits on master `2badacc9a6`. Record written
2026-10-23.

**Read "Measured and rejected" before changing the code.** The obvious
one-line version of this fix was the first one written, pushed to the fork
and reviewed out; the reason is there.

## Why

SFD-O4 log54 (`INS_ACC_ID` 3408138, `STAT_BOOTCNT` 624; flown 2026-10-22
on the SFD beta refresh28, `0e2c9772`): an EKF failsafe at touchdown on
the flow lane. Flight analysis in
`../analysis/logs/sfdo4_log54_20261022.md`.

The copter hovered at 0.55 m on range finder height. On the beta, range
finder height can engage in a low hover (#33359 with `EK3_OPTIONS` bit 3);
on master it cannot. While the range finder is the height source the
terrain estimator does not run, so `gndHgtValidTime_ms` was 55 s stale and
`gndOffsetValid` was held up by the height source alone. Touchdown
sequence (log TimeUS):

| TimeUS | |
|---|---|
| 370.7 | range out of range low (`RFND.Stat` 2) |
| 371.085 | height falls back to baro (range 500 ms stale); `gndOffsetValid` and `horiz_pos_rel` drop in the same cycle |
| 372.07 | "EKF variance" failsafe, FS_EKF_ACTION 2 -> ALT_HOLD |
| 372.13 | land complete, 60 ms after the failsafe |

Master has the same gap wherever Copter uses range finder height: on
takeoff and in the land stage of LAND, RTL, SmartRTL and AUTO, the only
places it marks terrain stable (`ArduCopter/baro_ground_effect.cpp:38`).
Derived from the source, then shown in SITL (below).

## Change

- `600fa427de` AP_NavEKF3: new `lastRngHgtPassTime_ms`, stamped in
  `FuseVelPosNED()` when a range finder height observation passes its
  innovation check; `gndOffsetValid` holds for 5 s after it.
  `gndHgtValidTime_ms` and its readers (the terrain estimator's re-anchor,
  the switch hysteresis) are untouched.
- `da86aaa70f` autotest `EK3_RngHgtFlowLandingKeepsPosition`, two
  subtests: a flow-only LAND from 10 m with the range out of range low on
  the ground, and a hover on `EK3_SRC1_POSZ` 2 that loses the range in
  flight.

## Evidence

### Replay of log54 (tier 1b)

On the beta the flight was flown on (`0e2c97724d`), with the beta port of
the final change (the same code plus the matching line in #33585's
flat-ground restore, which master does not have). Replayed cores log as
C 100/101. Run 2026-10-22.

| build | core 1 relative position | estimates |
|---|---|---|
| unfixed | lost at 371.085, the fall back to baro (matches the flight) | - |
| final change | held to disarm | XKF1 PN, PE, PD, VN, VE, VD and XKF5 TOfs, HAGL, RI on both replayed cores identical to the unfixed replay in all 7956 records |
| first version (rejected, see below) | held to disarm | identical as well |

Master's own EKF was not replayed: the low hover on range finder height
that set this up is beta-only. A temporary `XDBG` `WriteStreaming()` in
`updateFilterStatus()` showed the height source and `gndOffsetValid` per
frame; Replay writes it without its FMT record, so it was parsed by hand.

### SITL (tier 2)

Master `2badacc9a6` plus the PR, 2026-10-22/23.

| case | result |
|---|---|
| the change (`da86aaa70f`) | passes, 3 of 3 runs; landing holds position to disarm 2.2 s after out of range low; in flight held 5.0 s after the range goes out of range high, EKF failsafe at 5.9 s |
| no change (EKF3 from the merge base) | fails: relative position lost 0.45 s after out of range low (0.50 s on one of four master runs), EKF failsafe ERR at 1.35 s, disarm at 2.17 s |
| bound removed (`lastRngHgtPassTime_ms != 0`) | fails the in-flight leg: "still held 7 s after the range was lost" |
| `EK3_RNG_USE_HGT` -1 | fails the trace check: XKF5 RI took 7 values and TOfs 6 over the descent; with range finder height both held one value over 260 samples |

The trace check exists because no logged field shows the height source:
`EstimateTerrainOffset()` is the only writer of `innovRng` and
`terrainState` while range finder height is in use (the others are
guarded by `inhibitGndState` or run on a height reset), so RI and TOfs
stand still exactly. Derived from the source, then measured as above.

The 24 nearby master autotests pass with the same EKF code (run at
`f5f891a61d`, which differs from the head in a comment only):
EK3_RNG_USE_HGT, EK3_OptflowTerrainScaleHeight,
EK3_AccelBiasZeroVelOptFlow, BaroGroundEffectRangefinderSwitch,
EK3_OGN_HGT_MASK, EK3_OGN_HGT_MASK_climbing, LoiterFlowBrakeOvershoot,
FlowAidingRestartsWithoutYawFusion, FlowGyroZBiasNoYawReference,
ModeFlowHold, OpticalFlow, OpticalFlowLimits, OpticalFlowLocation,
OpticalFlowCalibration, FlyRangeFinderSITL, RangeFinder,
TouchdownGroundEffectAlt, TakeoffGroundEffectAlt,
GroundEffectCompensation_touchDownExpected, TerrainFailsafe, Replay,
EKFSource, Landing, PrecisionLanding. Copter builds with
`AP_RANGEFINDER_ENABLED 0` and with `AP_OPTICALFLOW_ENABLED 0`.

On the SFD beta (refresh11 topup1, `f874a71d55`, pushed in
`5b70a27117`) the same test fails without the change (0.45 s) and passes
with it, and 18 related beta tests pass (Replay on a rerun; the first hung
in a SITL reboot).

### Flights on the SFD beta, with Replay counterfactuals (tier 1 / 1b) - 2026-10-29

SFD-O4 logs 55-59, outdoor, GPS lane primary at every landing, `DISARM_DELAY`
0 (switch disarm). logs 55-57 flew refresh11 before the beta port
(`6d754361`), logs 58-59 with it (`59386e92`). Each replayed through
`6d7543612b` (without) and `109e527fd3` (with, the EKF of `59386e92`); the
replay of the build that flew reproduces every flown transition of the flow
lane's `XKF4.SS` bits 3 and 6. Flow lane (core 1) relative position at
touchdown:

| landing | without the change | with it | land complete | disarm |
|---|---|---|---|---|
| log58 | lost 244.966 (replay) | held (flown) | 245.748 | 246.367 |
| log59 | lost 192.667 (replay) | held (flown) | 192.968 | 192.968 |
| log57 flight 1 | lost 366.671 (flown) | lost 370.571 (replay) | 366.922 | 374.672 |

log58 is log54's race on another flight: 0.78 s before land complete
without the change, nothing with it. log57 flight 1 is the residual this
record's Open list carries: the hold ends 5 s after the last range height
fusion and the pilot took 7.75 s after land complete to disarm. The same gap
also cost the flow lane its position in flight on `6d754361`, for 0.1-0.5 s
at three take-offs and twice climbing through 0.9 m after a long hover on
range height; all five are gone with the change. No landing was flown with
the flow lane primary, so no failsafe was at stake. Analysis:
`../analysis/logs/sfdo4_logs52-59_20261029.md`.

## Measured and rejected

| change | argument for | why rejected |
|---|---|---|
| Stamp `gndHgtValidTime_ms` on each range height fusion (first version `1b05201ef4`, pushed to the fork 2026-10-22, never opened) | One line. The range is fused through `terrainState` there, which measures the ground as the terrain estimator would | Pre-PR review, derived from the source: that timestamp also drives the terrain estimator's re-anchor (`terrainState` reset to the range after 5 s without an update, `AP_NavEKF3_OptFlowFusion.cpp:120`), so after a switch out of range height with the range still valid the re-anchor stopped firing and a height reset at the switch stayed in the flow's height above ground. It also stamped before the height innovation gate. The log54 Replay could not tell it from the final version (both held), so the flight is no evidence either way |
| Treat out of range low as being on the ground, so range height carries on through touchdown | `readRangeFinder()` already substitutes `rngOnGnd` while disarmed | Out of range low only means closer than `RNGFND_MIN`, which a hover below the minimum also reads; it would fuse a wrong height there. Inspection |
| Apply the new term only while the fall-back source is baro | A fall back to GPS, or a source set switch to external nav or no height source, resets the height without moving `terrainState`, so the height above ground can be off while reported valid | The same is true within the terrain estimator's own 5 s hold on master, and #33585 carries `terrainState` across that reset. Stated in the PR description rather than gated. Inspection |
| `XKF5.BOf` (baro offset) as the trace that range height was in use | Filtered only while baro is not the height source | Master also freezes it while touchdown is expected (`baroInGndEffect`), which is the whole slow LAND descent. Derived from the source |
| `XKF4.SH`, `XKF3.IPD` or `XKV1.V09` as a trace of the fall back to baro | The height innovation changes source at the fall back | SITL 2026-10-23: SH read 0.00 throughout, IPD took 1-2 values in every window, V09 rises after out of range low whether nothing or baro is fused. No logged field shows it; the test checks the range stays non-Good for 0.6 s before a held sample instead |

## Review before opening

Three rounds, 2026-10-22/23: Claude reviewers per commit and on the whole
diff, Codex cold reads, and Codex audits of every earlier finding. The
redesign above came out of round 1. Also taken: commit messages in
master terms (Loiter cannot reach this path on master); the reader list
under ARCH-1 (`horiz_pos_rel`, `dead_reckoning`, JammingExpected's
`canDeadReckon`, `terrain_alt`, `getHAGL()` and its AP_GroundEffect,
Lua and OPTICAL_FLOW readers, the SRTM fallback); the estimates that do
move (SRTM terrain, drag fusion's wind states, JammingExpected); the
in-flight leg for the refused half of the rule; per-lane XKF5 grouping;
an assertion on the EKF failsafe itself.

Rejected, with the reason:

- Disclose AI assistance in the description (Codex, rounds 2 and 3): the
  root playbook makes no claim either way.
- "The hold reaches before takeoff through the on-ground `rngOnGnd`
  substitution" (round 2): refuted from the source - `readRangeFinder()`
  `continue`s on a non-Good reading before the substitution, so an out of
  range low range finder gives no range height fusion before takeoff.
- "The replay never exercised the re-anchor path" (round 1): moot after
  the redesign, which no longer touches the re-anchor's timestamp.
- Guard `lastRngHgtPassTime_ms` under `EK3_FEATURE_OPTFLOW_FUSION`, where
  it is unread: `gndHgtValidTime_ms` and `gndOffsetValid` follow the same
  unguarded pattern; 4 bytes per core.

"Checked by a human programmer" is left unticked for the author.

## Open

- Merge order with #33585 and #34380. Both read `gndOffsetValid`, and
  #33585's `ResetPositionD()` comment says it "goes false in the very
  cycle the source changes", which this change makes untrue. Whichever
  merges second re-checks those readers.
- Unflown. No flight has run the change (beta topup pushed 2026-10-22).
- A landing whose land detector takes more than about 4.5 s still loses
  position then, as a flow vehicle without `EK3_RNG_USE_HGT` does. On the
  beta, where range height engages in hover, a Loiter landing does this
  while waiting out `DISARM_DELAY`, after land complete.
- EKF2 has the same gap, left alone.
- #34894 (issue, 2026-10-26): `FuseVelPosNED()` stamps its pass times at
  the innovation gate, before `FinishFusion()` can refuse the update on a
  negative variance, so a lane whose updates are all refused never times
  out. `lastRngHgtPassTime_ms` is stamped at the same point and shares
  that blind spot: a refused range height update would still hold the
  ground offset valid. If the issue is fixed by stamping only applied
  fusions, this stamp moves with them. Comment posted on the issue
  2026-10-27 (derived from the source, not run).

## Reproduce

```sh
# in an ArduPilot checkout at da86aaa70f
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.EK3_RngHgtFlowLandingKeepsPosition

# without the change: fails "relative position lost 0.45 s after out of range low"
git checkout 2badacc9a6 -- libraries/AP_NavEKF3/ && ./waf copter
Tools/autotest/autotest.py test.Copter.EK3_RngHgtFlowLandingKeepsPosition
git checkout HEAD -- libraries/AP_NavEKF3/

# a hold that never ends: fails "still held 7 s after the range was lost"
sed -i 's/((imuSampleTime_ms - lastRngHgtPassTime_ms) < 5000)/(lastRngHgtPassTime_ms != 0)/' \
    libraries/AP_NavEKF3/AP_NavEKF3_OptFlowFusion.cpp && ./waf copter
Tools/autotest/autotest.py test.Copter.EK3_RngHgtFlowLandingKeepsPosition
git checkout HEAD -- libraries/AP_NavEKF3/
```

The Replay needs log54 resolved through `find_log.py` (see
`../REPLAY_LOGS.md`) and the beta at `0e2c97724d` with the change ported;
`build/sitl/tool/Replay <log>` from an empty directory.
