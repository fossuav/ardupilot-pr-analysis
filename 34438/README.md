# PR #34438 - AP_HAL_ChibiOS: fix the threads.txt worst-slice mark

[ArduPilot/ardupilot#34438](https://github.com/ArduPilot/ardupilot/pull/34438),
branch `andyp1per/pr-thread-stats-counter-rate`, opened 2026-09-19 at
`3347cad7db` on master `368dc0c428`. Two commits, AP_HAL_ChibiOS only.

## What it does

`@SYS/threads.txt` marks a thread with `*` when its worst slice is over 5 ms.

- `e8887e739f`: the slice was converted with `RTC2US(STM32_HSECLK, ...)`, but
  thread statistics are timed with `chSysGetRealtimeCounterX()`, DWT `CYCCNT`
  at the core clock on STM32. The mark fell at 5 ms x HSE / core clock, about
  83 us on an H7 at 480 MHz with an 8 MHz crystal. Now converted at
  `HAL_EXPECTED_SYSCLOCK`, which `chibios_hwdef.py` always emits and
  `system.cpp` asserts equals `STM32_SYS_CK` (H7) or `STM32_HCLK`.
- `3347cad7db`: the "has run" test was `stats.best > 0`; `best` starts at
  `(rtcnt_t)-1`, so it was always true, and a thread that had not run printed
  `LOAD 0.0%` with the mark (`worst` 0, `RTC2US(f, 0)` wraps). Now the
  snapshot's `stats.n > 0`.

Found on #32995, where the RP2 SMP port's counter is a 1 MHz timer against a
12 MHz crystal (mark at 60 ms), and where the RP2350 `threads.txt` showed two
idle threads as `LOAD= 0.0%*`. The branch carries these as `d403dceaa5` (plus
the RP2 1 MHz case) and `b0a6e0ef94` (plus the SMP per-core loop), alongside
`c86b75980c`, which is SMP-only: the stats reset zeroed `last`, crediting a
thread running on the other core with the whole uptime. Since the branch's
2026-09-19 rebase onto `368dc0c428` the three are `4a4be74999`,
`bdefe5d54d` and `cd62494f12`.

## Evidence

- CubeOrange (H7) and MatekF405 (F4) build with `--enable-stats`, no warnings;
  CubeOrange rebuilt on the final head.
- The arithmetic of the old threshold: `RTC2US(8e6, n) > 5000` needs
  n >= 40001 cycles, 83.3 us at 480 MHz (100 us at the default 400 MHz).
- **Owed:** a `threads.txt` from an STM32 board built with `--enable-stats`,
  before and after; and on RPI_UAVFC, core1 idle against `core1load`.

## Review findings answered

- Claude: the per-family macro ladder always resolves to
  `HAL_EXPECTED_SYSCLOCK` - taken, the change became one token. It also found
  the always-true run test, which became the second commit.
- Codex, second commit: the run test read the live `tp->stats.n` while the
  printed values come from the snapshot one line earlier - taken, it tests the
  snapshot.
- Codex, first commit: no findings.
