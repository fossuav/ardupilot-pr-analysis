# PR #34362 - AP_GroundEffect: stop touchdown_expected latching in cruise

Analysis archive for [ArduPilot/ardupilot#34362](https://github.com/ArduPilot/ardupilot/pull/34362).
Branch `groundeffect-touchdown-gate` (andyp1per fork), five commits, head
`c0935b991f`, base master `363235939d`. Opened 2026-09-10. This directory
carried the design and its evidence before the code was written.

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
serve it. That is a separate prospective PR, `../34361/`,
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

Written 2026-09-09, see "Implemented" below. Three parts, in descending
order of confidence.

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
  vehicle-side fix does not appear in it. **Confirmed 2026-09-09**:
  `log_RFRN` carries `takeoff_expected` and `touchdown_expected` as bits
  (`AP_DAL/LogStructure.h:98-99`) and `AP_DAL::get_touchdown_expected()`
  reads them straight back, so Replay re-feeds the flags the flight
  recorded. Replay can therefore show what the floor cost, and can never
  show the gate fix working. The gate half is SITL only.
- **SITL A/B**: hover at 20 m more than 20 m from the takeoff point with
  no rangefinder in range, and log `XKF4.SS` bit 12. Before: set. After:
  clear. Then repeat with a real descent to confirm the gate still arms
  when it should.
- **Autotest**: the second half of that A/B is the test worth keeping. It
  must be demonstrated to fail on unfixed code - `../32472/` records
  `BaroGroundEffectAtTakeoff` as a test that arms in ALT_HOLD at idle and
  therefore tests the anchor against a glitch rather than a takeoff, and
  `../32972/` records a whole class of tests that discriminate nothing.

## Implemented 2026-09-09

All three parts, on `SmallFastDrone-4.7.1-beta` over base `fd37f6f5fa`:

| part | commit |
|---|---|
| 1 deadband | `a18992efe3` |
| 2 latch bound | `6ae889d8a0` |
| 3 drift rule | `0b1c1124b8` |

The preference recorded above was to land 1 and 2 and only reach for 3 if
the gate still latched. Part 3 was landed anyway: the rule is wrong on its
own terms whether or not the earlier parts mask it, and it is a separate
commit so it can be reverted alone. Part 1 alone does clear this flight's
latch, as predicted.

### Part 2: the constant, now measured

This file asked for the measurement before the constant was chosen. It
was the right call, because the answer refutes the "similar window"
reasoning that suggested copying the 5 s takeoff cap.

The legitimate window is `GNDEFF_ALT` divided by the landing descent
rate. Takeoff altitude does not enter it. Measured in SITL 2026-09-09 on
the branch, longest single `XKF4.SS` bit 12 episode across a LAND to
disarm:

| `GNDEFF_ALT` | `LAND_SPD_MS` | takeoff alt | longest episode |
|---|---|---|---|
| 1 | 0.5 (default) | 15 m | 3.60 s |
| 5 | 0.5 | 15 m | 11.60 s |
| 10 | 0.5 | 15 m | 21.60 s |
| 10 | 0.5 | 30 m | 21.50 s |
| 5 | 0.3 | 15 m | 18.70 s |
| 10 | 0.3 | 15 m | **35.20 s** |
| 10 | 2.0 | 15 m | 1.30 s |

15 m and 30 m give 21.60 s and 21.50 s, which is what says the takeoff
altitude is not a term. 35.20 s is the worst case at the documented
extremes of both parameters (`GNDEFF_ALT` range -1 to 10, `LAND_SPD_MS`
range 0.3 to 2).

So a 5 s cap would have cut the *default* `GNDEFF_ALT=5` landing in half.
The constant chosen is `AP_GROUNDEFFECT_TOUCHDOWN_MAX_MS` = 60 s. Re-run
with it in, the 35.20 s case measures 35.20 s unchanged, so it cuts
nothing legitimate.

**Say plainly what this part does not do.** 60 s would not have fired on
the 51 s hover that motivated the work. It bounds a latch that would
otherwise hold for the rest of the flight; it is not what closes the
observed case. Part 1 is. A pure wall-clock bound cannot separate the two
cases, because at 35.2 s of legitimate window and an unbounded
pathological one there is no value that is both tight enough to catch a
51 s hover and loose enough to spare a slow approach. That is a limit of
the design, not of the constant.

### Part 1: margin, stated against the right thing

The 98.4% / 98.2% / -0.504 / -1.90 figures above stand as measured. One
clarification: the "three orders of magnitude of margin" compares the
real approach to the hover residual (p50 -0.0000 m/s). Against the 0.05
m/s deadband itself the margin is one order of magnitude, and that is
what the code comment claims.

The deadband also shortens the gate on ordinary landings near the takeoff
point, which was not anticipated here. On `TouchdownGroundEffectAlt`,
where drift stays under 20 m so part 3 is inert and the durations are far
under part 2's cap, the whole difference is part 1:

| leg | base `fd37f6f5fa` | branch |
|---|---|---|
| `GNDEFF_ALT=1`, land from 3 m | 6.90 s | 3.60 s |
| `GNDEFF_ALT=5`, land from 3 m | 12.80 s | 7.90 s |

The gate was being held open through the hover-residual part of the
approach as well, not only in cruise.

### Part 3: the cost, measured

The trade this file flagged is real and is now a number rather than a
worry. 30 m from the takeoff point with no rangefinder, landing:

| | gate open |
|---|---|
| base `fd37f6f5fa` | 9.60 s |
| branch | 0.00 s |

That is the ground-effect protection a baro-only vehicle loses when it
lands more than 20 m from where it lifted off. Anything with a
rangefinder or terrain coverage takes the `height_is_agl` branch and
never reaches the drift rule - which is why
`../34361/` is the root fix and was landed alongside.

### Autotests

Both demonstrated failing on base `fd37f6f5fa` with the tests present,
2026-09-09.

- `TouchdownGroundEffectCruise` (new). Leg 1 flies the repro: hover 20 m
  up, 30 m out, no rangefinder, force-disarm in the air so no landing
  contaminates the measurement. Base 16.80 s of gate, including one
  continuous 13.00 s episode; branch 0.00 s. Leg 2 flies a real landing at
  the same 30 m with a rangefinder fitted, and requires the gate to arm -
  3.50 s on the branch. Leg 2 is the guard against an over-tight fix: a
  change that simply never arms the gate passes leg 1 and fails leg 2.
- `TouchdownGroundEffectAlt` far-from-takeoff leg (rewritten). It
  asserted the old rule, that dropping the gate lengthens the window.
  Now asserts the gate stays shut without a true AGL. Base 13.30 s,
  branch 0.00 s.

### Still outstanding

- The Replay of the flight through the fixed EKF, to show `XKF3.IPD` on
  the flow lane is no longer pinned and the 5.6 m does not accrue. The
  gate half is settled by SITL above; this is the EKF-side consequence,
  and it is the one number this file still owes `../32972/` finding 6.
- No PR opened.

## What is here

```
34362/
  README.md    <- this file
```

No logs or plots here yet. The code is on `SmallFastDrone-4.7.1-beta`
(`a18992efe3`, `6ae889d8a0`, `0b1c1124b8`) with its autotests in
`Tools/autotest/arducopter.py`.

## Related

- `../32472/` - the merged PR this follows up, and the bullet that
  anticipated this failure and marked it not observed.
- `../32972/` finding 6 - the EKF-side cost, measured on the same flight.
- `../34361/` - the root fix for why `get_hagl()`
  failed here.
