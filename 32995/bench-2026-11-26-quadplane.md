# #32995 QuadPlane on RPI_UAVFC, 2026-11-26: the rate thread at #35395's head

The bench of `bench-2026-11-25-quadplane.md`, repeated on the alpha2 branch
refreshed with ArduPilot/ardupilot#35395 at its PR head: ArduPlane
`dfba74c2`, branch `rp2350-quadplane-rate-thread` in the ardupilot-rp2350
checkout. #35395's review changed which thread works out the outputs: the
main loop now runs `calc_pwm()` once a loop and the rate thread only sends
the finished values, where the version benched yesterday (`15a9ee53`,
`488cd840`) ran `calc_pwm()` in the thread on every iteration. The flash
matched the ELF over SWD at every boot.

Same wing, outputs and precautions as yesterday: VTOL motors on outputs
1-4, the ESC on output 1 unpowered, the elevon servos unplugged from
outputs 3 and 4, `Q_M_SPIN_ARM` 0, throttle held at `RC3_MIN` by override,
force-disarm if servo 1 ever exceeds 1000 (it never did). Two things
differ on the bench: an external compass is now detected
(`COMPASS_DEV_ID` 855305, not calibrated), and the CRSF receiver is linked
to its transmitter (50 Hz link, 160 Hz telemetry). The SD card mounts
again: logs 37-40 are today's.

**Summary.** The review's output change holds on hardware, and the thread
is cheaper on core1 than before it. Disarmed in FBWA with the throttle
stick at 1800, the forward throttle output stayed at its minimum in every
sample, thread on and off. The thread with a 200 Hz main loop still saves
10 points of core0 against QuadPlane as it is (300 Hz, no thread), as
yesterday, and core1 is 10 points less busy than yesterday with it, the
output path no longer recomputing every channel at 1.6 kHz. Core0 is
about 11 points busier than yesterday in both configurations alike, which
the CRSF link and the compass account for most of.

## The disarmed throttle check

`disarmed_thr_check.py` (scratch, not in tools/): disarmed, FBWA, RC3 held
at 1800 by override, `SERVO_OUTPUT_RAW` at 50 Hz for 15 s.

| | samples | output 7 (throttle, `SERVO7_MIN` 1100) |
|---|---|---|
| thread on (`Q_FSTRATE_ENABLE` 2, 200 Hz) | 694 | 1100 in all |
| thread off (`Q_FSTRATE_ENABLE` 0) | 394 | 1100 in all |

This is the case the PR's first version got wrong in SITL, sending the
stick's 1800 while disarmed. Output 2 reads 0 throughout, thread on or
off: TIM4 puts outputs 1 and 2 on DShot together and `SERVO_BLH_MASK` 1
covers only output 1. Nothing to do with the thread.

## Results

A thread off at 300 Hz (QuadPlane as it is), C thread on at 200 Hz (the
RPI_UAVFC default), each with PWM motors and with DShot600
(`Q_M_PWM_TYPE` 6, `SERVO_BLH_BDMASK` 15). Method and conditions as
yesterday, without B and D.

core0 / core1 busy, scheduler load (SYS_STATUS):

| | A, PWM | C, PWM | A, DShot | C, DShot |
|---|---|---|---|---|
| disarmed QSTABILIZE | 57.3 / 18.4 / 39.6 | 48.1 / 32.3 / 30.5 | 57.2 / 19.6 / 39.6 | 47.5 / 33.0 / 28.6 |
| armed QSTABILIZE | 63.0 / 18.0 / 43.5 | 53.0 / 32.3 / 32.9 | 63.3 / 20.8 / 43.8 | 53.7 / 33.5 / 31.0 |
| armed QHOVER | 60.0 / 19.3 / 40.2 | 50.2 / 32.3 / 29.8 | 59.7 / 19.1 / 40.0 | 50.3 / 32.6 / 28.6 |
| armed FBWA | 55.1 / 18.8 / 34.2 | 46.9 / 31.5 / 25.6 | 55.0 / 18.5 / 34.1 | 46.3 / 32.5 / 24.9 |

From the logs (37 A, 38 C, 39 A DShot, 40 C DShot), armed QSTABILIZE:

