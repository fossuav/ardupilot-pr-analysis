# #32995 Plane on RPI_UAVFC, 2026-11-25: CPU without a rate thread

First look at ArduPlane on the RP2350 port, which has no fast rate
thread. Andy's flying wing on the bench (RPI_UAVFC on COM32, picoprobe on
COM10): throttle on output 1 as bidirectional DShot600, elevons on outputs
3 and 4, `INS_HNTCH_ENABLE` 0, `OSD_TYPE` 5, `LOG_BITMASK` 65535,
`SCR_ENABLE` 0. The motor never ran: RC overrides held channel 3 at
`RC3_MIN` (1100, zero throttle) throughout, with a cap of 1180 in the
script.

Firmware: ArduPlane V4.8.0-dev `5e97be25`, the PR head `5e97be2505` built
without `--enable-stats` (configured 2026-11-25 13:30). The flash matched
the ELF at seven regions over SWD before measuring.

**Summary.** With no rate thread, Plane runs everything that matters on
core0, and core1 sits at 15-18% busy in every condition: the IMU bus
thread, `rcout`, the `OSD_c1` thread and kernel. At 200 Hz with EKF3
running, armed FBWA leaves core0 56% busy and the scheduler at 37-40%
load, with no long loops. At 400 Hz the same case reaches 79% of core0,
six long loops in 70 s (worst 3.87 ms against 2.5 ms) and the scheduler
deferring tasks (`PM.Ex` up to 200 us) - at its limit before navigation,
TECS, an airspeed sensor or scripting are added. Two thirds of core0's
busy time is fetched from XIP flash; the SRAM registries are tuned for
Copter and hold none of Plane's own path.

At Plane's own default of 50 Hz, measured later the same day, armed FBWA
with EKF3 leaves core0 35.5% busy and the scheduler at 16%, with no long
loops. About 32% of core0 is busy even disarmed at 50 Hz: threads,
interrupts and kernel outside the main loop's tasks.

**Where the day ended.** Three placement rounds, each an A B B A test
on the flight board at 200 Hz with EKF3 and committed on its own:
Plane's per-loop path (14.4 KB) took armed FBWA from 57.6% to 51.3% of
core0, its navigation path (4.6 KB) about half a point more in CRUISE
and LOITER, and its EKF3 and AHRS (17.3 KB) 52.0% to 45.8% in FBWA and
52.2% to 45.9% in AUTO. Chained across rounds, which were separate
boots, FBWA went from about 57.6% to 45.8% and free memory from 174 KB
to 134.5 KB. All of it is `[only arduplane]`; RPI_UAVFC Copter is
byte-identical. QuadPlane's multirotor code stays in SRAM in Plane builds
by Andy's decision.

**Both rates are well above Plane's own default.** Plane's compiled
`SCHED_LOOP_RATE` default is 50 Hz (`AP_Scheduler.cpp` 43-47; QuadPlane
raises its own default to 300, `ArduPlane/Parameters.cpp` 1354). The 200
came from `RPI_UAVFC/defaults.parm`, which set it for every vehicle on
Copter's reasoning (the rate thread carries the fast path, so the main
loop can drop from 400); Laurel and Pico2 carry the same line. On Plane
it raised the rate fourfold. 50 Hz was measured afterwards; 100 Hz was
not. See "The loop rate default" below for the change that lowers only
Copter's default.

## Method

As in the 2026-11-20 scripting profile: 30,000 DWT PCSR samples per core,
alternating cores through OpenOCD's TCL port without halting (about
1,300 a second per core, 22-25 s per condition), XIP CTR_HIT/CTR_ACC over
3 x 1 s, `@SYS/tasks.txt` and SYS_STATUS load over the same window, and
PM from the dataflash log of each armed run. Busy is every sample outside
the idle threads. Each condition settled 10 s first.

Conditions: disarmed MANUAL, armed MANUAL, armed FBWA (sticks centred),
each at `SCHED_LOOP_RATE` 200 and 400, and later at 50 with EKF3 only.

