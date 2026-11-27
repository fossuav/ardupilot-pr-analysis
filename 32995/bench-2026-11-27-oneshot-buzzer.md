# Bench 2026-11-27: OneShot and the buzzer on the RPI_UAVFC flight board

Board: the RPI_UAVFC flight wing on COM32, picoprobe on COM10, USB power,
running alpha2 Plane f7852587. Its configuration was left untouched: no
parameter was set. Throttle on output 1 is DShot600 (`SERVO_BLH_MASK` 1,
bidirectional), the elevons are outputs 3 and 5 (77, 78), and
`ONESHOT_MASK` 20 asks for OneShot on both. `SERVO8_FUNCTION` is 0, with no
LED strip. `SCHED_LOOP_RATE` 200.

Two faults reported: OneShot did nothing, and the RCOut banner said
", buzzer off" although no LED was configured.

Firmware under test: alpha2 (e2e66b61dc) plus branch
`rp2350-oneshot-buzzer` (151ef305e8 OneShot, 745189e2d6 output 8 with
function 0, then three documentation commits to a600ccc8d7), built first
from the uncommitted tree (reporting e2e66b61) and then at a600ccc8d7.

Before flashing, the parameters were read (1731) and the parameter
storage flash, 0x10010000 to 0x1001FFFF, was copied raw over SWD; both
are kept locally beside `data/2026-11-27-flight-board/`, not committed,
as they are the flight board's configuration.

Method: `oneshot_bench.py measure`, which reads the banner and
`SERVO_OUTPUT_RAW`, the slice registers, then samples each output's slice
counter and pad level (IO_BANK0 `OUTTOPAD`) about 400 times a second for
6 s, and plays `MFT60L1O4CC` while sampling slice 1.

| | f7852587 (alpha2) | with the fixes |
|---|---|---|
| Banner | `DS600:1-2 PWM:3-8, buzzer off` | `DS600:1-2 OneS:3-6 PWM:7` |
| Slices 3 and 6 | 1 MHz, TOP 20000 | 1 MHz, TOP 65535 |
| Counter, outputs 3 and 5 | max 19996, median 9865 | p99 4877 and 4959, median 2460 and 2557 |
| Pad high, outputs 3 and 5 | 0.076, 0.075 | 0.302, 0.311 |
| Slice 1 during the tune | 1 MHz, 20001 us, B 0 | 1.5 MHz, 250.6 us, B 124.6 us |

So before, the elevons got 1500 us pulses at 50 Hz (`SERVO_RATE`), and
the buzzer had no drive. After, each slice counter is restarted at most
5.0 ms after the last, at the 200 Hz loop rate, and the pad is high 30% of
the time: 1500 us per 5 ms. The one 65535 sample on slice 6 is the counter
caught between the trigger's write and its wrap. Output 8 with function 0
is no longer in any group, and the buzzer has the slice.

After each flash every parameter read back the same, except those the
board updates at boot: `STAT_BOOTCNT`, `STAT_RUNTIME`, `BARO1_GND_PRESS`,
`INS_GYROFFS_*` and `INS_GYR1_CALTEMP`.

## At a 50 Hz main loop

At the owner's request `SCHED_LOOP_RATE` was then set to 50, Plane's
fixed-wing default, and left there for flying; nothing else changed,
compared parameter by parameter. Load fell from 13% to 6.6%. Outputs 3
and 5 restart at most 6.9 ms apart, p99 6.0 ms, high 29-30% of the time:
each push sends a pulse and `timer_tick()` resends the last width every
5.5-7 ms between pushes, as on STM32, far from the 65.5 ms wrap. The
buzzer kept its slice (`loop50.json`). The board was left on a600ccc8d7.

## Not checked

- Servo travel when the width changes; the elevons sat at trim. The pulses
  at 1500 us show the forced wrap latching CC, as the counter never reached
  its own wrap.
- DShot on output 1 with the ESC powered. With a oneshot group present,
  `set_dshot_rate()` takes its 1 kHz branch, as on STM32: DShot still goes
  out at each push, and between pushes 1 ms after the last send, rather
  than at four sends per 200 Hz loop. The 1 ms timer is a floor that keeps
  `timer_tick()` resending oneshot pulses when pushes are slow or stop.
- Pre-existing: the board's `flight.lua:17` asks for a parameter that does
  not exist, and pre-arm reports it.

## Follow-on

The OneShot trigger runs in the pushing thread, so a fast rate loop
pushing OneShot outputs waits for each pulse. That is upstream behaviour
on STM32 too, measured on the Copter test quad and fixed in #35410; see
`../35410/`.
