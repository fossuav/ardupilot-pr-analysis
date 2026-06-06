# Disarmed periodic height-datum reset: design notes

## Background

Barometers drift with temperature. While a vehicle sits disarmed the EKF
height estimate follows that drift, so by the time it arms the reported
altitude-above-origin can be off by metres. Plane already addresses this by
periodically calling `update_home()` (which calls `AHRS::resetHeightDatum()`)
every 5 s while disarmed, in addition to a reset at arm. Copter previously
reset only at arm.

The question was whether Copter could adopt Plane's periodic reset. The naive
answer -- "just do the 5 s reset like Plane" -- turns out to cause a real
safety regression on Copter, while a couple of feared problems turn out **not**
to occur. This note records what the periodic reset does and does not break,
and the design that keeps the benefit without the regression.

All numbers below are from SITL probes (ArduCopter, EKF3). `XKF2.AZ` is the
EKF's learned accel-Z bias; `XKF1.PD`/`VD` are NED position/velocity down;
`P[15][15]` (`XKV2.V15`) is the Z accel-bias state variance.

## What a naive 5 s reset DOES cause

### 1. It slows on-ground accel-Z bias learning (the safety problem)

A reset recalibrates the baro to read zero and zeroes `velocity.z`. On the
ground, the Z accel-bias is observable only through the small height/velocity
error that zero-velocity fusion produces -- the exact signal the reset erases.
Resetting every 5 s while the filter is still learning therefore stretches
convergence.

With the bias present from boot (the realistic power-on case), time for
`XKF2.AZ` to reach the true 0.7 m/s/s:

| configuration            | reach 0.65 | reach 0.68 |
|--------------------------|-----------:|-----------:|
| no periodic reset        | 8.0 s      | 10.0 s     |
| 5 s reset, ungated       | 12.2 s     | 44.8 s     |

A 4.5x slower convergence. This matters because a multirotor lifts off on
vertical thrust: arming before the bias has converged means taking off with an
uncompensated Z accel bias, which corrupts the liftoff height/velocity estimate
("won't lift" or "jumps into the air"). The wide 10-45 s window where the
estimate is still wrong is the hazard.

### 2. With a GPS-fix gate it does nothing on baro-only vehicles (a bug)

Plane's periodic path (and a first cut on Copter) gates the reset on
`gps.status() >= FIX_3D`. But `resetHeightDatum` needs no GPS -- without a fix
it takes the full-reset path and preserves the height estimate via
`ekfGpsRefHgt += oldHgt` (the same path Copter's arm-time reset already uses
when home is not set). Gating the periodic reset on a fix means indoor /
optical-flow / GPS-denied copters -- the ones that rely on baro and most need
drift cleared -- never get it. Timing the interval off `gps.last_message_time_ms()`
makes it worse: that clock does not advance without GPS.

Verified baro-only (`GPS1_TYPE=0`, zero GPS messages): the un-gated, millis-timed
reset fires and bounds height drift to ~0.5 m (= drift 0.05 m/s x 10 s interval),
identical to the GPS-present case. The old gated code would have left it
unbounded (~4.5 m over 90 s).

**This is also present in Plane** -- its periodic `update_home()` is gated on a
fix at the call site, so a baro-only Plane never clears disarmed drift either.

### 3. It increases tracking lag of ongoing temperature drift (poor TCAL)

After initial convergence the variance is at its floor, so the filter is
"confident" even while a poorly-temperature-calibrated IMU keeps drifting during
warmup. The reset keeps erasing the tracking signal, so the bias estimate lags
the true (warming) value more than it would with no reset. Both still track --
neither diverges -- but the lag grows with reset frequency (see table below).

## What the reset does NOT cause

### A. No "kick" at the reset

A feared objection was that resetting gives the EKF a large kick. It does not.
The reset is a position relabel, not a dynamic disturbance: it zeroes
`velocity.z` across the whole output-observer buffer, zeroes `baroHgtOffset`,
and flushes the baro buffer, so there is no stale sample left to fuse.

Measured at an arm-time reset clearing 2.8 m of accumulated drift:

- `position.z`: clean one-sample step (the 2.8 m of drift being removed)
- `velocity.z`: no transient, |VD| <= 0.0012 m/s afterward (it actually got
  cleaner -- the pre-reset -0.01 m/s drift rate was removed)
