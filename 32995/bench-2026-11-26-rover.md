# #32995 Rover on RPI_UAVFC, 2026-11-26: CPU without a rate thread

Andy asked for the same performance sweep on Rover as on Plane and
QuadPlane, since Rover is what people care about. The board is the
motorless RPI_UAVFC testbed on COM15 (UID `5227E0D3...`, AM32 ESCs, no
motors), which ran the alpha2 Copter build `031f2549`; the firmware is
Rover from the PR head `b9db33af08`, then the two commits below.

**Summary.** At Rover's own 50 Hz default core0 is 33-35% busy armed and
the port has room to spare. Rover has no rate thread, and its scheduler
runs `ahrs_update` and the mode update at the loop rate, so a raised
`SCHED_LOOP_RATE` loads core0 fast: 55-63% armed at 200 Hz and 74-90% at
400 Hz, with 62-70% of core0's busy time running from XIP flash. Placing
Rover's hot code in SRAM (`3715cf8ccd`, 255 functions, 29.9 KB) takes
armed core0 at 400 Hz from 74-89% to 50-64% and halves `ahrs_update`,
for 33.6 KB of free memory. At the 50 Hz default the same entries take
armed core0 from 33-35% to 28-30% and `ahrs_update` from 1.6 ms to 1.0 ms.
Taking Rover's GCS tasks down to the
board's 25 Hz, as Copter does, saves under 1.5 points and is left out.

## The Copter testbed's backup

Flashing another vehicle erases every parameter, as each vehicle has its
own `FORMAT_VERSION` (Copter's 1748 parameters were gone at Rover's first
boot, `STAT_BOOTCNT` 1). Before the upload, in
`~/rp2350-bench-backups/2026-11-26-testbed-copter/` (local, not in this
repository):

- `params-031f2549.parm` and `.json`: all 1748 parameters over MAVLink,
  the count checked against `PARAM_COUNT`
- `param-block-0x10010000.bin`: the 64 KB parameter storage block over SWD
- `flash-full-4MB.bin`: the whole 4 MB flash over SWD, bootloader,
  parameters and the `031f2549` app; each 64 KB read twice and compared
- `README.txt`: restore steps (the full image with OpenOCD `program ...
  0x10000000 verify reset`, or the parameter block alone on the same
  Copter firmware)

A single 4 MB `dump_image` failed partway ("Failed to read memory at
0x1001f858") while the firmware was running; the chunked reads matched
each other, and the parameter block matches the same range of the full
image.

## Setting up Rover on the testbed

Rover's defaults then took the board-level settings the Copter
parameters had carried, copied from the backup: `OSD_TYPE` 6 and its
options, `SERIAL4_PROTOCOL` 37 (SmartAudio) and `VTX_ENABLE`,
`SERIAL1_PROTOCOL` -1, `NTF_LED_TYPES`, `RC_OPTIONS`, `RSSI_TYPE`,
`MSP_OPTIONS`, `AHRS_ORIENTATION` 8, the battery current scaling, and the
compass calibration with its custom rotation (`COMPASS_ORIENT` 101,
`CUST_ROT1_PITCH` 30). The accelerometer calibration was not copied: the
Copter's has `INS_ACCOFFS_Z` -19.7, which does not look like a real
calibration, so "3D Accel calibration needed" stays a pre-arm failure and
every run arms forced.

Two things stood between EKF3 and a position on the bench. A wiped
compass calibration reads as "Compass not calibrated", so EKF3 has no yaw;
with the calibration back the board then fails "Check mag field (xy
diff:450>100)", sitting at 14 deg roll and 42 deg pitch on the bench, and
EKF3's GPS pre-flight checks held the fake fix off. `EK3_GPS_CHECK` 0 let
it in at once: "EKF3 IMU0 is using GPS", flags `0x33f`. The fix is
`GPS1_TYPE` 14 fed `GPS_INPUT` at 10 Hz (SITL's home, zero velocity, 16
satellites), as for Plane.

## Method

