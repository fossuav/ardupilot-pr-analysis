# PR #29000 - Copter: switch off fast rate while doing temperature calibration

Analysis archive for [ArduPilot/ardupilot#29000](https://github.com/ArduPilot/ardupilot/pull/29000).
Branch `andyp1per/pr-fast-rate-tcal`. Record started 2026-10-30.

## 2026-10-30: the boot-time park kept the start-up rates

AP-Review at 4cc85b68cf (rebased, code unchanged since dfff83a3a3). Local
branch r1030/29000 in /home/andy/github/r1030-29000, not pushed.

Boot-time park, confirmed. Learning only starts at boot (`tcal_learning` is
set only in `AP_InertialSensor::init()`), so the PR's gate parks the rate
thread on its first pass. The `rate_controller_set_rates()` call before the
loop had already applied the fast rates, and `disable_fast_rate_loop()`
never runs because `was_using_rate_thread` is still false. The main loop
resets the motors dt and the PID notch rate; the DShot period stays at a
fast-rate multiple when `SERVO_DSHOT_RATE` is non-zero. The bot is right
that `was_using_rate_thread || using_rate_thread` would not help: both are
false at boot. Fix c240e41d38 drops the call and zero-initialises `rates`;
`enable_fast_rate_loop()` sets the same rates before anything reads them.

Normal start (`FSTRATE_ENABLE` 1, no tcal), ProbeFastRateBoot, five runs
each of 4cc85b68cf and the fix: the same 999 Hz start, two messages before
and one after; RTDT median dtAvg 1.000 ms in all ten. CPU-high drops to
about 500 Hz appeared in both (3/5 and 4/5 runs) with other agents' SITL on
the host, so they are host load.

Autotest 85bc15f741, RateThreadTempCal (the bot's 18 s recipe): no "rate
set to" before "TCAL[1]: completed calibration", one after.

| binary | md5 | "rate set to" during the cal | result |
|---|---|---|---|
| master 5b36047100 | 12fde90c | 2 x 999 Hz | FAILED |
| PR head 4cc85b68cf | a383303c | 1 x 999 Hz (start-up call) | FAILED |
| with c240e41d38 | fd8ecc4c | 0; 1000 Hz after completion | PASSED |

RateThreadPostFilterGyroLog, CompassMotFastRate and RateThreadTempCal pass
on the fix; parameter leak check clean.

Calibration A/B for the "why" question, ProbeTCalAccuracy: Plane
IMUTempCal's `SIM_IMUT1/2` model, accel and gyro cal at 12 C, both IMUs
learning 3 C to 42 C with `FSTRATE_ENABLE` 1, then corrected error at fixed
5 C to 40 C. Master ran the fast loop through the cal (1000 Hz, a drop to
500 Hz and back); the fix stayed parked until completion. All 42
`INS_TCAL1_*`/`INS_TCAL2_*` values identical to nine significant digits.
Corrected error at most 0.094 m/s/s and 0.068 deg/s in both, differing by
at most 0.002 m/s/s and 0.004 deg/s (noise in a 20-sample telemetry
average). SITL's IMU sample path does not depend on the rate thread, so
this says nothing about hardware either way. No mechanism that would bias
the fit has been found: the Invensense(v3) non-primary FIFO slow-down
applies only to IMUs in `INS_FAST_SAMPLE` (default 1), and every sample
still reaches the learner with the main-loop-published temperature.

Guard: the `#if HAL_INS_TEMPERATURE_CAL_ENABLE` guard is still in the PR
commit; nothing to restore. MatekF405 text: head 871292, fix 871296 (+4);
the `{}` initialiser costs 16 bytes and the removed call saves 12 (871280
without the initialiser).

Description and thread reply drafted for Andy, not posted. The autotest
commit subject is 74 characters; the pr_review gate notes it (~72).

Pushed 2026-10-30 to andyp1per with a lease on the old head: `4cc85b68cf`
-> `fbf9c380f9`.
