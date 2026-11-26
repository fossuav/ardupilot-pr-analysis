# #32995 QuadPlane on RPI_UAVFC, 2026-11-25: the rate thread for QuadPlane

Andy's flying wing on the bench (RPI_UAVFC on COM32, picoprobe on COM10),
reconfigured as a QuadPlane: VTOL motors 1-4 on outputs 1-4, aileron,
elevator, throttle and rudder on outputs 5-8 (output 5 is the LED-strip
pad; 6-8 have no pins). For the bench, Andy unpowered the ESC on output 1
and unplugged the elevon servos from outputs 3 and 4. `Q_M_SPIN_ARM` 0,
throttle held at `RC3_MIN` by override, and the session force-disarms if
servo 1 ever exceeds 1000; it never did. `LOG_BITMASK` 65535, `GPS1_TYPE`
14 with the stationary fake fix.

Firmware: ArduPlane `15a9ee53`, then `488cd840` with the fix below,
branch `rp2350-quadplane-rate-thread` in the ardupilot-rp2350 checkout, on
the rebased alpha2 branch (#32995 at `b9db33af08`). The flash matched the
ELF over SWD at every boot.

**Summary.** Copter's rate thread now lives in AP_Vehicle and QuadPlane
can use it (`Q_FSTRATE_ENABLE`, `Q_FSTRATE_DIV`). On the bench with PWM
motors, QuadPlane with the thread at 1.6 kHz and a 200 Hz main loop
leaves core0 41% busy armed in QSTABILIZE, against 52% for QuadPlane as
it is today (300 Hz, no thread), with no long loops and the VTOL rate
loop at 1.6 kHz instead of 300 Hz. The thread itself takes little off
core0 (2 points at 300 Hz, none at 200 Hz); the saving is the lower loop
rate, which the thread makes acceptable for VTOL. Core1 goes from 17% to
42% busy. RPI_UAVFC and Laurel now default to that split.

With bidirectional DShot on all four motor outputs and nothing answering
(the unpowered ESC and unplugged pins), the thread at a fixed 1.6 kHz
stalled for about 5 ms at a time and the main loop overran at 100% load
while both cores sat mostly idle. The cause was a console print in the
IMU thread for every sample the rate thread's queue dropped, blocking in
the port's direct USB write; `488cd840ff` compiles it out and the stall
is gone. With DShot active the numbers match the PWM ones, with core1
about 2 points busier.

## The code

Thirteen commits on the alpha2 branch, the first seven a Copter refactor
with no behaviour change and the rest QuadPlane support:

| commit | change |
|---|---|
| `dee71bb390` | AP_Vehicle: the rate thread, moved from Copter, with hooks for the mode, divisor, output and logging; `RTDT` through the named-format logger |
| `223a6d8582`, `6b07c2839a` | RP2350 registry: AP_Vehicle's thread in SRAM, Copter's old names dropped (squash candidates) |
| `a9b80c66c6` | Copter: uses AP_Vehicle's thread; `FSTRATE_*` stay where they are |
| `f3ae82818c`, `0419136e71` | the notch update task moves to AP_Vehicle |
| `d2669622c0` | RP2350 registry: Copter's hooks in SRAM |
| `662bfea548` | AP_InertialSensor: the fast sample window built into Plane |
| `fbcda24885`, `2f4f8fbd05` | the thread rotates its gyro into the controller's AHRS view (QuadPlane pitches it by `Q_TRIM_PITCH`; Copter's is the body frame) |
| `866dd1f5c5` | Plane: `Q_FSTRATE_ENABLE`, `Q_FSTRATE_DIV`; with the thread on it is the only writer of the outputs; motor test and ESC calibration keep the motors in the main loop; off for tailsitters and tiltrotors, with a pre-arm check |
| `c569acb085`, `15a9ee53af` | RP2350: the perf report comment, QuadPlane's hooks in SRAM |

Later the same day: `373f8e533f` (Plane: `AP_PLANE_QUADPLANE_DEFAULT_LOOP_RATE_HZ`,
300 unless a board sets it), `c7319d37c1` (hwdef: RPI_UAVFC and Laurel set
it to 200 and ship `Q_FSTRATE_ENABLE` 2, `Q_FSTRATE_DIV` 2),
`0ef0fefd64` (DEVELOPMENT.md) and `488cd840ff` (AP_InertialSensor: the
dropped-sample print compiled out, below).