- height innovation: <= 0.05 m, no spike

So the flight controller feels no vertical-velocity disturbance. (This depends
on the buffer flush + `baroHgtOffset = 0`; a naive reset that skipped those
*would* produce a velocity transient -- the objection is probably valid for an
older/simpler reset, but not this one.)

### B. It does not dump already-learned bias

A single reset does not reduce a converged bias estimate: the largest
downward step in `XKF2.AZ` across resets during active learning was 0.01 m/s/s
(noise). The reset touches `position.z`/`velocity.z`/baro, not the accel-bias
state or its covariance. This is why a one-shot arm reset is safe and why
resuming resets after convergence does not undo learning.

### C. It cannot fire in flight

`resetHeightDatum` returns early unless `onGround`, and the Copter periodic
call is additionally gated on `!motors->armed()`. So it cannot zero the height
state mid-flight.

### D. A "late step" in bias is not a real on-ground event

The variance-based gate (below) protects the from-boot convergence but not a
bias that steps in *after* the variance has collapsed. That is acceptable
because such a step is not physically realistic on the ground: temperature
drift is gradual (section 3, handled by interval choice), and the only genuine
*step* -- motor vibration rectification -- appears once **armed**, when the
periodic reset is already disabled, the arm reset has already fired, ground
effect inhibits on-ground learning, and the in-flight hover-Z-bias learning
takes over. So no rate-of-change term is needed in the gate.

## The design

Three pieces, all in common code, parameterised per vehicle:

1. **Convergence gate.** `resetHeightDatum` takes a `defer_until_abias_converged`
   flag. The arm-time reset passes `false` (always reset). The periodic reset
   passes `true`: each EKF core skips the reset while its Z accel-bias is still
   converging, i.e. while `P[15][15] > 0.03 * sq(ACCEL_BIAS_LIM_SCALER *
   _accBiasLim * dtEkfAvg)` (3% of the bias-limit variance that seeds the state,
   so it scales with `EK3_ACC_BIAS_LIM` and the EKF rate). This restores
   from-boot learning to baseline (0.68 reached at 10.0 s, identical to no
   reset) while still bounding drift afterwards.

2. **Not gated on GPS.** The periodic reset runs baro-only and is timed off
   `AP_HAL::millis()` (section 2).

3. **Per-vehicle interval.** The interval trades warmup-drift tracking lag
   against the height-drift bound (= baro_drift_rate x interval). Measured at
   an aggressive 0.3 m/s/s/min warmup drift and 0.05 m/s baro drift:

   | interval        | warmup lag | height-drift bound        |
   |-----------------|-----------:|---------------------------|
   | none (arm-only) | 0.050      | unbounded (~6 m / 2 min)  |
   | 5 s             | 0.075      | ~0.25 m                   |
   | 10 s            | 0.061      | ~0.50 m                   |
   | 15 s            | 0.056      | ~0.75 m                   |

   Copter uses **10 s** -- the knee of the curve: tracking within ~0.01 m/s/s of
   baseline, drift bounded to ~0.5 m, no rate-term needed. Plane keeps its 5 s
   (its launch does not depend on a converged on-ground Z bias). At realistic
   (much smaller) warmup drift rates the lag scales down proportionally and is
   negligible.

## Verification

- From-boot bias learning: gated 10 s == baseline (0.68 @ 10.0 s); ungated 44.8 s.
- Drift bounding: gated reset bounds disarmed height drift to drift_rate x interval,
  with the accumulated drift cleared once per interval after convergence.
- Baro-only (`GPS1_TYPE=0`): reset fires, drift bounded identically to with-GPS.
- Arm-time reset: clean position step, no velocity/innovation transient.
- `EK3AccelBias` and `EK3_AccelBiasInhibitOnGroundMoving` updated to inject the
  bias from boot (the realistic case) and pass on the gated build; they remain a
  regression test for the gate (ungated-from-boot's 44.8 s blows their 30 s
  assertion window).

## Follow-ups not in this change

- Apply the analogous fix to Plane: split `update_home()` so the home move stays
  GPS-gated but `resetHeightDatum` runs baro-only.
- Optional dedicated autotests for the baro-only firing and the drift bound.