| | A, PWM | C, PWM | A, DShot | C, DShot |
|---|---|---|---|---|
| PM load | 41.7-43.7% | 32.2-33.1% | 41.4-43.5% | 30.5-31.4% |
| MaxT | 3.36-3.38 ms | 5.02-5.07 ms | 3.36-3.39 ms | 5.01-5.06 ms |
| long loops, all armed modes | 2 (QHOVER, FBWA) | 0 | 1 (FBWA) | 0 |
| `RTDT` dtMax median / worst | - | 692 / 827 us | - | 693 / 824 us |
| MEMINFO free | 124,144 B | 120,224 B | 123,936 B | 120,008 B |

Against yesterday, armed QSTABILIZE, PWM:

| | A yesterday | A today | C yesterday | C today |
|---|---|---|---|---|
| core0 busy | 52.0% | 63.0% | 41.0% | 53.0% |
| core1 busy | 18.1% | 18.0% | 41.9% | 32.3% |
| scheduler load | 39.5% | 43.5% | 28.3% | 32.9% |
| `RTDT` dtMax median / worst | - | - | 696 / 837 us | 692 / 827 us |

- The thread's saving on core0 is unchanged: 10 points today, 11
  yesterday, and 10.6 points of scheduler load against 11.2.
- Core1 with the thread: 9.7 points more idle than yesterday. Per
  function, `calc_pwm()` and the `pwm_from_angle`/`pwm_from_range` it
  calls are gone (1.5 points), and the HAL's output work fell by about 4:
  `push_local` 1.73 to 0.39%, `dshot_send` 0.70 to 0.15%, with the group
  triggers and DMA locks under it. The outputs now change once a main
  loop instead of at the rate loop rate, so most pushes have little to
  send. The rest is spread thinly.
- Core0, both configurations: about 11 points busier than yesterday.
  Thread off, function by function: CRSF decoding, CRSF telemetry and the
  PIO UART carrying them +4.3 points, the compass and the sensor status
  checks +2.0, terrain +0.6; EKF3 and the AHRS +0.1. The rest is spread
  thinly. A bench condition, not the code: the comparisons within today
  stand.
- The thread's jitter is as yesterday while armed. In mode 5 both C logs
  show one larger gap, 4.2 ms (log 38) and 3.4 ms (log 40), each within
  0.15 s after the disarm that ends the session; log 40 has another
  3.4 ms gap 8 s later, still disarmed. Yesterday's C on `15a9ee53` has
  the same, 3.1 ms 0.11 s after its disarm (log 30), so it predates the
  review change. Not investigated.

## Board state afterwards

Restored as yesterday: `Q_ENABLE` 0, the outputs, `SERVO2`-`SERVO4` limits
and trims, `SERVO_BLH_BDMASK` 1, `GPS1_TYPE` 1, `SCHED_LOOP_RATE` 200, and
the mission cleared of the fake GPS's home. The 1,175 parameters match
those read at the start (`params.txt` in the scratch `before2` and `after2`)
but for `BARO1_GND_PRESS`, the boot gyro offsets and their temperature and
the `STAT_*` counters. The board now runs `dfba74c2` rather than
`488cd840`; `RCOut: DS600:1-2 PWM:3-5` as before.

## Reproduce

As yesterday, with today's configurations:

```sh
CONDS="dis_qs:disarmed:17:30000 arm_qs:armed:17:30000 arm_qh:armed:18:30000 arm_fbwa:armed:5:30000" \
  python3 quadplane_profile/qp_bench.py <out> <fw dir> \
  "A:Q_FSTRATE_ENABLE=0,SCHED_LOOP_RATE=300,Q_M_PWM_TYPE=0" "C:Q_FSTRATE_ENABLE=2,SCHED_LOOP_RATE=200,Q_M_PWM_TYPE=0" \
  "Ad:Q_FSTRATE_ENABLE=0,SCHED_LOOP_RATE=300,Q_M_PWM_TYPE=6" "Cd:Q_FSTRATE_ENABLE=2,SCHED_LOOP_RATE=200,Q_M_PWM_TYPE=6"
python3 quadplane_profile/qp_summary.py <ELF> <map> <out>/A <out>/C <out>/Ad <out>/Cd
python3 quadplane_profile/qp_summary.py --top 2000 <ELF> <map> <out>/C/arm_qs_c1.txt
python3 quadplane_profile/qp_logana.py <log>
```