EKF3 does not initialise on a plane without a 3D fix
(`AP_NavEKF3_core.cpp` 469, "If we are a plane and don't have GPS lock
then don't initialise"), and the bench has none indoors. The first two
sets therefore ran on DCM with EKF3 retrying its start: XKF4 in log 1
reads `SS` 0 and `FS` 128 throughout, and `NavEKF3::InitialiseFilter`
shows in the samples. The second two sets used a stationary fake fix,
`GPS1_TYPE` 14 fed `GPS_INPUT` at 10 Hz (SITL's default home, zero
velocity, 16 satellites), as for Copter on 2026-09-19: EKF3 initialised,
aligned yaw on the compass and used GPS within about 15 s.

## Results

| Run | core0 busy | of it in XIP | EKF3 code | FW controllers | core1 busy | sched load | XIP hit | XIP misses |
|---|---|---|---|---|---|---|---|---|
| 200 Hz DCM, disarmed | 40.8% | 57.6% | 1.32% | 0.24% | 17.7% | 19.8% | 87.7% | 0.88 M/s |
| 200 Hz DCM, armed MANUAL | 42.5% | 55.3% | 1.69% | 0.26% | 15.2% | 21.5% | 84.2% | 0.92 M/s |
| 200 Hz DCM, armed FBWA | 48.5% | 60.4% | 1.93% | 1.77% | 15.6% | 27.1% | 82.8% | 1.14 M/s |
| 200 Hz EKF3, disarmed | 48.9% | 62.5% | 4.71% | 0.30% | 18.2% | 30.1% | 86.9% | 1.15 M/s |
| 200 Hz EKF3, armed MANUAL | 52.7% | 62.4% | 5.02% | 0.35% | 15.4% | 31.6% | 83.7% | 1.25 M/s |
| 200 Hz EKF3, armed FBWA | 56.4% | 64.7% | 4.66% | 1.81% | 15.5% | 36.9% | 82.6% | 1.46 M/s |
| 400 Hz DCM, disarmed | 56.4% | 62.3% | 2.59% | 0.49% | 18.3% | 36.0% | 85.2% | 1.34 M/s |
| 400 Hz DCM, armed MANUAL | 58.0% | 61.0% | 3.14% | 0.51% | 15.7% | 38.7% | 82.3% | 1.38 M/s |
| 400 Hz DCM, armed FBWA | 68.7% | 66.4% | 3.63% | 3.29% | 15.2% | 49.9% | 80.4% | 1.82 M/s |
| 400 Hz EKF3, disarmed | 66.5% | 66.2% | 6.45% | 0.64% | 18.7% | 46.3% | 84.1% | 1.72 M/s |
| 400 Hz EKF3, armed MANUAL | 69.9% | 65.5% | 6.99% | 0.65% | 15.4% | 48.5% | 81.3% | 1.83 M/s |
| 400 Hz EKF3, armed FBWA | 79.3% | 70.0% | 6.99% | 3.63% | 15.9% | 58.7% | 80.1% | 2.23 M/s |
| 50 Hz EKF3, disarmed | 31.9% | 51.4% | 2.16% | 0.06% | 17.6% | 13.3% | 92.0% | 0.54 M/s |
| 50 Hz EKF3, armed MANUAL | 34.4% | 52.4% | 2.26% | 0.08% | 15.5% | 14.5% | 88.8% | 0.65 M/s |
| 50 Hz EKF3, armed FBWA | 35.5% | 54.1% | 2.26% | 0.56% | 15.5% | 16.2% | 88.3% | 0.70 M/s |

EKF3 and FW controller columns are shares of all core0 samples
(`AP_NavEKF3` objects; `AP_FW_Controller` and the roll, pitch and yaw
controllers). In the DCM runs the EKF3 share is its failed starts.
Sched load is the SYS_STATUS mean over the window.

Loop timing from PM, armed, dropping the window that holds the arming
or mode change:

| Rate, AHRS, mode | PM rows | long loops | MaxT | PM load | rows with Ex > 0 |
|---|---|---|---|---|---|
| 50 EKF3 MANUAL | 11 | 0 | 20.01-20.06 ms | 14.5-14.8% | 0 |
| 50 EKF3 FBWA | 15 | 0 | 20.01-20.06 ms | 15.8-16.8% | 0 |
| 200 DCM MANUAL | 9 | 0 | 5.02-5.05 ms | 22.2-23.0% | 0 |
| 200 DCM FBWA | 14 | 0 | 5.02-5.19 ms | 27.9-28.8% | 0 |
| 200 EKF3 MANUAL | 11 | 0 | 5.02-5.06 ms | 32.2-33.5% | 0 |
| 200 EKF3 FBWA | 15 | 0 | 5.01-5.12 ms | 36.9-40.1% | 0 |
| 400 DCM MANUAL | 12 | 0 | 2.52-2.99 ms | 37.4-39.5% | 0 |
| 400 DCM FBWA | 15 | 3 | 2.64-3.88 ms | 48.8-51.7% | 0 |
| 400 EKF3 MANUAL | 12 | 1 | 2.53-3.35 ms | 48.2-51.1% | 0 |
| 400 EKF3 FBWA | 14 | 6 | 2.82-3.87 ms | 52.3-62.4% | 5 (max 200 us), LR 399 |

`Ex` is the time the scheduler adds to each loop after a task could not
run within its budget (`AP_Scheduler.cpp` 406-420), so a non-zero value
means tasks are being deferred. No log data was dropped in any run
(`DSF.Dp` 0).

Per-call cost of the FAST tasks in armed FBWA, from `tasks.txt`, average
and maximum:

| | 50 EKF3 | 200 DCM | 200 EKF3 | 400 DCM | 400 EKF3 |
|---|---|---|---|---|---|
| `Plane::ahrs_update` | 1236 / 1863 us | 486 / 625 us | 861 / 1834 us | 477 / 643 us | 717 / 1706 us |
| `Plane::stabilize` | 265 / 323 us | 258 / 329 us | 287 / 393 us | 251 / 322 us | 259 / 342 us |
| `Plane::set_servos` | 180 / 319 us | 168 / 233 us | 181 / 275 us | 162 / 253 us | 166 / 231 us |
| FAST tasks, average, of the period | 9% | 19% | 28% | 38% | 48% |
| FAST tasks, sum of maxima, of the period | 13% | 26% | 53% | 53% | 96% |

- The FAST tasks cost the same per call at either rate, so doubling the
  loop rate doubles their share. `ahrs_update` is dearer per call at
  lower rates with EKF3 because the 100 Hz prediction falls on every
  loop at 50 Hz, every other loop at 200 Hz and every fourth at 400 Hz.
- At 50 Hz, `GCS::update_send` (664 us average) and `update_logging25`
  (521 us) take 28% of the scheduler's time between them and overrun
  their declared budgets; these are task overruns, not long loops.
- `Plane::stabilize` goes from 33 us in MANUAL to 258 us in FBWA at 200 Hz:
  the fixed-wing attitude controllers. Their profile is flat, dozens of
  small `Plane::` and `APM_Control` functions all in XIP flash, with no
  double-precision soft float to speak of (`__muldf3` 0.05%). That reads
  as XIP-miss bound rather than arithmetic; derived from the profile, not
  A/B tested.
- `ahrs_update` without EKF3 is about 480 us a call, which is DCM, the
  INS update and EKF3's failed starts.
- Logging and GCS: `update_logging25` costs 457-543 us a call when armed
  and overruns, and `GCS::update_send` reaches 1.0-1.16 ms with overruns
  at both rates.
- The ChibiOS kernel is 9.6-11.6% of all core0 samples in every
  condition (context switches, virtual timers, locks, the USB interrupt
  `Vector78` and `sduSOFHookI` about 0.7%).

## What it means for the port

These are bench figures on a stationary aircraft: no navigation mode,
TECS or L1 controller, no airspeed sensor in use (`ARSPD_USE` 0), a
10 Hz fake GPS that never moves, and no scripting. Flight adds to all of
them.

- 50 Hz, Plane's default, leaves core0 at 35.5% and the scheduler at
  16%. 200 Hz holds with room: core0 at 56% and no long loops in the
  heaviest bench case. 400 Hz does not, once EKF3 runs.
- Setting the rate to 400 and back left `SCHED_LOOP_RATE` 200, and
  likewise `GPS1_TYPE` 1, stored on the flight board: AP_Param rewrites
  an existing entry even when the value equals the default
  (`AP_Param.cpp` 1208). A change to the board default will not reach
  this board until the parameter is reset.
- Core1 is 82-85% idle under Plane. The Copter split (rate loop on
  core1) has no Plane equivalent, so either Plane work moves there or
  core0's work gets cheaper.
- Core0 spends two thirds of its busy time fetching from XIP flash, at
  80-87% hit rates. The registries hold none of `ArduPlane/*`,
  `APM_Control`, `AP_TECS` or `AP_L1_Control`, and most EKF3 control,
  output and fusion functions are in flash (`CovariancePrediction` and
  `calcOutputStates` are in SRAM). The RAMFUNC2 check is strict only for
  Copter, so Plane builds skip the registry's Copter-only entries
  silently. A Plane placement pass from these profiles is the cheapest
  lever; not measured. Measured later the same day: see "Plane's
  per-loop path in SRAM" below.
- Moving core0 threads to core1 through `AP_THREAD_CORE_TABLE` (`log_io`,
  `FTP`, `I2C0`/`I2C1`, `OSD`) is a per-board table today, and the Copter
  table keeps them on core0 on purpose. A per-vehicle choice would need
  a mechanism that keeps vehicle tests out of the HAL. Not tried.

## Other findings

- "AP_Logger: stuck thread ()" on the first arming after the flash
  (boot 13), with `last_io_operation` empty; no STATUSTEXT for it on
  the first armings of boots 14, 15 and 16. No data was lost. This may be the
  first `f_getfree()` walk landing outside initialisation, open in
  README.md since 2026-09; not pinned.
- At arming the 80 KB log buffer went down to 3 KB free at 400 Hz with
  EKF3 (`DSF.FMn` 3090), 13 KB at 400 Hz on DCM, and 44-48 KB at 200 Hz,
  with `LOG_BITMASK` 65535.
- `threads.txt` per-core LOAD is not usable on this build. Core1 read
  12.2% at every read whatever it was doing (PCSR: 15-18%), and some
  reads repeated the previous read exactly. `Util::thread_info()` calls
  `sysStopLoadMeasure()` then `sysStartLoadMeasure()`; the start is
  skipped while the stop is still pending, so the measurement stops
  after one read and restarts at the next (derived from the source, not
  measured). The PCSR figures above do not depend on it.
- Core1's idle-load `__udivmoddi4` from flash is 1.3% of core1 disarmed,
  as on Copter.
- Disarmed scheduler load read 25.5% for the first minute after a boot,
  and 19.9% once settled, the same as before the session.

## The loop rate default

At Andy's request (option 2 of three offered), Copter's default is now
lowered by a board define rather than `defaults.parm`, so other vehicles
keep their own. Committed on `rp2350-v5-squashed-and-cleaned-and-rebased`
on top of `5e97be2505` as `88704a865c` (AP_Scheduler), `2e6a62251b`
(hwdef) and `1411b17f5b` (DEVELOPMENT.md); not pushed:

- `AP_Scheduler.cpp`: `AP_SCHEDULER_COPTER_DEFAULT_LOOP_RATE_HZ`
  (400 unless a board sets it) for Copter and Heli builds; Sub keeps its
  own 400 in a separate branch, everything else 50 as before.
- RPI_UAVFC and Laurel: `define AP_SCHEDULER_COPTER_DEFAULT_LOOP_RATE_HZ
  200` in `hwdef.dat`, with the reasoning moved from `defaults.parm`,
  whose `SCHED_LOOP_RATE 200` lines go. Pico2 keeps its line: it is
  there to match `SIM_RATE_HZ 200` for any vehicle.
- `rp2350/DEVELOPMENT.md`: the three places that stated the 200.

Checked on the built firmware, decoding `AP_Scheduler::var_info[1]` from
each ELF (`plane_profile/loop_default.py`) and reading each board's
`processed_defaults.parm`: RPI_UAVFC and Laurel Copter default to 200 and
RPI_UAVFC Plane to 50, with no `SCHED_LOOP_RATE` in either board's ROMFS
defaults. All three build with no warnings. MatekH743 copter with
`--consistent-builds` gives `arducopter.bin` sha256 `f1db94851b64`, the
PR tip's value, so STM32 output is unchanged.

On these two boards Sub's default goes from 200 (the old `defaults.parm`)
to its own 400, and Rover, Tracker and Blimp from 200 to 50; none of
them is run on RP2350.

The flight board was not reflashed: the 50 Hz numbers above are
`5e97be25` with `SCHED_LOOP_RATE` 50 set, the same code as the new
build with its new default.

## Plane's per-loop path in SRAM

At Andy's request, a sweep of Plane's hot paths into SRAM, on
`1411b17f5b`. Committed as `06c2529e91` (the marker), `7b5393edc0` (waf)
and `29e77d95b8` (the entries); not pushed.

Selection (`sweep.py`, `pick_entries.py`). A static call graph of the
Plane ELF from the FAST tasks and the 50 Hz control tasks, kept to code
only Plane links (ArduPlane, APM_Control, AP_TECS, AP_L1_Control,
AP_Landing, AP_Soaring), plus the Plane-only functions the profiles show
hot but the graph cannot reach (mode objects, the 1 kHz
`failsafe_check` timer callback). Ranked by mean share of core0 samples
over the four armed FBWA profiles at 200 and 400 Hz: 0.03% of core0 or
more, or 0.015% at 1% per KB, and rejecting any name, as the registry
matches it, that the Copter ELF also defines (`AP_GPS::status`,
`AP_Scheduler::get_loop_period_s`, `failsafe_check_static`) and five
large cold functions (`Tailsitter::output`, `QuadPlane::setup` ...).
84 functions, 14.4 KB, 9.8% of core0 of the 11.1% Plane-only flash code
took. Shared libraries Plane also runs hot (EKF3, AHRS, GCS) are left
alone: moving them moves Copter's code too.

The change:

- `rp2350_ramfunc2_sections.sh`: an `[only <program>]` marker and a
  `--program` option. A marked entry is placed, and its miss is fatal,
  only when its program is named; otherwise it is skipped. The program
  rides in the sort key's condition field after an `@`, so unmarked
  entries print and sort exactly as before and the SRAM layout of other
  builds cannot move.
- `Tools/ardupilotwaf/chibios.py`: `--program` for each program linked
  for hardware.
- The RAMFUNC2 registry: the marker documented, and the 84 entries as
  `[only arduplane]`, the header-defined ones also `[inlinable]`.
- `rp2350/DEVELOPMENT.md`: the marker in the registry rules.

Checked: RPI_UAVFC and Laurel Plane build with no warnings, the strict
Plane check passing on both; `rp2350_ramfunc2_update.py --verify
--vehicle plane` finds every registered function in SRAM. RPI_UAVFC
copter with `--consistent-builds` gives `arducopter.bin` sha256
`0a224befa8e2` before and after, with Plane objects in the build
directory, and its generated fragment has no Plane picks. flake8 is
clean on `chibios.py`. The Plane build's SRAM code grows by 16,576 B:
the 14.4 KB and 146 more veneers (651 to 797).

A/B on the flight board (`ab.py`, `abana.py`): A is `1411b17f5b`, B the
same plus the change; both identify as `1411b17f`, and each boot's flash
was checked against its own image over SWD. Boots A B B A, flashed over
COM32, `SCHED_LOOP_RATE` 200, the fake GPS with EKF3 running, armed at
zero throttle, 30,000 PC samples per core per condition, each boot's
samples attributed with its own ELF and map:

| Armed FBWA, 200 Hz | A (2 boots) | B (2 boots) | B - A |
|---|---|---|---|
| core0 busy | 57.6% (57.0-58.3) | 51.3% (51.0-51.5) | -6.4 points |
| Plane-only code, of core0 | 8.00% (7.84-8.17) | 2.02% (1.98-2.05) | -6.0 points |
| scheduler load | 35.3% (35.1-35.5) | 28.7% (28.7-28.7) | -6.6 points |
| XIP hit rate | 82.7% (82.5-82.9) | 84.9% (84.7-85.1) | +2.2 points |
| FAST tasks per loop | 1353 us | 1044 us | -23% |
| `Plane::stabilize` | 264 us | 109 us | -59% |
| `Plane::set_servos` | 170 us | 87 us | -49% |
| `Plane::update_control_mode` | 59 us | 21 us | -64% |
| `Plane::ahrs_update` | 861 us | 828 us | -33 us |
| MEMINFO free | 174,332 B | 157,756 B | -16,576 B |

In armed MANUAL core0 went from 52.3% to 49.6% and the FAST tasks from
1075 us to 962 us. Core1 stayed at 15.2-15.6% throughout. The A and B
boots do not overlap on any row.

- Core0 fell by about what Plane's own code lost (6.4 against 6.0
  points), so its time in flash was nearly all fetch stall. The rest of
  the fall, `ahrs_update` included, is the cache: the hit rate rose
  2.2 points with Plane's code out of it (derived from the numbers, not
  separated by a test).
