# PR #33507 - estimate the accel-Z bias inside the AGL KF (EKF3)

Analysis archive for [ArduPilot/ardupilot#33507](https://github.com/ArduPilot/ardupilot/pull/33507).
Branch `pr-agl-kf-zbias` (andyp1per fork), base `master`. Evidence is Replay
on, and flights of, a 4-inch optical-flow quad (MatekH743, ARK Flow,
downward rangefinder), flights of a 5-inch baro-only indoor quad, and Replay
on a second flow-navigation airframe; numbers inline, no logs committed.
Upstream logs the AGL KF as `XKFA`; the flights were on the SmallFastDrone
branch where it is `XKF6`.

## Status (one line)

The bias state is right; its process-noise default is not. Bias state
flight-validated; the decoupled process noise `EK3_AGL_ABIAS_P` (third
commit) was Replay-derived and then flight-confirmed, but the 0.05 default
that passes the autotest under-tracks thermal drift on two airframes
(0.1-0.3 flown; 0.3 flight-validated). The PR body and one code comment still
describe Qbias in terms of `EK3_ABIAS_P_NSE`, which the third commit replaced.

## The problem

The 2-state AGL KF integrates `velDotNED.z`, which still carries the active
accel-Z bias (`correctDeltaVelocity` removes only the inactive-lane bias and
the frozen hover-Z correction). With no bias state the rangefinder only
partially corrects the drift, so the AGL height sits high by an amount that
tracks the main filter's bias: `HAgl - RFND*cosTilt` was +0.33 m at
`XKF2.AZ` 0.51 decaying to +0.13 at 0.21 (4-inch quad, log56). Not tilt
(which lowers it), not lag (it was high during the climb). That offset feeds
the flow velocity scaling (~20% early-flight scale error), would corrupt
altitude outright if the AGL height were fused as the rangefinder
observation (#33359), and with #33478 a short AGL velocity becomes a short
main-filter velocity and a sinking altitude hold.

## The conclusion and why

Add the bias as a third state, `[h, v, b_az]`, observable from successive
rangefinder updates, with the Joseph update reducing to the 2-state form when
the bias terms are zero. Flown on the 4-inch quad, log59 (not committed):
`Bias` converged to -0.065 (std 0.018) and `HAgl` tracked the rangefinder
with no offset.

Then it was too stiff. `Qbias` was sized for a static bias, but the bias
drifts with IMU temperature (~5 C of prop-wash cooling per flight). log66:
`BiasStd` locked at 0.009, a persistent +0.1 m/s upward residual in both
`VD` and `-VAgl` while the rangefinder was flat, and altitude ran to 1.16 m
against 0.13 m with the rangefinder selected as height source all flight.
The lever is the residual velocity, not the height switch.

Hence the third commit: a dedicated `EK3_AGL_ABIAS_P`, decoupled from the
main filter's `EK3_ABIAS_P_NSE`. It is safe to loosen because the AGL-KF bias
is a pure random walk with no prediction term - it changes only in the
innovation-gated rangefinder update, its covariance is capped, and after 5 s
without the rangefinder the filter is marked invalid - so a looser value
cannot learn a bad bias on stale range data, unlike the main filter.

## Key findings

### Replay sweep on log66 (PD drift over the hover / main-filter AZ std)

| setting                          | drift  | AZ std |
|----------------------------------|--------|--------|
| baseline (shared 0.02)           | 0.74 m | 0.034  |
| shared EK3_ABIAS_P_NSE = 0.1     | 0.29 m | 0.051  |
| decoupled EK3_AGL_ABIAS_P = 0.1  | 0.40 m | 0.034  |
| decoupled 0.2                    | 0.30 m | 0.033  |
| decoupled 0.3                    | 0.27 m | 0.033  |

Raising the shared noise recovers the drift but makes the main filter's bias
noisier (0.051), the bad-bias risk. The decoupled parameter recovers the full
~60% reduction at 0.2 with the main filter unchanged.

### Under-tracking at the default, fixed at 0.3

Regress AGL-KF height change on rangefinder height change over 1-5 s
baselines (slope 1.0 = perfect; the input normalises out so flights of
different aggression compare). Flown on the 5-inch baro-only quad (not
committed):

| log            | `AGL_ABIAS_P` | slope     | corr      |
|----------------|---------------|-----------|-----------|
| log35          | 0.05          | 0.70-0.71 | 0.93-0.94 |
| log38 phase 1  | 0.05          | 0.59-0.61 | 0.89-0.90 |
| log41 seg1     | 0.3           | 0.83-0.85 | 0.96      |
| log41 seg2     | 0.3           | 0.84-0.87 | 0.96-0.97 |
| log41 seg3     | 0.3           | 0.90-0.94 | 0.97-0.98 |

Low slope at high correlation is a gain error, not noise, which is what
made it findable. With 0.3 and #33478 that airframe held 36 s hands-off at
0.13 m true std.

The same value came out of a Replay sweep on a second flow-navigation
airframe (log311, not committed), metric = main-filter altitude lag behind
the rangefinder over a 0.9 m/s climb: 1.70 m at 0.05, 1.03 at 0.1, 0.47 at
0.2, 0.20 at 0.3, ~0 at 0.5, monotonic, with no hover-height penalty and no
jitter (0.026 m against the rangefinder's own 0.040). 0.3 rather than 0.5
keeps the re-acquisition transient after a long dropout proportionally
smaller. A third airframe wanted 0.1-0.2.

The intuitive reading is backwards: a rising `XKFA.Bias` during a climb
looks like the bias "stealing" velocity, which argues for a lower Q. The
Replay refuted it; the ramp is the filter correctly tracking the offset and
needs to be faster.

### The default is the autotest's number, not the airframe's

0.05 passes `EK3_AglKfVelForVelD` (a sudden bias step overshoots at >=0.1)
and gives ~36% of the reduction. Flown at 0.05 on the 4-inch quad (log67):
`BiasStd` locked at 0.0156, exactly as Replay predicted (~0.0155), and
altitude still drifted (1.3 m against 0.3 m) on a flight that cooled 7 C.
Replay predicts 0.2 gives `BiasStd` 0.041. A slow thermal drift and a step
are different tests; the default is tuned to the step. The parameter doc's
own argument ("only updates from clean rangefinder measurements, so a higher
value cannot learn a bad bias") supports a higher default.

### The bias freezes on a dropout, and the velocity does not go to zero

With no measurement `aglKfB` holds (by design) while the prediction keeps
adding `(aglKfB - velDotNED.z)*dt`; the 2 s decay leaves a steady state of
residual x tau, not zero. The bias state shrinks the residual but any
unlearned part still integrates. The consequence for consumers of `aglKfV`
and `aglKfH` (the velD fusion, the height-source switch in #33359, the HAGL
gate in #32472) is written up in `../33478/`.

### The root beneath it

The 4-inch airframe's accelerometer reads ~0.77 m/s^2 low at 45 C despite
`INS_TCAL1` enabled to 70 C (IMU.AccZ -9.04 at 45 C, -9.79 at 28 C, pre-arm,
level). The whole chain - ground bias learning, AGL-bias tracking, residual
velocity, altitude drift - is compensating for a sensor that should read
flat over temperature. Fixing the thermal calibration removes the thing being
chased; this PR makes the chase work in the meantime.

## What is here

```
33507/
  README.md    <- this file
```

No logs committed; logs 56, 59, 66 and 67 (4-inch quad), 35, 38 and 41
(5-inch quad) and 311 (second airframe) are cited by number only.

## Reproduce

```
git checkout pr-agl-kf-zbias
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.OpticalFlowAGLKalmanFilter
```

The Replay sweeps are real-log only (`--force-ekf3` over a log carrying
RISI/RFRN/RRNI/ROFH). The under-tracking has no SITL reproduction yet:
inject a slowly ramping `SIM_ACC1_BIAS_Z` during a flow hover with repeated
1-3 m climbs at 0.05 and 0.3, and regress `XKFA.HAgl` change on rangefinder
change; the default should show a slope well under 1 at high correlation.

## Branches and people

- `pr-agl-kf-zbias` - the PR branch (three commits: state, autotest,
  decoupled process noise).
- Author: @andyp1per. No maintainer review yet.
- Consumed by #33478 (`../33478/`), whose flight validation ran this filter
  at 0.3; #33359's `aglKfH` fusion needs it.
- Reviewer question (LupusTheCanine): a shared AccZ bias? The AGL KF bias
  has to stay learnable while the baro is gated, which is exactly when the
  main-filter bias freezes; #33478 makes the main bias observable through
  the velD fusion instead of by sharing the state.