As for Plane (bench-2026-11-25-plane.md): 30,000 DWT PCSR samples per
core through OpenOCD without halting, XIP counters over 3 x 1 s,
`@SYS/threads.txt` and `@SYS/tasks.txt`, SYS_STATUS load, each condition
settled 10 s. RC overrides from system id 255 hold the sticks centred and
the throttle at `RC3_TRIM` 1500, which is Rover's stop. Conditions:
disarmed MANUAL, and armed MANUAL, ACRO, HOLD, LOITER and AUTO, at
`SCHED_LOOP_RATE` 50 (Rover's default), 200 and 400. AUTO runs a
three-item bench mission at the fake fix; with the vehicle stationary it
asks for full throttle (output 3 at 1900, steering swinging 1376-1624),
which on the motorless bench drives nothing.

## Results

Percent of core0 samples; xip% is the share of core0's busy samples that
ran from flash, rover the `Rover/` objects, AR_* the AR controllers and
motors, load the scheduler's own figure.

| rate, condition | core0 busy | xip% | rover | AR_* | EKF3 | core1 | load | XIP hit |
|---|---|---|---|---|---|---|---|---|
| 50, disarmed MANUAL | 28.9 | 48.6 | 0.56 | 0.22 | 2.17 | 19.9 | 11.0 | 92.4 |
| 50, MANUAL | 32.8 | 47.3 | 0.69 | 0.28 | 2.74 | 18.2 | 13.1 | 89.1 |
| 50, ACRO | 33.7 | 48.3 | 0.64 | 0.50 | 2.79 | 18.0 | 14.0 | 89.0 |
| 50, HOLD | 33.0 | 47.2 | 0.55 | 0.33 | 2.70 | 18.1 | 13.0 | 89.2 |
| 50, LOITER | 33.8 | 49.1 | 0.73 | 0.45 | 2.65 | 18.0 | 14.3 | 88.9 |
| 50, AUTO | 34.7 | 50.6 | 0.83 | 0.96 | 2.69 | 18.3 | 15.9 | 88.3 |
| 200, disarmed MANUAL | 45.2 | 59.2 | 1.49 | 0.84 | 4.72 | 21.7 | 29.6 | 87.7 |
| 200, MANUAL | 54.9 | 56.1 | 1.84 | 1.06 | 6.65 | 18.7 | 37.0 | 82.8 |
| 200, ACRO | 59.8 | 58.6 | 2.10 | 1.91 | 7.06 | 18.8 | 40.3 | 83.6 |
| 200, HOLD | 53.7 | 56.6 | 1.24 | 0.97 | 6.63 | 19.1 | 36.7 | 83.4 |
| 200, LOITER | 58.2 | 60.1 | 1.89 | 1.97 | 7.10 | 18.6 | 40.8 | 83.6 |
| 200, AUTO | 63.4 | 62.4 | 2.36 | 3.66 | 6.89 | 19.1 | 47.0 | 82.3 |
| 400, disarmed MANUAL | 58.7 | 62.7 | 2.36 | 1.64 | 6.66 | 22.0 | 40.4 | 84.9 |
| 400, MANUAL | 73.6 | 62.0 | 2.74 | 2.13 | 10.39 | 18.6 | 54.2 | 80.1 |
| 400, ACRO | 80.1 | 65.2 | 3.28 | 3.16 | 10.65 | 19.1 | 57.9 | 81.4 |
| 400, HOLD | 74.3 | 62.3 | 2.06 | 2.28 | 10.21 | 18.5 | 53.2 | 80.7 |
| 400, LOITER | 80.3 | 65.8 | 2.95 | 3.38 | 10.97 | 18.3 | 57.8 | 81.5 |
| 400, AUTO | 89.6 | 70.0 | 4.13 | 7.34 | 10.68 | 19.1 | 59.0 | 79.7 |

Core1 carries only SPI0 (the IMU), `rcout` and `OSD_c1`, 18-22% busy
whatever the rate. Core0 does everything else. `ahrs_update` is about
half the task time at every rate and the mode update a quarter at 200 and
400 Hz. At 50 Hz each `ahrs_update` call costs 1682 us against 1003 us at
400 Hz, the calls far enough apart that each starts with a colder cache.

At 400 Hz in AUTO, core0's hottest flash code is spread wide: EKF3 10.0%
of all samples from flash, AP_Math 5.5%, AHRS 4.0%, the AR controllers,
AR_WPNav and AC_Avoidance together about 8%, GCS 2.6%, with
`AR_PosControl::update`, `AC_Avoid::adjust_velocity_proximity`,
`__ieee754_rem_pio2f` and `GCS::update_sensor_status_flags` the largest
single functions at 0.7-1.0% each. No one path dominates, so the
placement takes everything Rover runs hot rather than a call tree.

## Rover's hot code in SRAM

`rover_pick.py` ranks every function still in flash by its mean share of
core0 over the ten armed profiles at 200 and 400 Hz, across every
ArduPilot library and vehicle directory (ChibiOS, libc and libm come
from shared archives a marker cannot limit). Kept: 0.03% of core0 or
more, or 0.015% at 1% per KB, and none below 0.3% per KB. That floor
mattered: 0.1% per KB would have taken 49.4 KB for 26.0% of core0, 0.3%
per KB takes 29.9 KB for 22.7%. 255 functions; 58 of them were already
Plane's EKF3 and AHRS entries, now `[arduplane,ardurover]`, and the other
197 are new `[ardurover]` lines. Laurel and Pico2 Rover build with every
entry found; RPI_UAVFC Copter and Plane keep `0a224befa8e2` and
`7626a88d4182` with `--consistent-builds`.

A/B, A the PR head, B with the entries, boots A B B A at 400 Hz with
EKF3 on the fake fix (`rover_ab.py`; the flash matched the ELF over SWD at
every boot):

| armed | core0 busy A | B | from flash A | B | load A | B | `ahrs_update` A | B |
|---|---|---|---|---|---|---|---|---|
| MANUAL | 74.1 | 49.9 | 46.0 | 17.3 | 52.8 | 32.4 | 941 | 474 |
| ACRO | 79.9 | 53.6 | 52.4 | 19.2 | 57.9 | 36.2 | 993 | 489 |
| AUTO | 89.3 | 64.3 | 62.4 | 28.8 | 60.3 | 47.7 | 1013 | 524 |

"From flash" here is percent of all core0 samples. Each pair of boots
agreed within a point. Free memory 182.3 KB to 148.7 KB.

The same A/B at Rover's default 50 Hz, A B B A:

| armed, 50 Hz | core0 busy A | B | from flash A | B | load A | B | `ahrs_update` A | B |
|---|---|---|---|---|---|---|---|---|
| MANUAL | 32.8 | 28.0 | 15.3 | 9.1 | 13.5 | 10.1 | 1604 | 1016 |
| ACRO | 33.4 | 28.2 | 16.3 | 9.0 | 14.3 | 10.5 | 1611 | 1024 |
| AUTO | 34.7 | 30.1 | 17.4 | 10.5 | 15.9 | 12.0 | 1625 | 1041 |

At 50 Hz core0 has room either way; what a user gains there is the EKF
and AHRS update taking about 0.6 ms less each loop. Committed as
`3715cf8ccd` on `rp2350-v5-squashed-and-cleaned-and-rebased`, not pushed
and not reviewed.

## Rover's GCS rate: measured and left out

Copter takes its GCS task rate from the HAL (`AP_GCS_UPDATE_RATE_HZ`, 25
on the RP2350 boards, from #32995's `e2ea1e87af`); Rover's table runs
`update_receive` and `update_send` at a fixed 400, which a raised loop
rate makes every loop. The same two-line change for Rover
(`tools/rover_profile/rover_gcs_rate.patch`) leaves MatekH743 Rover
byte-identical (`2a309db3e1ca` with `--consistent-builds`, with and
without), so it would change only the RP2350 boards.

A/B on top of `3715cf8ccd`, boots A B B A at 400 Hz, B with the patch:

| armed | core0 busy A | B | load A | B |
|---|---|---|---|---|
| MANUAL | 49.6 | 49.1 | 34.9 | 29.3 |
| ACRO | 53.9 | 52.5 | 38.2 | 33.0 |
| AUTO | 63.5 | 62.7 | 48.9 | 43.4 |

The scheduler's load falls 5.5 points but core0 hardly moves: at 25 Hz
the GCS does the same work in larger calls (`update_send` 692 us a call
against 58 us; about 17 ms a second against 23 ms). Under 1.5 points of
core0 does not pay for capping Rover's MAVLink receive and streams at
25 Hz, so it is not committed.

## The registry scripts and the program markers

Two scripts read the registries, and neither knew the program markers
well enough to be trusted with them:

- `rp2350_ramfunc2_update.py`, which repairs entries after a rebase, ran
  the generator with `--strict` and no `--program`. A marked entry was
  never checked, so a Rover build that failed on one got no plan, and
  `--vehicle rover` instead reported dozens of Copter-only entries as
  missing ("removed upstream in ... Sub: Refactor ..."). What replaced an
  entry was written unmarked, which would have put a Plane or Rover name
  into Copter's strict check, and the run rewrote the build's own section
  lists.
- `rp2350_ramfunc2_sizes.py --update` kept only `[needs]`-style markers
  and `[inlinable]`: against the Rover ELF it would have stripped 288 of
  the 425 program markers, and it counted 10.2 KB of Plane-only entries
  as "in flash".

`af935a65c2` fixes both, and `46d1e21896` makes the generator's repair
hint ask for `--vehicle`. Tested in a scratch worktree with a commit that
renamed `AP_MotorsUGV::output_regular` (`[ardurover]`) and
`EKFGSF_yaw::predictAHRS` (`[arduplane,ardurover]`): the Rover build
failed on both, and `--vehicle rover --build` placed the renamed
functions under those markers, one plan per set of programs, and linked.
Copter, Plane and Rover then built, verified and planned clean, the
build's section lists unchanged by the plan. The annotator keeps all 425
markers and leaves Plane-only lines alone against a Rover ELF. A first
test renamed by appending a suffix, which the script's `git log -S`
cannot see, as the old name is still a substring; that limit predates
the markers.

Then, at Andy's request, two more:

- `rp2350_pc_profiler.py` read everything after the `|` as the name, size
  comment included, so of the registry's 965 entries only the 231 without
  a comment could ever match, and its report suggested functions already
  placed. `3ec670ca66` takes the name as the generator does and reads the
  markers: against the PR-head Rover ELF it now knows 766 Rover functions
  as registered, against the build with the Rover entries none of them in
  flash, as `--verify` says.
- `--rp2350-relocate` (`58e288dfac`, with `6f6ce1a495` letting the script
  take the program as waf names it): when the placement step stops on a
  miss, the build runs the script with `--apply` for each program being
  linked, generates the placement again and links. With the same test
  rename, `./waf copter plane rover --rp2350-relocate` repaired the Plane
  and Rover misses in their own builds and linked all three, a single
  `--targets bin/arduplane,bin/ardurover` build repaired both at once, and
  every registered function was then in SRAM in each. A Scratch bank
  overflow fails at the link, after that step, so it still needs the
  script's `--build`. `14f61e9355` points the generator's hint and
  DEVELOPMENT.md at the option. At `14f61e9355` MatekH743 Copter is still
`f1db94851b64` and RPI_UAVFC Copter and Plane `0a224befa8e2` and
`7626a88d4182` with `--consistent-builds`.

## Board state afterwards

The testbed ran Rover `3715cf8c` (the code measured as B; the uploader
verified it), disarmed, `SCHED_LOOP_RATE` 50, `GPS1_TYPE` 1 and
`EK3_GPS_CHECK` 31 restored, the bench mission cleared. The settings
copied from the Copter parameters stayed, with the accelerometer
uncalibrated. OpenOCD shut down with `C_DEBUGEN` cleared on both cores,
and the COM15 bridge stopped.

Then, at Andy's request, the testbed went back to Copter: the backed-up
4 MB image programmed at `0x10000000` over SWD in 30 s ("Verified OK").
`reset run` through OpenOCD left core1 in the boot ROM at `0x19c` while
core0 ran the app, as DEVELOPMENT.md warns; `cold_reset` brought both
up in the app. It reports ArduCopter `031f2549`, `STAT_BOOTCNT` 178
(177 at the backup), and all 1748 parameters match the backup but for
those every boot rewrites: `BARO1_GND_PRESS`, the boot gyro offsets and
their temperature, `STAT_BOOTCNT` and `STAT_RUNTIME`.

In AUTO on a stationary fix Rover asks for full throttle: output 3 sat at
1900 us throughout. Harmless on this motorless bench, but the AUTO
condition needs `SERVO3_LIMIT` set in `rover_session.py`, or no motor
power, on any board with motors fitted.

## Reproduce

Tools in `tools/rover_profile/` (self-contained; TCP 5771). Start
`bridge.py COM15 127.0.0.1 5771` with Windows Python and OpenOCD as in
README.md, then:

```sh
python rover_profile/param_dump.py <backup dir>/params       # before flashing another vehicle
python rover_profile/ekfcheck.py 90                         # GPS1_TYPE 14, EK3_GPS_CHECK 0
python rover_profile/mission.py upload -35.3632621 149.1652374
FAKE_GPS=1 EKF_WAIT=120 python rover_profile/rover_session.py <out> dis_man:disarmed:0:30000 \
    arm_man:armed:0:30000 arm_acro:armed:1:30000 arm_hold:armed:4:30000 \
    arm_loiter:armed:5:30000 arm_auto:armed:10:30000
python3 rover_profile/rover_summary.py <ardurover ELF> <map> <out>...
python3 rover_profile/libgroup.py <ELF> <map> <ardupilot checkout> <out>/arm_auto_c0.txt --top 40
python3 rover_profile/rover_pick.py <ELF> <map> <ardupilot checkout> ALL "<ELF>:<map>:<out>/arm_*_c0.txt"...
python3 rover_profile/rover_ab.py ABBA <dir with A/ and B/> <out>
python3 rover_profile/rover_abana.py <dir with A/ and B/> <out>
```

`rover_pick.py` takes `MIN_PCT`, `MIN_DENSE_PCT`, `DENSE_PER_KB` and
`MIN_PER_KB` (0.3 here) from the environment. `rover_ab.py` flashes the
testbed, so it is for a disarmed bench; it stops only its own bridge and
OpenOCD before each upload.