- What is left of Plane in flash is 1.1% of core0 armed in FBWA.
- Not exercised: navigation modes (TECS, L1, AUTO), whose 10-50 Hz
  tasks the selection covered only where the FBWA profiles reached them.
- `AC_PID` sits in Scratch Y, core1's bank, by the Copter design, and
  Plane's fixed-wing controllers call it from core0. Not measured; the
  DEVELOPMENT.md rule says a core0 caller of Scratch Y does worse than
  main SRAM.

## Navigation modes

At Andy's request, the same sweep for FBWB, CRUISE, LOITER and AUTO, on
`29e77d95b8` (the per-loop path already in SRAM). Committed as
`373c878559`; not pushed.

Safety on the bench. These are auto-throttle modes, and the flight
board has `TKOFF_THR_MINACC` and `TKOFF_THR_MINSPD` at 0, with which an
AUTO takeoff check passes with no launch. For these runs `SERVO1_MAX`
was set to `SERVO1_MIN` (1000): `SRV_Channel::pwm_from_range()` returns
the minimum when the maximum is not above it, so every throttle demand
went out as 1000 us, DShot stop, with the throttle function still
assigned and TECS on its normal path. Plane writes the throttle PWM
directly only as zero. `session.py` also force-disarmed if
`SERVO_OUTPUT_RAW` ever showed servo 1 above 1000; it never did. AUTO
flew a mission of two waypoints 500-600 m from home at 100 m with no
takeoff item, uploaded for the test and cleared afterwards.