SITL, before the bench: Copter's `CompassMotFastRate`,
`DynamicRpmNotchesRateThread`, `RateThreadPostFilterGyroLog` and
`ThrottleGainBoostRateThread` pass on the refactor; the dynamic rate's
999/499 Hz steps in `DynamicRpmNotchesRateThread` vary as much between
three runs of the refactor (0, 1, 20) as against the base (8). QuadPlane
with `Q_FSTRATE_ENABLE` 1 (`tools/quadplane_profile/qp_sitl_check.py`)
ran the thread at 999 Hz through a motor test, QHOVER, QLOITER, a
transition to FBWA, a back-transition and QLAND, with the same climb,
airspeed and landing as with it off. The QuadPlane autotests never set
the parameter, so they do not cover the thread. Copter's refactor has not
run on hardware.

## Method

As for Plane earlier the same day: one boot per configuration, 30,000
DWT PCSR samples per core per condition through OpenOCD, XIP counters,
`tasks.txt`, SYS_STATUS load, and PM and `RTDT` from the dataflash log.
Conditions: disarmed QSTABILIZE, then armed at zero throttle in
QSTABILIZE, QHOVER and FBWA. QLOITER was dropped: the compass reads
unhealthy, so EKF3 never has a horizontal position on the stationary
bench.

Configurations: A thread off at 300 Hz (QuadPlane as it is), B thread on
at 300 Hz, C thread on at 200 Hz, D thread off at 200 Hz; the thread with
`Q_FSTRATE_ENABLE` 2 (fixed once armed, as Copter on this board) and
`Q_FSTRATE_DIV` 2 (1.6 kHz from the 3.2 kHz ICM-56686). Motors on PWM
(`Q_M_PWM_TYPE` 0); see the DShot section for why.

## Results

Armed QSTABILIZE:

| | A off, 300 | B on, 300 | C on, 200 | D off, 200 |
|---|---|---|---|---|
| core0 busy | 52.0% | 50.2% | 41.0% | 40.9% |
| core1 busy | 18.1% | 43.1% | 41.9% | 17.4% |
| scheduler load (SYS_STATUS) | 39.5% | 37.9% | 28.3% | 29.3% |
| PM load | 43.7-44.7% | 42.3-44.1% | 33.2-34.7% | 34.1-35.0% |
| long loops / MaxT | 1 / 4.59 ms | 1 / 4.33 ms | 0 / 5.04 ms | 0 / 5.06 ms |
| rate loop | 300 Hz | 1600 Hz | 1600 Hz | 200 Hz |
| `RTDT` dtMax median / worst | - | 694 / 832 us | 696 / 837 us | - |
| `Plane::set_servos` average | 236 us | 148 us | 148 us | 233 us |
| MEMINFO free | 130,336 B | 126,224 B | 126,384 B | 130,480 B |

All conditions, core0 / core1 busy and scheduler load:

| | A | B | C | D |
|---|---|---|---|---|
| disarmed QSTABILIZE | 48.0 / 17.8 / 35.5 | 47.4 / 42.9 / 34.4 | 37.5 / 40.4 / 25.8 | 37.8 / 16.9 / 26.7 |
| armed QSTABILIZE | 52.0 / 18.1 / 39.5 | 50.2 / 43.1 / 37.9 | 41.0 / 41.9 / 28.3 | 40.9 / 17.4 / 29.3 |
| armed QHOVER | 48.0 / 17.4 / 35.7 | 46.8 / 42.7 / 34.2 | 38.5 / 42.8 / 25.7 | 39.2 / 17.2 / 27.0 |
| armed FBWA | 42.6 / 17.0 / 31.1 | 41.6 / 41.8 / 29.2 | 34.9 / 40.9 / 22.2 | 34.5 / 17.5 / 22.9 |

- The thread takes the rate controller, the mixer and the output push
  out of `Plane::set_servos` (236 to 148 us a loop). That is 2.7 points
  of core0 at 300 Hz and 1.8 at 200 Hz, and the measured saving is
  smaller still. Most of core0 is `ahrs_update` (EKF3, 456-545 us) and
  `stabilize` (QuadPlane's attitude, height and input shaping, 283-299
  us), which stay in the main loop.
- Core1 pays about 25 points for a rate loop 5 to 8 times as fast, and
  stays 57% idle.
- The thread's jitter is small: a median worst gap of 0.69 ms a 100 ms
  window against its 0.625 ms period, worst 0.85 ms, in every mode.
- 300 to 200 Hz saves about 11 points of core0 and 10 of scheduler load
  with or without the thread. Without it (D) the VTOL rate loop also
  drops to 200 Hz.
