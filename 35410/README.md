# PR #35410 - don't hold the fast rate thread for OneShot pulses

Analysis archive for [ArduPilot/ardupilot#35410](https://github.com/ArduPilot/ardupilot/pull/35410).

**2026-11-27:** opened at `a8e43601f2` (branch `rcout-oneshot-trigger` on
andyp1per), three commits on master `caa5f0d272`. Found while enabling
OneShot on RP2350 for #32995: with `FSTRATE_ENABLE` and `MOT_PWM_TYPE` 1
every push from Copter's rate thread waited in `trigger_groups()` for the
last motor pulse, so a 1591 Hz rate thread ran at about 940 Hz armed, and
disarmed its rate logic flooded the GCS with "Rate CPU" messages. Bench
only, on an RP2350 quad; no STM32 hardware run, no flight. Carried on the
alpha2 branch from `6d5570e1d2`, after #35358.

## Conclusion

A push from the fast rate loop no longer waits. It writes its widths under
`trigger_mutex` and sets a virtual timer for when the pulses in flight and
their 50 us gap are over; the rcout thread then starts the newest widths.
Armed at 1591 Hz the rate loop's dt median went from 1062 us to 674 us
(DShot600: 668 us), and the motors got 896 pulses a second against 921
before, of at most 926 for 1030 us pulses. Measured on the bench, see
[bench-2026-11-27-copter-fastrate-oneshot.md](bench-2026-11-27-copter-fastrate-oneshot.md).

## Key findings

- The wait is upstream ChibiOS code and applies on STM32 alike; RP2350
  reached it only once #32995 gained OneShot. OneShot125's pulses fit a
  628 us cycle and never waited.
- Skipping a push that came during a pulse, leaving its widths to the next
  push (the first branch, `rcout-oneshot-rate-thread`, 14b257eb69), held
  the rate loop but cut the motors to 703 pulses a second. Review caught
  it; the timer design replaced it.
- Four review rounds, each with Claude reviewers and Codex cold reads and
  audits, then found and closed: a waiting push sleeping with the mutex
  held (a Lua write could stall the rate thread), the timer armed outside
  the mutex, a lost trigger after a sleep, and a late or early timer event
  repeating or dropping a push. The final design never sleeps holding the
  mutex and records which trigger the timer waits for.
- Copter's rate thread runs at `PRIORITY_RCOUT` + 1 (182), above the rcout
  thread (181), so on a single core the timer's pulses start once the rate
  thread blocks. The bench board runs the two on separate cores, so that
  delay was not measured. Derived from the source, not measured.
- In cases A to F a force-armed quad with no RC was disarmed by the radio
  failsafe 0.03 s after each arm, so only their disarmed results stand;
  G onwards ran with `FS_THR_ENABLE` 0 and checked every heartbeat.
- The rate logic steps back up 100 ms after each step down rather than at
  its 10 s retry, which is half of the message flood. Not in this PR.

## Files

- `bench-2026-11-27-copter-fastrate-oneshot.md`: every case, method and
  table.
- `data/2026-11-27-copter-fastrate/`: `copter_fastrate.py` (sets the motor
  type, reboots, samples the motor slices over SWD, force-arms),
  `rtdt.py` (RTDT dt by armed state from a log), one JSON per case, and
  `trigger_groups_noblock_prototype.diff` (case B2). The dataflash logs,
  parameter reads and storage copy are kept locally, not committed.

## Reproduce

On an RPI_UAVFC with Copter, no props and the ESCs unpowered, bridge the
USB serial to 127.0.0.1:5770 (`../32995/tools/scripting_profile/bridge.py`)
and attach a CMSIS-DAP probe. Flash the build under test, then:

    python3 data/2026-11-27-copter-fastrate/copter_fastrate.py case \
        <label> <outdir> FS_THR_ENABLE=0 MOT_PWM_TYPE=1

Fetch the run's log over MAVFTP and run `rtdt.py` on it. Put
`FS_THR_ENABLE` and `MOT_PWM_TYPE` back afterwards.