On `29e77d95b8`, scheduler load was 29.4% in FBWB and CRUISE, 30.0% in
LOITER and 31.9% in AUTO, against 28.7% in FBWA. The navigation code
itself is cheap at these rates: `update_speed_height` (TECS) about
50 us at 50 Hz, 0.26% of core0, and `navigate` 31-134 us at 10 Hz, at
most 0.13%. Plane-only code left in flash was 1.64% of core0 across the
four modes. `ahrs_update` is 110 us dearer per loop in AUTO than in
FBWB; the extra is spread over DCM, EKF3 control, the compass, the GSF,
terrain grid lookups and L1, no source file above 0.2% of core0, so it
is not a placement target.

Selection as before, with lower thresholds because the remainder is
thin: 0.01% of core0, or 0.005% at 0.3% per KB. 51 functions, 4.6 KB,
covering 0.97% of core0: TECS `_update_speed` and `update_50hz`, the L1
and mode updates, the navigation roll, pitch and throttle and the
controller getters. 0.03% would have taken 9 functions (2.3 KB, 0.40%)
and 0.015% 28 (3.9 KB, 0.77%).

`--verify` found one entry still in flash: GCC had folded
`ModeAuto::does_auto_throttle` into `ModeAuto::does_auto_navigation` as
an alias, so the first name has no section of its own, the generator's
pick matched nothing, and the strict check, which tests that the symbol
exists, did not notice. The registry names the section's owner instead.
Every registered function is then in SRAM. RPI_UAVFC copter with
`--consistent-builds` is still `0a224befa8e2` (taken before that
one-line fix, which changes only an `[only arduplane]` entry).