- The thread costs about 4 KB of heap: its 3 KB stack and the gyro
  window.
- In FBWA the VTOL motors are shut down, but the thread still runs the
  rate controller and the output push at 1.6 kHz, so core1 pays the same.

## Bidirectional DShot with nothing answering

The first matrix ran the motors as DShot600 (`Q_M_PWM_TYPE` 6). The RP2350
driver requires bidirectional DShot on every DShot output ("BDMASK must
cover all DShot outputs"), so `SERVO_BLH_BDMASK` 15, with nothing on any
of the four answering.

- `Q_FSTRATE_ENABLE` 1 (dynamic) cycled 1600 → 1066 → 800 → 1066 → 1600
  Hz about five times a second in every condition, disarmed and in FBWA
  too, each step a STATUSTEXT. With PWM motors it never stepped.
- `Q_FSTRATE_ENABLE` 2 held 1580-1596 Hz armed, but the thread saw gaps
  of about 5 ms in every 100 ms window (log 24, log 25, 4.7-5.1 ms), and
  the main loop at 300 Hz ran long on about two loops in three (`NLon`
  about 1,350 per PM row, `MaxT` 5.2-6.6 ms, load 100%) until disarmed.
  MAVLink starved: mode changes and arming were not acknowledged.
- SWD samples taken inside that window (log 25, about 146-170 s) show core0
  64% and core1 82% idle: both loops are waiting, not working.
- The INS's measured gyro rate fell from 3,194 to 3,022 Hz over the 54 s
  armed (the thread's rate in `RTDT` from 1,597 to 1,511 Hz), which reads
  as samples being lost.
- At 200 Hz (log 26) the same: `RTDT` dtMax median 4.9 ms, worst 6.8 ms,
  `MaxT` 5.2-7.0 ms, PM load 58-65%.
- With the motors on PWM at 300 Hz (log 27; outputs 1-2 still DShot
  through `SERVO_BLH_MASK` 1, also silent): 1,600 Hz, dtMax median
  0.70 ms, worst 0.78 ms, PM load 24%, no long loops after arming.
- Without the thread (A on DShot, log 20) or at the dynamic mode's
  average of about 1 kHz (logs 21, 22) the main loop was healthy.

### The cause: a console print per dropped sample

The DShot path never waits on the ESC: `RCOutput_pico::write_frame()`
returns and restarts a parked state machine after two missed replies,
there is no DMA handle to collect, and a missing reply only counts an
error. The clue was core1's profile inside the stall: the IMU's SPI
functions, which lead core1 in a healthy run, were gone, and in their
place were the USB write path (`usb_prepare_in_ep`, `obqWriteTimeout`,
`UARTDriver::_write`) and `print_vprintf`.

`AP_InertialSensor::push_next_gyro_sample()` runs in the IMU bus thread
and, on every ChibiOS build, called
`hal.console->printf("IMU: dropped rate loop sample\n")` each time the
rate thread's queue was full. On this port a USB write with
`HAL_USB_CDC_DIRECT_IO` starts the transfer and then drains it in the
writing thread, sleeping 125 us at a time for up to about 10 ms
(`usb_tx_poll_drain()`). So each print held the IMU thread for
milliseconds: its FIFO overflowed, samples were lost, the rate thread fell
further behind and the queue dropped more. A raw capture of the USB stream
during a 30 s armed run (`RAWLOG` in `qp_armed_profile.py`) held 9,804
complete copies of the line and about 1,400 broken ones, about 200 a
second, invisible to the MAVLink parser.

`488cd840ff` compiles the print out unless `FAST_RATE_BUFFER_DEBUG` is set
in the file. The same test, DShot on all four outputs at the fixed
1.6 kHz, armed in MANUAL at 300 Hz:

| | log 32, `15a9ee53` | log 33, `488cd840` |
|---|---|---|
| long loops per PM row | about 1,400 | 0 |
| MaxT | 5.3-6.2 ms | 3.35-3.40 ms |
| PM load | 100% | 20-21% |
| rate thread | 1,552 Hz | 1,600 Hz |
| `RTDT` dtMax median / worst | 4.9 / 6.5 ms | 0.77 / 0.81 ms |
| IMU lines in the raw stream | 9,804 | 0 |

The print is upstream code (`6db09c9fdd`, the fast rate buffer), so the
fix is for master; Copter on a USB-powered bench with its ESCs off would
have met the same. What first fills the queue with silent bidirectional
outputs is not found: disarmed, where `FSTRATE_ENABLE` 2 scales
dynamically, the rate still steps 1600-1066-800 Hz about five times a
second with DShot and never with PWM. Armed at the fixed rate it held
1,600 Hz.

For the port (#32995), separately: any thread that writes to the USB
console or a USB MAVLink port blocks in `usb_tx_poll_drain()` until the
transfer drains, up to about 10 ms. Not measured beyond this case.

### The matrix with DShot active

`488cd840`, `Q_M_PWM_TYPE` 6, otherwise as the PWM matrix:

| core0 / core1 busy, scheduler load | A off, 300 | B on, 300 | C on, 200 | D off, 200 |
|---|---|---|---|---|
| disarmed QSTABILIZE | 47.4 / 18.5 / 35.2 | 46.3 / 38.8 / 34.4 | 38.0 / 38.6 / 26.5 | 37.9 / 17.4 / 28.1 |
| armed QSTABILIZE | 51.3 / 18.6 / 39.5 | 50.4 / 45.7 / 37.2 | 41.1 / 44.4 / 28.4 | 40.5 / 17.9 / 30.6 |
| armed QHOVER | 48.3 / 18.8 / 35.9 | 47.1 / 45.3 / 33.9 | 38.2 / 44.6 / 26.3 | 38.2 / 17.6 / 27.8 |
| armed FBWA | 42.6 / 17.8 / 30.2 | 41.7 / 43.7 / 28.6 | 34.0 / 43.4 / 22.2 | 33.7 / 16.9 / 24.8 |

Core0 is within a point of the PWM matrix everywhere; core1 with the
thread is about 2-3 points busier armed, the DShot frames at the rate
loop rate. `Plane::set_servos` 241 / 151 / 152 / 232 us, `stabilize`
285-297 us, `ahrs_update` 454-534 us, as with PWM. No rate steps armed in
B or C. The SD card stopped mounting after this run (no logs listed over
MAVFTP or the log protocol, also after a reboot), so its logs (34-37) are
unread; log 33 above is the same firmware and outputs at 1.6 kHz.

## Board state afterwards

The wing configuration is restored: `Q_ENABLE` 0, the outputs, `SERVO2`-
`SERVO4` limits and trims (QuadPlane's motor setup had rewritten them),
`SERVO_BLH_BDMASK` 1 and `GPS1_TYPE` 1 set back, and the fake GPS's home
cleared from the mission. The 1,175 parameters then match the start
(`data/2026-11-25-quadplane/params-before.txt` and `params-after.txt`) but
for `BARO1_GND_PRESS`, the boot gyro offsets and their temperature, and the
`STAT_*` counters (`STAT_BOOTCNT` 64). `RCOut: DS600:1-2 PWM:3-5` as
before. The board runs `488cd840` rather than `f4c65bc4`; the stored
`Q_` parameters stay in storage, hidden while `Q_ENABLE` is 0.

The SD card did not mount at the end. Logs 19-33 are this session's: 19
the smoke run, 20-23 the DShot matrix A-D, 24-26 the DShot fixed-rate runs,
27 the PWM control, 28-31 the PWM matrix A-D, 32-33 the print before and
after the fix. Logs 34-37 (the DShot matrix on `488cd840`) are on the card
if it mounts after a power cycle.

## Reproduce

Tools in `tools/quadplane_profile/`, with `plane_profile/` and
`scripting_profile/`. Bridge and OpenOCD as in README.md, then:

```sh
python3 quadplane_profile/qp_params.py --reboot NAME=VALUE ...   # set, read back, reboot
CONDS="dis_qs:disarmed:17:30000 arm_qs:armed:17:30000 arm_qh:armed:18:30000 arm_fbwa:armed:5:30000" \
  python3 quadplane_profile/qp_bench.py <out> <fw dir> \
  "A:Q_FSTRATE_ENABLE=0,SCHED_LOOP_RATE=300,Q_M_PWM_TYPE=0" "B:Q_FSTRATE_ENABLE=2,SCHED_LOOP_RATE=300,Q_M_PWM_TYPE=0" ...
python3 quadplane_profile/qp_summary.py <ELF> <map> <out>/A <out>/B ...
python3 quadplane_profile/qp_logana.py <log>
# armed in MANUAL without relying on MAVLink replies (the DShot stall starves the link)
python3 quadplane_profile/qp_armed_profile.py <out> 30000
# SITL
python3 quadplane_profile/qp_sitl_check.py <ardupilot checkout> <out> <extra defaults>
```
