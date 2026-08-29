# PR #32472 - Ground effect altitude and timeout parameters (Copter / AP_GroundEffect)

Analysis archive for [ArduPilot/ardupilot#32472](https://github.com/ArduPilot/ardupilot/pull/32472).
Branch `pr-ground-effect`, base master. No logs committed; real-flight
numbers are cited inline.

## Status (one line)

Fourteen commits, two autotests driven by the new SIM_BARO_GEFF_M, approved
with mechanical items pending; the parameters were flown for six months as
TKOFF_GNDEFF_ALT/TMO on the SmallFastDrone branches across eight airframes,
and two places where this design differs from what was flown are recorded
below.

## The problem

Copter's window releases at 0.5 m of EKF altitude, which strong
propwash airframes cross within a few hundred ms while the barometer is
still metres wrong: a BF_X indoor quad -5 m, a 5-inch baro-only quad -9 to
-11 m, a MatekH743 flow quad -6.15 m at motor start, a ducted quad 121 Pa
(10 m) on a ground throttle ramp at ThO 0.15 with the rangefinder at
0.04 m.

## The conclusion and why

Three decisions, each with flight evidence:

- HAGL for the release check. BF_X quad log204 (not committed,
  EK3_RNG_USE_HGT 3, AltHold): the EKF altitude read -2.3 m at a true
  1.2 m, so a release check on EKF altitude re-armed the window right
  after every 5 s timeout; the noise floor stayed on permanently, the
  terrain reset (#32553) never fired, and the EKF drifted 3.4 m while
  the baro was only 0.3-2 m off. Switching the check to the AGL KF
  height (log206) gave a stable 0.3 m terrain offset and a clean
  release. This PR does the same through ahrs.get_hagl().
- A minimum hold. The MatekH743 flow quad's log11 first applied TMO 3;
  the ducted quad went 3 -> 5 for a slow-spooling frame; log22 with TMO
  0 is the A/B (below).
- No re-latch of takeoff_expected on descent. What the flag reaches
  inside the filter is wider than the baro noise: on the SmallFastDrone
  build a dip below TKOFF_GNDEFF_ALT re-latched it and, through a
  zero-velocity fusion term gated on it (SmallFastDrone only; master
  never had the term), replaced a rangefinder-anchored velocity with
  "not moving" on every dip (5-inch baro-only quad, log41). Keeping the
  flag to "about to leave the ground" is right.

## Key finding: two things the flown design did that this one does not

1. The takeoff timer. The SmallFastDrone detector resets takeoff_time_ms
   while land_complete, so TMO and the 5 s cap count from the land
   detector clearing. This PR anchors it while !throttle_up &&
   land_complete, throttle_up = has_manual_throttle() && throttle > 0, so
   in Stabilize and Acro the 5 s cap counts from the first throttle.
   Airframes that sit at throttle longer than that before lifting exist:
   BF_X quad log196 7.9 s, ducted quad log21 4-9 s, MatekH743 flow quad
   3.7 s from arm to throttle. After the cap the EKF fuses a
   propwash-corrupted baro at full weight on the ground. Either anchor the
   timer on land_complete as flown, or say in the body that
   manual-throttle spool-ups longer than 5 s are uncovered. (Note that
   #32972's pre-liftoff anchor ends at the first throttle in these modes
   regardless; see ../32972/.)
2. The descent re-enable. BF_X quad log210, baro-only (no rangefinder, so
   no HAGL), re-enable disabled: hovering low with the normal K the baro
   read -2.66 m in ground effect, the controller descended to follow it,
   ground effect grew, and the vehicle was pulled onto the floor. With the
   re-enable and the noise floor the contamination is bounded (~1.65 m,
   log208). This PR replaces the re-enable with an altitude gate on
   touchdown_expected, which needs a demanded descent (velocity target
   below zero), so a low hover being pulled down at mid-stick is not
   covered. The body defers "tightening the EKF's response to
   touchdown_expected"; log210 is what that follow-up is for, on
   baro-only airframes specifically. For rangefinder airframes the HAGL
   check makes a re-enable safe (log206) and the AGL-KF switch (#33359)
   removes most of the need.

## Field observations on GNDEFF_ALT from small indoor copters

- The threshold competes with the operating envelope. On a 5-inch indoor
  quad flying at 1.10 m mean (not committed), a 1.0 m threshold put 40%
  of airborne samples inside ground effect, so the 4x baro deweighting
  and the -0.5 m innovation floor (`XKF3.IPD` pinned at -0.5000) were the
  cruise condition; at 0.5 m it was 11%, and every dip re-entered it.
  Either flag deweights the baro the same way, so `GNDEFF_ALT` doubles as
  a floor on the useful hover band for such airframes.
- Without a rangefinder the gate is evaluated on the estimate it exists to
  protect. On a SkySakuraH743 baro-only quad (not committed) an EKF
  height over-read of 0.7-1.3 m had the gate open 34%, 8% and 94% of
  genuinely-low samples on three consecutive flights until the thrust
  scale was corrected (then 100%); with a payload the estimate never
  cleared 1.0 m and the gate latched for the whole flight. The HAGL path
  is the fix where a rangefinder exists.
- The HAGL path inherits an AGL KF dropout defect: with the rangefinder
  out of range low on the deck, `aglKfH` can ramp at ~0.4 m/s for up to
  5 s while the vehicle is motionless (`../33478/`, finding 3), which can
  release the takeoff window early or defeat `near_ground` at touchdown.
  Not observed in this PR's tests; a rangefinder-freshness check at
  `getHAGL()` would close it.
- Real amplitudes for `SIM_BARO_GEFF_M`: -9 to -11 m at spool-up, -16 to
  -21 m at touchdown (200-300 Pa in under a second), 2.4-3.8 m steps in the
  estimate. The SITL runs in the PR thread used 1 and 5 m.

## Also measured

- TMO 0 vs 3 on the ducted quad (log22 vs log21, not committed):
  post-compensation BARO.Alt std 39 -> 92 cm, alt-error std 11 ->
  17 cm, a 0.10 Hz mode the vehicle followed (84 cm rangefinder swing),
  two post-arm yaw resets. Confounded with a BARO_THST_FILT change in
  the same flight.
- Defaults vs flown: GNDEFF_ALT 0.5 here; the ducted frame runs 1.5, the
  5-inch baro-only quad went 1.0 -> 0.5 and found 11% of its indoor
  hover samples below 0.5 m. SIM_BARO_GEFF_M decays to zero at 2 m AGL,
  which is about the ducted case, not the small-quad one.

## What is here

```
32472/
  README.md    <- this file
```

No logs committed.

## Reproduce

```
git checkout pr-ground-effect
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.TakeoffGroundEffectAlt,TouchdownGroundEffectAlt
```

Not yet built: the log210 pull-down (AltHold at mid-stick at 0.3-0.4 m
with SIM_BARO_GEFF_M 3 and no rangefinder; the injected error grows as
the vehicle descends, which is the feedback loop) and the Stabilize
5 s-cap case (see ../32972/).

## Branches and people

- `pr-ground-effect` - the PR branch (local matches GitHub head
  2f81d1bfc2).
- SmallFastDrone-4.6-AltHold: 35a7f215dc (TKOFF_GNDEFF_ALT), b417228a68
  (TKOFF_GNDEFF_TMO); SmallFastDrone-4.7-beta becb063a13 (HAGL check).
- Related: #32972 (the EKF side; its anchor's outer gate is this
  window), #32553, #33359.
