# Bench 2026-11-26: RPI_UAVFC outputs 5-10 and the buzzer's PWM slice

Board: the RPI_UAVFC on COM15, a DShot600 quad on USB power, running alpha2
Copter (031f2549) with `OSD_TYPE` 6. Firmware under test: Copter from
`rp2350-hwdef-cleanup` at 1bad3ce4 (fw6c). The case 3 rerun used that commit
plus the slice-restart fix, committed as c2e0e66c51 (fw7c). Afterwards the
board was flashed back to 031f2549, with the parameters as found.

Method: `buzz_bench.py`, kept with the case JSON files in
`data/2026-11-26-buzzer-outputs/`. Each case sets parameters and reboots.
It then collects the boot text and the banner (`MAV_CMD_DO_SEND_BANNER`) and
reads `SERVO_OUTPUT_RAW`. Over SWD, while the cores run, it reads the
IO_BANK0 FUNCSEL of GPIO2, 3, 5, 12-14 and 41 and the CSR/DIV/TOP/CC registers
of slices 1, 2, 6, 7 and 8. Last, it plays `MFT60L1O4CC` (`PLAY_TUNE`, 8 s)
and samples slice 1 and the GPIO2/3 function about 600 times a second.

| Case | Setup | Banner | Slice 1 during the tune | Result |
|---|---|---|---|---|
| c0 | as found after the update | `DS600:1-4 PWM:7` | 1.5 MHz, 250.6 us, B 124.6 us | buzzer keeps the slice |
| c1 | `OSD_TYPE` 0, `SERVO8_FUNCTION` 120 | `DS600:1-4 PWM:5-7 NeoP:8` | 1.5 MHz, 250.6 us, B 124.6 us | strip from PIO1 (GPIO2 FUNCSEL 7), buzzer 4 kHz |
| c2 | `SERVO8_FUNCTION` 0 | `DS600:1-4 PWM:5-8, buzzer off` | 1 MHz, 20001 us, B 0, unchanged on 4304 samples | `DO_SET_SERVO 8 1700` gives A 1700.0 us, still 1700 through a second tune |
| c3 | `SERVO8_FUNCTION` 94, script strip | `DS600:1-4 PWM:5-7 NeoP:8` | 1 MHz, 376.0 us, B 187.0 us | strip up, but the buzzer plays at 2.66 kHz |
| c3 fixed | same, fw7c | `DS600:1-4 PWM:5-7 NeoP:8` | 1.5 MHz, 250.6 us, B 124.6 us | buzzer 4 kHz |
| c4 | `BRD_ALT_CONFIG` 1, `SERVO8_FUNCTION` 120 | `DS600:1-4 PWM:5-7 NeoP:8 PWM:9-10` | 1.5 MHz, 250.6 us, B 124.6 us | GPIO5 and GPIO41 FUNCSEL 4; `DO_SET_SERVO` 9 1600 and 10 1400 give slice 2 B 1600.0 us and slice 8 B 1400.0 us |

Also, in the c4 boot without a reboot, `DO_SET_SERVO` 5/6/7 at 1100/1200/1300
gave slice 6 A 1100.0 us, B 1200.0 us and slice 7 A 1300.0 us. Without
`BRD_ALT_CONFIG` 1, GPIO5 and GPIO41 stay at FUNCSEL 31 (null), undriven.

## Findings

- Case 3 found a bug, now fixed. A script that sets up a strip on a
  scripting output gave the buzzer its slice back, but nothing restarted the
  slice, so it stayed on the servo group's 1 MHz clock. The tone code divides
  the alarm's 1.5 MHz by 4000, so every tone played at 2.66 kHz instead of
  the transducer's rated 4 kHz. `Util::toneAlarm_reclaim_pwm_slice()` now
  restarts the slice on the alarm's config, as `toneAlarm_init()` does when
  the strip is there at boot.
- A function-0 output sends no pulse. `SERVO_OUTPUT_RAW` shows 0 for
  outputs 5-10 until `DO_SET_SERVO`, and CC reads 0 to match. The comment in
  `SRV_Channels::enable_aux_servos()` says such outputs "get their initial
  trim value on startup"; on this board they do not. The RCOutput comment
  that said function 0 is driven at trim was wrong and is corrected.
- Update from alpha2: this board read `SERVO8_FUNCTION` 120, the new default,
  since its 0 on alpha2 was only the old default. `SERVO5_FUNCTION` kept a
  stored 120, so GP1 also had a NeoPixel function after the update.
- With `OSD_TYPE` 6 the PIO OSD owns PIO1 and no NeoPixel output can start,
  which is why c0 shows the LED pad left on PWM function.
- Pre-existing, not changed here: every slice runs TOP+1 counts, so 50 Hz
  outputs have a 20001 us period and the buzzer runs at 3.99 kHz.
- MAVFTP `ListDirectory` failed for every directory, even `@SYS`, through the
  pymavlink helper, while file get, put and remove worked. Not chased.
