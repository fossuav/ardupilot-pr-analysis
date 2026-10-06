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