A/B, A `29e77d95b8`, B the same plus the 51 entries, boots A B B A,
200 Hz, EKF3 and the fake GPS, armed at zero throttle as above:

| | CRUISE A / B | LOITER A / B | AUTO A / B |
|---|---|---|---|
| core0 busy | 52.5 / 52.0% | 52.5 / 52.0% | 51.5 / 51.6% |
| Plane-only code, of core0 | 2.59 / 1.69% | 2.63 / 1.66% | 2.69 / 1.71% |
| scheduler load | 30.0 / 29.4% | 29.9 / 29.3% | 30.0 / 29.6% |
| FAST tasks per loop | 1067 / 1029 us | 1062 / 1026 us | 1062 / 1021 us |
| `update_speed_height` | 50 / 25 us | 52 / 24 us | 53 / 25 us |
| `update_control_mode` | 28 / 16 us | 34 / 17 us | 33 / 15 us |
| MEMINFO free | 157,764 / 152,836 B | 157,756 / 152,828 B | 157,756 / 152,828 B |

Core0 busy and scheduler load do not overlap between A and B in CRUISE
and LOITER; in AUTO, core0 busy overlaps and the scheduler load ranges
touch. `navigate` in AUTO stayed at 124 us: the mission and L1 waypoint
code was not hot enough to be picked. Against the per-loop path's 6.4
points of core0 for 16.6 KB, this set buys about half a point for
4.9 KB.

