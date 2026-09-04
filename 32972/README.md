# PR #32972 - Protect height fusion from baro ground effect at takeoff (EKF3)

Analysis archive for [ArduPilot/ardupilot#32972](https://github.com/ArduPilot/ardupilot/pull/32972).
Branch `pr-baro-gnd-effect`, stacked on #32768. No logs are committed;
the numbers below are from real indoor flights (cited inline) and from
the code.

## Status (one line)

Eight commits on top of #32768 (five plus three review fixups);
flight-developed on a BF_X indoor quad (SmallFastDronev1 board) over 22
indoor flights (Mar 2026) and run since on two more airframes; two SITL
autotests on the branch; rebased onto the 11-commit #32768 rewrite and
pushed 2026-09-04 (263f181a18), which cleared all twelve red CI checks;
the pre-liftoff anchor ends earlier than the PR body says (finding 1) and
can also engage in mid-air (finding 5).

The 2026-09-04 automated review and the three commits answering it are in
[review-response-2026-09-04.md](review-response-2026-09-04.md); findings 4
and 5 below live there in full.

## The problem

BF_X indoor quad (DPS310, EK3_RNG_USE_HGT -1): motor spool-up drops the
barometer 4-5 m. With the stock 4x scaler, log189 (not committed) stepped
-3.65 m at takeoff, the hgtTimeout ResetHeight snapping PD to the corrupt
baro. With ResetHeight suppressed (log190) PD still ramped -3.9 m, so the
reset was a contributor, not the cause. Other airframes: a 5-inch baro-only
quad -9 to -11 m spool-up spikes; a ducted quad 121 Pa (10 m) on a ground
throttle ramp at ThO 0.15 with the rangefinder at 0.04 m; a MatekH743 flow
quad -6.15 m at motor start.

## The conclusion and why

Three guards, each chosen after the obvious alternative was flown:

- Suppress ResetHeight while ground effect is expected. Riding on IMU
  integration for the window is accurate over seconds; snapping to a
  baro known to be metres wrong is not (log189).
- Negative EK3_GND_EFF_DZ as a noise floor. Per-fusion logging (log191,
  XKHD, not in the PR) showed PD 0.31 -> 3.06 m over about 11 baro
  samples with K growing 0.0005 -> 0.027 as P[9][9] grew: the 4x
  scaler (R 16 m^2 at EK3_ALT_M_NSE 2) is too weak. Every innovation in
  the window was positive, so the -0.5 m innovation floor was doing
  its job; the contamination was IMU drift integrating against a
  deweighted baro, not the baro pushing PD. R = |DZ|^2 (64 m^2 at -8)
  slows that.
- Pre-takeoff anchor. Baro-only with DZ -8 the spool-up (7.9 s, log196)
  still drifted -1.2 m from accel bias against R 64 and needed 75%
  throttle to leave the ground; fusing meaHgtAtTakeOff instead
  (log198) cut it to 0.13 m. That is the PR body's 1.2 -> 0.1 m.

Rejected:

- Innovation-variance capping in the GPS_GLITCH_RAD=0 style (log192):
  never activates; the noise floor makes the gate so wide the test
  ratio stays under 1.
- Capping Kfusion[9] directly (log193/194): PD still reached 5.9 and
  3.0 m, because the protected phase lasted four samples before the
  height source switched to baro above the RNG_USE_HGT threshold. That
  led to #33359 (AGL KF for the switch), not to a change here.
- A bi-directional +/-0.5 m innovation clamp at the normal R (log205):
  with EK3_RNG_USE_HGT > 0 the terrain offset diverged to 131 m and
  the altitude to -140 m; the vehicle fell with an unrecoverable EKF
  failsafe. terrainState = PD + rng feeds hgtMea = rng - terrainState,
  so per-sample PD motion of 0.02 m is amplified without bound; the
  floor's small K is what keeps that loop slow. Baro-only (log209) the
  clamp was also worse than the floor, -3.68 m against -1.65 m
  (log208): a constant K of 0.04 contaminates at 0.2 m/s where the
  floor's K averages 0.08 m/s.

## Key finding 1: the anchor ends at the takeoff command, not at liftoff

Anchor conditions: takeoff_expected || touchdown_expected, DZ < 0,
!assume_zero_sideslip(), time_flying_ms == 0. The last is zero exactly
while Copter's land_complete is true, and land_complete does not wait
for liftoff. Stabilize and Acro clear it as soon as the motors are
THROTTLE_UNLIMITED with throttle above the lower limit
(mode_stabilize.cpp), i.e. at the first real throttle. AltHold and
Loiter pilot takeoffs clear it in do_pilot_takeoff on throttle >=
min(TKOFF_THR_MAX, 0.9) or on EKF accel/velocity/altitude-change
thresholds, and with PILOT_TKOFF_ALT 0 (the indoor setting the
SmallFastDrone branches use) stop() clears it once throttle_in exceeds
hover/2. So the anchor covers the ground-idle interval and, in most
configurations, none of the spool-up; the spool-up gets the post-liftoff
floor, R = |DZ|^2, which is the regime log196 measured at -1.2 m.

Where the anchor does persist (AltHold with a takeoff altitude set) it
persists because it hides from the takeoff detector the motion the
detector waits for (log203: liftoff never detected with the anchor
on). The notes tried !takeOffDetected (true after 1 s from motor
vibration), !inFlight (baro-derived) and time_flying_ms and found each
circular; the PR picked the least bad. Open.

Flight timeline that shows it: ducted quad, log21 (not committed),
SmallFastDrone 4.7-beta4 with the equivalent code, third arm in Loiter,
EK3_GND_EFF_DZ -4 or -5 (the notes disagree; the anchor R is 1 m^2 either
way, see below):

| t (s) | EKF alt | CTUN.BAlt | RFND | |
|---|---|---|---|---|
| 120.18 | 0.03 | -0.21 | 0.16 | arm, reset fires |
| 120.20 | 0.00 | 0.00 | 0.16 | clean |
| 120.86 | ~-0.05 | rising | 0.17 | AUTO_ARMED, throttle up |
| 122.5 | -0.30 | -0.06 | 0.17 | on the ground |
| 123.18 | ~-0.36 | | 0.17 | vehicle-side window closes |
| 124.0 | -0.46 | -0.02 | 0.16 | |
| 125.0 | -0.52 | +0.02 | 0.17 | bottom |
| 130.0 | -0.25 | +0.49 | 0.42 | lifting off |
| 160.0 | 0.15 | 0.50 | 0.70 | -0.55 m vs rangefinder |

An earlier reading of this flight blamed the EKF chasing a corrupted baro
after the window closed. The table says otherwise: the compensated baro
sits within 0.1 m of zero from 122.5 to 125 s while the EKF walks away
from it, which is IMU drift against a deweighted baro (the log196
mechanism), and the recovery from 125 s is the baro regaining weight.
That build's window timer counts from land_complete clearing and expired
3.0 s after arm, so land_complete cleared at arm and the anchor never
ran; the spool-up had only the floor. The -0.85 m that persisted through
the hover is a different mechanism, see ../32553/.

Upstream vehicle side (#32472, same as master): the window timer is
anchored while !throttle_up && land_complete, with throttle_up =
has_manual_throttle() && throttle > 0 and a 5 s cap, so in Stabilize
the outer gate can also close 5 s after the first throttle. In ALT_HOLD
it never closes: has_manual_throttle() is false there, so throttle_up is
false whatever the stick does, the timer is re-anchored every cycle and
the 5 s cap never expires. That is why the ResetHeight suppression needed
a bound of its own; see review-response-2026-09-04.md.

BaroGroundEffectAtTakeoff arms in ALT_HOLD at idle with the stick
untouched, so land_complete stays true for the whole 8 s: it tests the
anchor against a glitch, not a takeoff, and it does not reach the
ResetHeight suppression at all - the held reference keeps the innovation
inside the gate. BaroGroundEffectResetSuppression was added for that
branch and its expiry.

The anchor noise: the PR body says R = 0.1*|DZ|; the code is
sq(MAX(0.1*|DZ|, 1.0)), which is 1 m^2 for every allowed DZ. The
0.64 m^2 in the flight notes does not match; either the SmallFastDrone
build lacked the floor of 1.0 or the note computed it from the formula.

## Key finding 2: where a negative dead zone is right, and where it is wrong

The parameter conflates two knobs and the sign selects which:

| `EK3_GND_EFF_DZ` | innovation dead zone | baro R in ground effect       |
|------------------|----------------------|-------------------------------|
| +4               | -0.5 to -4.0 m       | `ALT_M_NSE^2 * 4` = 16 m^2    |
| +10              | -0.5 to -10.0 m      | 16 m^2 (unchanged)            |
| -8               | -0.5 to -8.0 m       | `max(8,1)^2` = 64 m^2         |

The 4x scaler is hard-coded and independent of the parameter; the dead
zone uses `fabsF()` either sign. So a negative value gives a wider dead
zone and 4x more deweighting at once.

That is right when a rangefinder anchors the height (the BF_X flights
behind this PR, where the floor was what kept the terrain-offset feedback
loop stable). It is wrong on a baro-only vehicle, where the baro is the
only observation and deweighting it to R = 64 leaves the vertical channel
on IMU integration: flown on a baro-only quad, log51 (not committed), the
EKF drifted to -1.15 m while the vehicle sat on the ground. On the 5-inch
baro-only quad (height time constant ~6 s measured from the innovation
ramp) the same value would take the steady-state lag at 0.16 m/s from
~1.0 m to ~3.7 m. Positive values scale the dead zone only, which costs
nothing: the logged post-clamp innovation of -7.63 m at spool-up inverts
exactly to a raw -11.13 m, which at +10 would present as -1.63 m. Not a
cure either; the EKF moved 0.05-0.09 m across that spike, and the 1.3 m of
lag accrued in the climb that followed.

The parameter description should say "negative values assume a
rangefinder (or another height or velocity anchor) is fused"; the -8
example as written will be copied onto baro-only airframes.

## Key finding 3: what the floor costs on the other side

- 5-inch baro-only quad, log38 phase 2 (not committed): a rangefinder
  dropout on a touchdown put +3.6 m into the estimate through a mechanism
  that is SmallFastDrone-only (fixed there); the ground-effect innovation
  floor then held XKF3.IPD at exactly -0.5000 through the re-takeoff, so
  the baro could not correct it. The PR keeps the floor except while the
  anchor is active.
- Same quad, log41 seg1 (positive DZ 4, so the 4x scaler): a real 3.26 m
  climb inside the 5 s window (RFND 0.34 -> 3.60, the baro tracked it)
  moved PD 0.75 m, then a 2.6 m step at the timeout. With
  |DZ| > 2*ALT_M_NSE the negative-DZ floor deweights the baro more
  than the scaler, so a real climb inside the window tracks worse as
  |DZ| grows. That flight was also fusing a synthetic zero velocity
  through the window (SmallFastDrone bug, fixed there; master never had
  the term), so it is not a clean measurement. Inconclusive; the trade
  is real.

## Also measured

- The whole protection set off vs on: ducted quad log22 vs log21
  (TKOFF_GNDEFF_TMO 0 vs 3): post-compensation BARO.Alt std 39 ->
  92 cm, alt-error std 11 -> 17 cm, a new 0.10 Hz oscillation the
  vehicle physically followed (84 cm rangefinder swing), two yaw resets
  within 5 s of arm vs none. Confounded with BARO_THST_FILT 1.0 -> 0.1
  in the same flight.
- With a rangefinder height source and the AGL-KF switch (#33359), PD
  stayed within +/-0.05 m through takeoff (log195). That, not this PR,
  is the fix for rangefinder vehicles; this PR is for baro-only.

## What is here

```
32972/
  README.md                        <- this file
  review-response-2026-09-04.md    rebase, the 2026-09-03 review, findings 4 and 5
  plots/
    ab_ground_effect_takeoff.png   A: baseline DZ 4 vs this PR at DZ -5
    ab_reset_suppression_bound.png B: baseline vs unbounded vs bounded suppression
    make_plots.py                  regenerates both from data/ab-2026-09-04/
  data/ab-2026-09-04/
    A1_base_dz4.BIN                baseline binary (1c88a3bf62), DZ 4, GEFF 5
    A2_branch_dzm5.BIN             branch binary, DZ -5, GEFF 5
    B1_base.BIN                    baseline binary, GEFF 30
    B2_nobound.BIN                 branch with the suppression bound compiled out
    B3_branch.BIN                  branch as merged, GEFF 30
    harness.py                     the throwaway autotest methods used
```

All SITL (CMAC home), no real-flight logs. The flight-derived numbers in
the sections above are from logs that are not committed.

## Reproduce

```
git checkout pr-baro-gnd-effect
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.BaroGroundEffectAtTakeoff
Tools/autotest/autotest.py --no-configure test.Copter.BaroGroundEffectResetSuppression
```

Measure the EKF height with XKF1.PD in the log, or LOCAL_POSITION_NED.z
live. Never GLOBAL_POSITION_INT.relative_alt: AP_AHRS falls back to the
raw baro whenever the EKF vertical position is unhealthy, which is the
state these tests create, so it reports the barometer and any assertion
on it passes whether the code works or not (finding 4).

The takeoff-command gap has no test yet. To build one: Stabilize,
EK3_GND_EFF_DZ -5, EK3_RNG_USE_HGT -1, arm, raise throttle to about
half hover and hold 8 s (land_complete clears at the first throttle, so
the anchor is off), with SIM_BARO_GLITCH -5 or, with #32472,
SIM_BARO_GEFF_M (applies whenever throttle > 0, decays to zero at 2 m
AGL); watch XKF1.PD. The terrain-loop failures (log205) need a SITL
rangefinder with EK3_RNG_USE_HGT > 0 and the same injection. A baro-only
variant (RNGFND1_TYPE=0) with a -8 floor should reproduce the on-ground
drift of finding 2.

## Branches and people

- `pr-baro-gnd-effect` - the PR branch, at 263f181a18 (2026-09-04),
  local and origin in sync, based on 1c88a3bf62 (#32768 head).
  Pre-rebase backups: pr-baro-gnd-effect-backup-prerebase (3980009868)
  and pr-baro-gnd-effect-backup-20260904 (pre-fixup, 0e2cb01baf).
- SmallFastDrone-4.7-beta equivalents: c31449d865 (ResetHeight),
  8809637be5 (noise floor), 721f9986a7 (anchor); 873a262140 is the
  variant flown on the ducted quad.
- Related: #32472 (vehicle-side window, where the outer gate is
  decided), #32553 (terrain reset, the log200-206 series), #33359 (AGL
  KF switch, log195), the AGL KF #32389.
- Automated review 2026-09-03 (AIReview label, external dev-call batch,
  not GitHub Actions): four points, all answered, two of them belonging
  to #32768 rather than here. See review-response-2026-09-04.md.
