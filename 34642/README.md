# PR #34642 - Let the SITL gyro rate follow INS_GYRO_RATE

Analysis archive for [ArduPilot/ardupilot#34642](https://github.com/ArduPilot/ardupilot/pull/34642).
Branch `pr-sitl-gyro-rate` (andyp1per fork), base `master`, head
`c66dba662b` (2026-10-06). Opened 2026-10-06, split out of [#34208](../34208/).
All numbers SITL.

## Status (one line)

SITL's IMU ran at 1 kHz whatever `INS_GYRO_RATE` said, so the fast rate thread
could not be run at real IMU rates in SITL. With fast sampling, the backend now
follows `INS_GYRO_RATE` (raw stream at 8x decimated to it); default unchanged.

## Changes from the version carried in #34208

A Codex cold read of the August version found the catch-up (generate every
due sample when `SIM_RATE_HZ` is below the gyro rate) applied to every SITL
setup, so low-rate configurations changed even at the default
`INS_GYRO_RATE` (stratoblimp runs `SIM_RATE_HZ 100`). Now the catch-up runs
only when `INS_GYRO_RATE` raises the rate; at the default the timer generates
one sample and skips missed ones as master does (confirmed by a second Codex
pass). Because the default timing is now unchanged, the `GPSBlendingAffinity`
armed-only fix that #34208 carried is no longer needed and was dropped (kept
locally as branch `test-gpsblending-armed`).

Documented limits (commit message): bursts of more than eight samples
overflow the rate loop's gyro buffer; gaps over 10 ms are resynced, so
`SIM_RATE_HZ` below 100 gets no catch-up; RealFlight drives the IMU from its
own frames and does not use it.

Rejected review points: catch-up samples carry historical timestamps with
the current SITL state - no worse than master's one sample per frame from the
same state.

## Tests

- `SITLGyroRate`: reports 1/2/4 kHz for `INS_GYRO_RATE` 0/1/2 and `IMU.GHz`
  converges. Fails on master (times out waiting for the 2 kHz report).
- `GPSBlendingAffinity`, `DynamicRpmNotchesRateThread`,
  `RateThreadPostFilterGyroLog` pass.

## 2026-11-02 (later): Sim on Hardware keeps its base gyro rate

AP-Review round 1 (COMMENT at `c66dba662b`) minor: Sim on Hardware boards are
H7s, where `INS_GYRO_RATE` defaults to 1 (`MPU_FIFO_FASTSAMPLE_DEFAULT`), and
CubeOrange enables fast sampling on all IMUs, so following `INS_GYRO_RATE`
doubled their simulated gyros to 2000/1520 Hz with catch-up bursts. The PR is
for desktop SITL (default 0), so the multiplier is now 1 outside
`HAL_BOARD_SITL`. With mult 1 the start path stores the same raw rate
(`_set_gyro_raw_sample_rate()` is a plain store), `gyro_nsamples` is 8 and
there is no catch-up, so the timer loop reduces to the pre-PR logic: Sim on
Hardware samples as before.

refresh12 `7d40b4a49e` (`r1102b/34642-r12`), PR `02d4f5cab2`
(`sq/34642-1102`, on top of `c66dba662b`). Not pushed. SITLGyroRate passes
on both; CubeOrange-SimOnHardWare copter builds with no warnings (the `#else`
path).

Pushed 2026-11-02 (afternoon) to andyp1per with a lease: `c66dba662b` -> `d464e2156a` (refresh12 `df341758a7` locks it). Reply: https://github.com/ArduPilot/ardupilot/pull/34642#issuecomment-6580088212.

## 2026-11-02 (night)

AP-Review round 2 (COMMENT at `d464e2156a`): fold the Sim on Hardware fix into its target. Folded into "let the SITL gyro rate follow INS_GYRO_RATE" (SITL-only code, so neither commit can fly): `sq/34642-1102c` head `49312747a0`, tree identical; backup `pre-squash/34642-1102`. Pushed 2026-11-02 at `49312747a0`.