## Registry entries a Plane build does not need

Andy asked which of the shared registry entries only Copter uses, so a
Plane build could stop placing them (`[only arducopter]`: a Copter build
still places them, and the entry sorts as before, so Copter's picks are
unchanged) and spend the SRAM on EKF3 and AHRS instead.

`copter_only.py` classes each entry of the three registries against the
Plane ELF of `373c878559`, using every Plane profile of the day
(2,313,479 PC samples, both cores, disarmed to AUTO, each attributed
with its own build) and the Plane ELF's direct calls and function
addresses held anywhere, literal pools in code included:

| Registry | not in Plane | Plane runs it | reachable, never sampled | multirotor only |
|---|---|---|---|---|
| RAMFUNC2 (679) | 56 | 520, 90,388 B | 66, 12,428 B | 37, 6,182 B |
| Scratch X (14) | 0 | 8, 1,424 B | 2, 36 B | 4, 1,764 B |
| Scratch Y (15) | 0 | 12, 2,870 B | 2, 402 B | 1, 416 B |

- Not in Plane: ArduCopter itself, the rate thread's INS functions and
  some ChibiOS code. They cost a Plane build nothing already.
- Multirotor only: 42 entries, 8,362 B, all `AC_AttitudeControl`,
  `AP_Motors` and `Thrust_Linearization`; never sampled, and every caller
  chain ends in QuadPlane, tailsitter or tiltrotor code or those
  libraries. Within Plane these are QuadPlane's, which runs them every
  loop in VTOL modes at its 300 Hz default, so taking them out of a
  Plane build trades QuadPlane speed for fixed-wing SRAM. They include
  all four Scratch X entries, 1,764 B of core0's 3,808 B bank.
- Reachable but never sampled: configuration-dependent, not unused.
  The largest is `NavEKF3_core::FuseMagnetometer` (4,212 B), which Plane
  uses in flight once EKF3 fuses the full field; on a stationary bench
  it fuses yaw only. Others are the PIO OSD thread, harmonic notch
  updates (`INS_HNTCH_ENABLE` 0 here) and `powf`. Keep.
