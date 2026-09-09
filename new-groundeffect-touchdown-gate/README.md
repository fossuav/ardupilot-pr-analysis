# NEW PR (not opened) - AP_GroundEffect: stop touchdown_expected latching in cruise

Prospective PR against master. Nothing implemented and no PR opened as of
2026-09-09; this directory exists so the design and its evidence are on
record before code is written.

Target: master `371990d846` (2026-09-05). The code is #32472, merged
upstream 2026-09-01, so this is a follow-up to a merged PR rather than a
change to one in review. See `../32472/` for that PR's own record; the
bullet about the HAGL path defeating `near_ground` is where this starts.

## Status (one line)

Two defects in `AP_GroundEffect::update()`, both measured on one flight
(log7, not committed, 2026-09-09); fix proposed, not written; validation
route chosen (Replay for the EKF cost, SITL A/B plus an autotest for the
gate itself); the deadband is sized from data, the latch bound is not.

## The problem

`touchdown_expected` was set for **51 s continuously** while an outdoor
BF_X quad hovered stationary at **17.9 m** above its takeoff altitude, and
for 20.8% of the whole armed flight. In the EKF that opens the
ground-effect baro protection: with `EK3_GND_EFF_DZ=-8` the baro
observation noise is floored at 64 m^2 and the innovation at -0.5 m. On
the lane of that flight with no vertical velocity source the altitude ran
away 5.6 m in 38 s against a flat barometer, with `XKF3.IPD` pinned at
exactly -0.5000 throughout. The cost is recorded in `../32972/` finding 6.

Two independent terms had to be true for 51 s. Both were, for different
reasons, and both look like defects.

### Defect 1: `near_ground` asserts proximity when it means "I do not know"

`AP_GroundEffect.cpp:149-158`. When `ahrs.get_hagl()` fails, the height
falls back to `-pos_d_m - takeoff_alt_m`, which assumes the ground under
the vehicle is at the takeoff elevation. The code correctly distrusts
that beyond `AP_GROUNDEFFECT_TAKEOFF_DRIFT_NE_MAX_M` (20 m) of horizontal
drift - and then converts the distrust into an assertion:

```cpp
near_ground = (drift_ne_m >= AP_GROUNDEFFECT_TAKEOFF_DRIFT_NE_MAX_M)
              || (height_m < _alt_m);
```

Measured: drift was 21.8 m, 1.8 m past the threshold, so `near_ground` was
true unconditionally at 17.9 m. Its own comment ("we cannot assume the
ground beneath us is at the takeoff elevation, so any gentle descent
counts") argues for not trusting `height_m`, which is not the same as
asserting proximity.

`get_hagl()` failed because the rangefinder was out of range high for
101 s continuous (`RNGFND1_MAX=15` on a vehicle that flies well above it)
and the AGL KF then timed out. Note that a terrain-database AGL was valid
and in use for optical flow the entire time; `getHAGL()` simply does not
serve it. That is a separate prospective PR, `../new-ekf3-hagl-terrain-alt/`,
and it is the cheaper root fix - with it, this flight would have taken the
`height_is_agl` branch and never reached the drift fallback.

### Defect 2: `descent_demanded` has no deadband

`AP_GroundEffect.cpp:135`:

```cpp
const bool descent_demanded = d_active && target_climb_rate_ms < 0.0f;
```

with `target_climb_rate_ms = _pos_control->get_vel_desired_U_ms()`.

Measured over the 51 s latch, on `-PSCD.DVD`, which is exactly that
signal: negative in **100.00% of 508 samples**, p50 -0.0000, max -0.0000,
longest continuous run 50.8 s. In a hover the desired vertical velocity
settles to a small **persistently negative** residual and never reaches
zero, and `< 0.0f` reads that as a commanded descent indefinitely.

This is not dither crossing zero. An earlier reading of this flight said
it was, from `CTUN.DCRt`; that is the wrong field (it logs
`get_vel_target_U_ms()`) and it was negative in only 24.1% of samples,
which would not have held the term at all. The correction is recorded in
`../32472/` and in the flight note.

## The proposed change

Not written. Three parts, in descending order of confidence.

1. **Deadband on `descent_demanded`**, sized from the data above. At
   0.05 m/s, 98.4% of the false samples on this flight stop qualifying,
   while the same flight's real approach ran a desired climb rate of
   -0.504 m/s at p50 and -1.90 at p5 - three orders of magnitude of
   margin. 0.01 m/s already removes 98.2%, so the exact value is not
   delicate; 0.05 is proposed because it is comfortably above any
   plausible numerical residual and comfortably below any commanded
   descent. Constant, not a parameter: a parameter here invites the
   `GNDEFF_ALT` problem recorded in `../32472/`, where a threshold that
   competes with the operating envelope becomes a floor on the useful
   hover band.

2. **Bound the latch when `near_ground` rests on the drift fallback.**
   `takeoff_expected` already has an unconditional
   `AP_GROUNDEFFECT_TAKEOFF_MAX_MS` (5 s) cap for the same reason. A
   touchdown that has not happened within a similar window is not a
   touchdown. Not sized from data - a real touchdown's duration in the
   gate has not been measured, and that measurement should come before
   the constant is chosen.

3. **Do not assert `near_ground` from drift alone.** The most direct fix
   and the one most likely to be argued about, because failing the other
   way costs real ground-effect protection at any landing site more than
   20 m from the takeoff point, which is the case the branch was written
   for. Parts 1 and 2 may make this unnecessary; if they do, leave it
   alone.

Preference: land 1 and 2, measure, and only reach for 3 if the gate still
latches. Part 1 alone would have prevented this flight's latch.

## Validation

The flight is replayable (`LOG_REPLAY=1`), which settles the EKF half
exactly. The gate half is vehicle code and is outside what Replay can
say, so it needs SITL.

- **Replay** the flight through the fixed EKF to show `XKF3.IPD` on the
  flow lane is no longer pinned and the 5.6 m does not accrue. This tests
  the consequence, not the gate: Replay re-feeds the recorded
  `takeoff_expected`/`touchdown_expected` through the DAL (`RFRN`), so a
  vehicle-side fix does not appear in it. Confirm that before relying on
  the result - if the flags come from the DAL, Replay can only validate an
  EKF-side change, and the gate fix has to be shown in SITL.
- **SITL A/B**: hover at 20 m more than 20 m from the takeoff point with
  no rangefinder in range, and log `XKF4.SS` bit 12. Before: set. After:
  clear. Then repeat with a real descent to confirm the gate still arms
  when it should.
- **Autotest**: the second half of that A/B is the test worth keeping. It
  must be demonstrated to fail on unfixed code - `../32472/` records
  `BaroGroundEffectAtTakeoff` as a test that arms in ALT_HOLD at idle and
  therefore tests the anchor against a glitch rather than a takeoff, and
  `../32972/` records a whole class of tests that discriminate nothing.

## What is here

```
new-groundeffect-touchdown-gate/
  README.md    <- this file
```

Nothing else yet. No logs, no plots, no code.

## Related

- `../32472/` - the merged PR this follows up, and the bullet that
  anticipated this failure and marked it not observed.
- `../32972/` finding 6 - the EKF-side cost, measured on the same flight.
- `../new-ekf3-hagl-terrain-alt/` - the root fix for why `get_hagl()`
  failed here.
