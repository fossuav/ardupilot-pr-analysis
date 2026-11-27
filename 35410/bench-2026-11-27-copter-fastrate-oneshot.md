# Bench 2026-11-27: Copter's fast rate thread with OneShot motors

Question: does `RCOutput::trigger_groups()`'s pulse-separation wait hold up
Copter's rate thread when the motors are OneShot? The wait is shared
ChibiOS code, not RP2350's; RP2350 reaches it now that OneShot runs there
(`rp2350-oneshot-buzzer`, 151ef305e8).

Board: the RPI_UAVFC test quad on COM15, USB power only (battery 0.37 V, so
the ESCs were unpowered), no props. `FSTRATE_ENABLE` 2, `FSTRATE_DIV` 2,
3.2 kHz gyro, so a 1591 Hz rate thread; `SCHED_LOOP_RATE` 200. Firmware:
Copter at a600ccc8d7 (alpha2 plus the OneShot and buzzer commits). Found on
031f2549 with `MOT_PWM_TYPE` 6, and put back that way: parameters as found
apart from those updated at boot. The parameter reads, storage copy and
dataflash logs are kept locally, not committed: real-board logs stay out
of this repo.

Method (`copter_fastrate.py case`): set `MOT_PWM_TYPE`, reboot, 25 s
disarmed collecting "Rate CPU" texts, then force-arm in STABILIZE for about
9 s and force-disarm. In cases A to F the radio failsafe (`FS_THR_ENABLE`
1, no RC) disarmed the quad 0.03 s after each arm, so their "armed" columns
are disarmed: only their disarmed results stand. Cases G to L ran with
`FS_THR_ENABLE` 0, and every heartbeat in the armed window read armed.
Over SWD, the motor slices' counters (3 and 4) are sampled about 700 times
a second: with OneShot each trigger restarts them, so their spread is the
interval between triggers.

Disarmed only (see above):

| Case | `MOT_PWM_TYPE` | Rate thread | "Rate CPU" texts | Trigger interval (median, p90, p99 counter) |
|---|---|---|---|---|
| A | 6, DShot600 | 1591 Hz | 1, at the arm | PIO; slices unused |
| B | 1, OneShot | flaps between 795 and 1061 Hz, down to 636 Hz after each arm-disarm | 257 in 25 s, 95 in the 9 s after the arm | 548, 980, 1190-1290 us |
| C | 2, OneShot125 | 1591 Hz | 1 at start | 312, 590, 660 us (8 MHz counts / 8) |
| B2 | 1, OneShot, prototype | 1591 Hz | 1 at start | 690, 1250, 1600 us |

## Armed, rate fixed (cases G to L, `FS_THR_ENABLE` 0)

RTDT from the log of each run (`rtdt.py`); its `dtAvg` field holds the
nominal period, 628 us, so the measured loop time is `dt`.

| Case | Firmware | Motors | dt median | dtMax median / largest | Motor pulses/s |
|---|---|---|---|---|---|
| H | a600ccc8d7 (waits) | OneShot | 1062 us | 1161 / 1252 us | 921 |
| G | plus skip to the next push | OneShot | 674 us | 721 / 895 us | 703 |
| J | plus timer at pulse end | OneShot | 677 us | 735 / 874 us | 904 |
| K | plus timer at pulse end | OneShot125 | 673 us | 724 / 842 us | 1615 |
| I | a600ccc8d7 | DShot600 | 672 us | 723 / 904 us | PIO |
| L | plus timer at pulse end | DShot600 | 671 us | 733 / 880 us | PIO |
| P | final (v4) | OneShot | 674 us | 739 / 868 us | 896 |
| Q | final (v4) | OneShot125 | 663 us | 729 / 900 us | 1633 |
| R | final (v4) | DShot600 | 668 us | 730 / 850 us | PIO |

Motor pulses per second are each pad's high fraction over SWD divided by
the pulse width (1030 us armed; OneShot125 128.8 us). With 1030 us pulses
and the 50 us gap the most OneShot can give is 926 a second.

G ran the first upstream branch, `rcout-oneshot-rate-thread` (790bb6a569,
14b257eb69): a push from the rate thread while the last pulses were going
out returned, leaving its widths to the next push. The rate loop kept its
rate but the motors got a pulse only every second push, 703 a second,
fewer than the 921 the waiting code gave. Review caught it, and the
redesign, `rcout-oneshot-rate-thread-noblock` (6270741938, 257aaa97d0,
6b019ee521), sets a virtual timer for the end of the pulses instead, which
wakes the rcout thread to start them (J, K, L): the rate loop at DShot's
`dt`, and the motors at 904 pulses a second. No case with the timer gave a
"Rate CPU" text beyond the one at arming.

Review of that version found that a waiting push slept holding
`trigger_mutex`, which the new blocking lock in `push_local()` turned into
a stall of the rate thread behind any thread's sleep, and that a late or
early timer event could repeat or drop a push. The final version, opened as
#35410 at `a8e43601f2` (6270741938, 4f21d5fc75, a8e43601f2; the bench ran
the same code before its comment and message fixes), never sleeps holding
the mutex and records which trigger the timer waits for. Cases P, Q and R ran it. The rate thread is created
at `PRIORITY_RCOUT` + 1 (182), above the rcout thread (181), so on a
single core the timer's pulses start once the rate thread blocks; the
bench board runs them on separate cores.

## Disarmed, rate adapting (cases A to C, B2)

In B every push from the rate thread waited in `trigger_groups()` for the
previous 1000 us pulse plus 50 us, so the thread ran at about 950 Hz
against its 1591 Hz, missed gyro samples, and its rate logic stepped down
and back up about five times a second, each step a STATUSTEXT: about ten a
second. OneShot125's 125-250 us pulses fit inside the 628 us cycle and
never wait.

B2 ran an earlier prototype (`trigger_groups_noblock_prototype.diff`): a thread
other than the main loop returns instead of waiting when the previous
pulses are still going out, leaving the new widths to the next trigger. The
rate thread held 1591 Hz; the motors got a pulse every second push, with
the newest width. The main loop keeps the wait; `timer_tick()` triggers only
after the pulses end, so the change does not reach it.

## Notes

- Not measured on STM32. The wait and the rate thread's push path are the
  same code there.
- Copter has no `ONESHOT_MASK`; its oneshot outputs are the motors, and any
  output sharing a timer with them. The servo case, `ONESHOT_MASK` with a
  rate thread, comes with QuadPlane's rate thread, not yet upstream.
- The rate logic's flapping is a second issue: after dropping a step it
  steps back up after 100 ms at the lower rate whenever the higher rate had
  lasted 100 ms before falling behind, rather than at the 10 s retry, so a
  limit between two steps gives a STATUSTEXT about every 100 ms.