- A first pass that read function addresses from data sections only
  called ten entries unreferenced; thread entries, functors and
  callbacks take their addresses from literal pools in code, and with
  those scanned none is.

Decision, Andy, 2026-11-25: the multirotor entries stay. QuadPlane is
out of scope for now, but it is not to be broken deliberately, and with
fixed-wing Plane at its limit at 400 Hz, QuadPlane at 300 Hz running
its attitude control and mixing from flash would likely fall behind.
EKF3 and AHRS placements are to be additions only, paid from free heap.

Shared code left in flash on `373c878559`, armed in AUTO and CRUISE at
200 Hz: `AP_NavEKF3` 4.4-4.5% of core0, `AP_Math` 2.3-2.4%, GCS
2.2-2.3%, `AP_AHRS` 1.9-2.0%, `AP_Logger` 1.0-1.1% and `AP_Common`
(`Location`) 1.1%.

## EKF3 and AHRS for Plane

At Andy's request, placements for the EKF3 and AHRS code Plane runs, as
`[only arduplane]` so that Copter is not touched until it has its own
A/B. Committed on `373c878559` as `20e3226232` (the qualified picks),
`04361430a2` (waf) and `f4c65bc4f1` (the entries); not pushed.

Shared code made the marker's limit matter. One generator run serves
every program a waf run links, and they share the generated section
lists, so a plain `./waf` that builds every vehicle would have handed
Plane's picks of shared functions to Copter as well; for the Plane-only
names above that could not happen, since Copter has none of them. The
picks of an `[only <program>]` entry now name that program's own
objects and library archive (`*libArduPlane_libs.a:*` and
`*ArduPlane/*`), as waf passes `--program arduplane:ArduPlane`. A bare
`--program <name>` keeps the old unqualified picks, so the generator and
waf changes can land in either order. RPI_UAVFC Plane with
`--consistent-builds` gives `69d7ce322eb0` with the old picks and the
qualified ones.

Selection (`lib_pick.py`): the functions of `AP_NavEKF3`, `AP_NavEKF`,
`AP_AHRS` and `AP_DAL` still in flash on `373c878559`, ranked by mean
share of core0 over ten profiles of that code (armed MANUAL, FBWA,
CRUISE, LOITER and AUTO, two boots each). They held 7.09% of core0 in
229 sampled functions. Taken: 0.02% of core0 or more, or 0.01% at 0.7%
per KB, and none below 0.1% per KB; 89 functions, 17,288 B, 5.18% of
core0. The floor drops 14 large, thinly sampled functions (17.0 KB,
0.93%), among them `FuseVelPosNED` (3.3 KB), `selectHeightForFusion`,
`setAidingMode`, `readGpsData`, and `fuseEulerYaw`, which Plane's EKF3
uses only on the ground (in flight it fuses the full field through
`FuseMagnetometer`, already in SRAM). Without the floor, 0.03% alone
would have taken 66 functions and 28.1 KB for 5.24%.

Checked: RPI_UAVFC and Laurel Plane build with no warnings, `--verify`
finds every registered function in SRAM, and RPI_UAVFC copter with
`--consistent-builds` is `0a224befa8e2` both alone and from one
`./waf copter plane` run, in which Copter's
`NavEKF3_core::updateFilterStatus` stays in flash (0x100b6208) and
Plane's is in SRAM (0x20017150). Plane's SRAM code grows by 18,320 B
(78 more veneers); static heap 317,104 to 298,800 B.

A/B on the flight board, A `373c878559` (as built before the commit),
B the same plus the entries, boots A B B A, 200 Hz, EKF3 and the fake
GPS, throttle output pinned as for the navigation modes:

| | FBWA A / B | AUTO A / B |
|---|---|---|
| core0 busy | 52.0 / 45.8% | 52.2 / 45.9% |
| scheduler load | 30.0 / 24.8% | 30.3 / 25.4% |
| `Plane::ahrs_update` | 881 / 646 us | 864 / 600 us |
| FAST tasks per loop | 1084 / 859 us | 1069 / 817 us |
| XIP hit rate | 84.5 / 86.6% | 84.5 / 86.5% |
| MEMINFO free | 152,836 / 134,532 B | 152,828 / 134,524 B |

Core0 busy and scheduler load do not overlap between A and B in either
mode. `stabilize`, `set_servos` and `navigate` moved by a few
microseconds either way, inside the spread between boots of the same
build. The two A boots differed more than the B boots (`ahrs_update`
824 and 938 us in FBWA). This set buys about 6 points of core0 for
18.3 KB, the per-loop path's rate.

