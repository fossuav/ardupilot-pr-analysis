# PR #35308 - EKF3 averages the flow samples between measurements

Analysis archive for [ArduPilot/ardupilot#35308](https://github.com/ArduPilot/ardupilot/pull/35308).

Opened 2026-11-20 at `cd6a948cc5`, branch `pr-ekf3-flow-average`, on
master: `02cf47e433` (AP_NavEKF3) and `cd6a948cc5` (autotest). On by
default, as discarding four samples in five is the defect.

## What it does

`writeOptFlowMeas()` gates measurements at `sensorIntervalMin_ms` (50 ms)
and used to keep the sample at the gate. Now every usable sample received
since the last measurement (quality > 0, rates under 4.2 rad/s) is summed
with its body rates and the average is written. The sum restarts after a
gap longer than an interval. An interval with no usable sample writes
nothing, and its body rates still feed the gyro bias estimate, as before.
A 10 Hz sensor is unchanged; DroneCAN sensors in the fleet run 50-66 Hz,
MAVLink 100 Hz, one ARK around 200 Hz.

## Evidence

- SITL test (tier 2): hover flow innovation spread at 100 Hz 24.1-27.6
  mrad/s over three runs (five samples averaged predicts 25.8, one sample
  57.7), 10 Hz 56.5-58.1; without the change 57.7 at 100 Hz.
- SITL A/B, flow-only hover, 0.05 rad/s noise: velocity error rms 0.057 ->
  0.038 m/s and drift 0.27 -> 0.08 m at 100 Hz; 0.051 -> 0.038 m/s at
  66 Hz; 10 Hz identical.
- Fleet Replay (tier 1b, 423 logs, SFD beta with #35306 and #35307): flow
  innovation spread lower on 270 lanes, higher on 79 (median ratio 0.87);
  time the flow is 1 m/s out of agreement with the velocity -16%; GPS p95
  lower on 74 cores, higher on 61, summed +17.2, all of it one log.

### Superseded 2026-11-23 in its log count

The 423 files of that fleet Replay are 381 distinct logs: 40 flights sit
in the cache under two or three names, so its counts and sums take them
more than once. The numbers stay as measured; re-run on the distinct logs
before citing them.

## The one regression: a flow lane locked out on the ground

An O4 log, core 1 (a flow lane, GPS on core 0): GPS p95 8.0 -> 25.2 m/s.
Instrumented Replay showed the touchdown bounce (flow up to 2.3 rad/s, body
rate 1.8 rad/s) processed differently: the base came out with 0.007 m/s of
velocity error, the averaged build with 0.17. On the ground the flow height
is clamped near the range finder's ground clearance (5 cm), so 0.17 m/s
predicts 3.7 rad/s against a measured zero; the Y axis is rejected while X
passes, and the lockout recovery defers ("range stale") because a range
below its minimum is never fused. The velocity integrates accel bias to
36 m/s by disarm. Small parameter perturbations did not flip either build.

Not averaging's: across the fleet 122 lanes with a range finder exceed
1 m/s on the ground in both builds; averaging flips 14, 9 worse and 5
better (the "Operational VALT Flight" flow-out outlier is one of the 9).
Owed as its own fix: let the recovery treat a below-minimum range on the
ground as a measured height, and look at the 5 cm clamp's gate.

## Decided

- Body frame (tridge's question). Offline, yaw within a 50 ms window is
  p99 2-3.6 deg, max 5.3, and the plain average differs from one rotated
  into the window centre by p99 0.2-2% of the flow, max 5.5%. A prototype
  rotating each sample by the newest IMU's yaw since the last measurement
  and the average back into the newest frame, replayed over the fleet,
  left the flow innovation spread unchanged (median ratio 1.000, p10-p90
  0.996-1.005), GPS p95 lower on 42 cores, higher on 31, summed -2.9;
  recovery events within a few percent. The plain average stays.
- EK3_FLOW_M_NSE stays at 0.25. Replays with averaging: 0.15 gives GPS p95
  summed -16.9 over 255 cores but 26% more lockout resets (343 -> 431) and
  quality latches 42 -> 58; 0.10 is worse on both (GPS +37.0, resets +60%).
  Without averaging 0.15 is worse (GPS +39.9, resets 326 -> 454). The
  parameter covers scale, height and timing errors averaging does not
  reduce.
- Equal weighting: the EKF knows arrival times only, which carry the
  scheduler's jitter, not the sensor's integration intervals.
- Time stamp: the fixed 50 ms back-dating (`flowTimeDeltaAvg_ms/2`, for a
  10 Hz PX4Flow) stays; a 100 Hz single sample was ~45 ms too old and the
  average is ~25 ms, so the error halves. Following the sensor rate is a
  separate change.
- `delTimeOF` is zeroed before the Z body rate reads it, so Z is the latest
  IMU sample, not a window average: pre-existing, left out.

## On the SFD beta

#33484 carries a per-sample quality that master lacks; the beta needs
the quality averaged with the samples (post-merge fixup in the SFD
REFRESH_NOTES; the beta port `1c1d7fa154` did it).

## Open, 2026-11-23 (head `cd6a948cc5`)

AP-Review asks for the Replay test to run at `SIM_FLOW_RATE` 100. Not
changed. Its other point, the unaveraged Z body rate, is the pre-existing
behaviour recorded under "Decided".