## Board state afterwards

`SCHED_LOOP_RATE` 200 and `GPS1_TYPE` 1 restored and read back, and the
full parameter list compared with the one read at the start: only
`BARO1_GND_PRESS`, the boot gyro offsets and their temperature, the
`STAT_*` counters and `MIS_TOTAL` differ. `MIS_TOTAL` went from 0 to 1
because the fake fix set home and Plane stores home as mission item 0;
the next real fix overwrites it. The board now runs A of the placement
A/B, `1411b17f5b`, the committed branch head, rather than the
`5e97be25` it had at the start; `STAT_BOOTCNT` went from 13 to 24. Bench
logs `00000001.BIN` to `00000005.BIN`, and one per A/B boot after them,
are on the SD card.

After the navigation round: `SERVO1_MAX` 2000 and `GPS1_TYPE` 1
restored and the test mission cleared, which also took `MIS_TOTAL` back
to the 0 it had at the start. The full parameter list then matches the
start but for `BARO1_GND_PRESS`, the boot gyro offsets and the `STAT_*`
counters (`STAT_BOOTCNT` 30). The board runs `29e77d95b8`, the
committed head with Plane's per-loop path in SRAM.

After the EKF3 and AHRS round the same restore and comparison hold, with
`STAT_BOOTCNT` 35; the board runs A of that A/B, the code of
`373c878559`, identifying as `29e77d95`.

Then, at Andy's request, `f4c65bc4f1` was built and flashed over COM32
(the uploader verified it). The board reports `ArduPlane V4.8.0-dev
(f4c65bc4)`, its parameters match the start of the session as above
(`STAT_BOOTCNT` 36), MEMINFO 138,152 B free and scheduler load 16-18%
disarmed at 200 Hz. It booted into RTL: Andy's transmitter was on by
then, and channel 8 (`FLTMODE_CH`) at 987 us selects `FLTMODE1`, which
is RTL on this airframe. OpenOCD shut down with `C_DEBUGEN` cleared on both
cores, the COM32 bridge stopped, the board disarmed.

## Reproduce

Tools in `tools/plane_profile/`; they use `attrib.py`, `xipctr.py` and
`bridge.py` from `tools/scripting_profile/`. Start `bridge.py COM32
127.0.0.1 5770` with Windows Python and OpenOCD as in README.md, then:

```sh
python plane_profile/session.py <out> dis_man:disarmed:0:30000 \
    arm_man:armed:0:30000 arm_fbwa:armed:5:30000
FAKE_GPS=1 python plane_profile/session.py <out> ...   # with GPS1_TYPE 14
python3 plane_profile/summary.py <arduplane ELF> <map> <out>...
python3 plane_profile/libgroup.py <ELF> <map> <ardupilot checkout> <out>/arm_fbwa_c0.txt
python plane_profile/logana.py <log>
# the placement sweep and its A/B
python3 plane_profile/sweep.py <ELF> <map> <ardupilot checkout> sweep.json <arm_fbwa_c0.txt>...
python3 plane_profile/pick_entries.py sweep.json <copter ELF> <ardupilot checkout>
python3 plane_profile/ab.py ABBA <dir with A/ and B/ firmware> <out>   # with GPS1_TYPE 14
python3 plane_profile/abana.py <dir with A/ and B/> <out> <ardupilot checkout>
# registry entries a Plane build does not need; shared-library candidates
python3 plane_profile/copter_only.py <plane ELF> <map> <ardupilot checkout> out.json <ELF>:<map>:<samples glob>...
python3 plane_profile/lib_pick.py <plane ELF> <map> <ardupilot checkout> AP_NavEKF3,AP_NavEKF,AP_AHRS,AP_DAL <ELF>:<map>:<samples glob>...
```

`ab.py` flashes the flight board, so it is for a disarmed bench only; it
stops OpenOCD and the bridge before every upload. `CONDS` picks its
conditions and `abana.py`'s; `MIN_PCT`, `MIN_DENSE_PCT` and
`DENSE_PER_KB` set `pick_entries.py`'s thresholds.

For the navigation modes, first set `SERVO1_MAX` to `SERVO1_MIN` and
`GPS1_TYPE` 14, then `plane_profile/mission.py upload <lat> <lon>` at the
fake GPS position; afterwards `mission.py clear` and restore both
parameters.

`session.py` force-arms, overrides channels 1-4 from system id 255 and
caps throttle at 1180. With no radio, a lost override stream leads to
the short failsafe's CIRCLE; entering an auto-throttle mode re-suppresses
the throttle (`mode.cpp` 121), and it stays suppressed on the bench
without 10 m of height or 5 m/s of GPS ground speed.
