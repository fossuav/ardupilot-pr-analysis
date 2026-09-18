# PR #34432: AP_NavEKF3: keep baro ground effect out of a height source switch

https://github.com/ArduPilot/ardupilot/pull/34432, branch
`andyp1per/pr-baro-offset-gnd-effect`, opened 2026-09-18 at `f2be29f74e`.

Found while reviewing #32232 (see `../32232/README.md`, 2026-09-18 section,
for the variant matrix and the pinned-climb carry-over).

## Mechanism (tier 2)

Copter trusts the range finder for height only while `is_taking_off() ||
is_landing()`. With EK3_RNG_USE_HGT, an ALT_HOLD takeoff (PILOT_TKO_ALT_M 0)
puts the range finder on for the spool-up and switches back to baro at
liftoff, still in ground effect. `calcFiltBaroOffset()` has learned baro minus
range height through the spool-up, and the switch resets the height to that
baro. Master reaches it with a range finder that reads on the ground; an
out-of-range-low one never goes fresh there (#32232 changes that).

## Master A/B, BaroGroundEffectRangefinderSwitch (SIM_BARO_GEFF_M 3)

EKF height minus truth; the mean runs from 5 m up to the switch to LAND.

| build | worst, arming to 5 m | mean above 5 m |
|---|---|---|
| master | -0.66 | +2.50 |
| offset held, reset kept | -3.05 | +0.14 |
| reset skipped, offset learned | -0.01 | +2.47 |
| fix | -0.17 | +0.03 |

An earlier run with the landing descent in the mean: -0.66/+2.43,
-2.99/+0.05, -0.01/+2.41, -0.17/0.00. Master with RNGFND1_MIN 0.05
(out of range low on the ground): +0.02.

Regression at the fix: Copter TakeoffGroundEffectAlt, TouchdownGroundEffectAlt,
RangeFinder, SurfaceTracking, FlyRangeFinderSITL, RangeFinderPowerDown,
EK3_RNG_USE_HGT, Replay; QuadPlane Mission, PrecisionLanding, LoiterAltQLand,
MAV_CMD_NAV_TAKEOFF, VTOLLandGoAround, TakeoffCheck. All pass.

## Rejected variants (tier 2, on #32232's branch)

Dead zone on negative offset error: ratchets upward on baro noise (-0.07 m
EKF error after a 10 s armed wait at SIM_BARO_RND 0.2; modelled +0.17 m at
sigma 0.1). Offset floored at its value when the flag rose: same results as the
freeze, but needs its floor reset wherever the offset is reset (#32768 re-inits
it at arming). Neither did better in any of six scenarios.

## Known limits

- Baro drift is not learned while the flags are set, which on Copter is the
  whole armed wait on the ground. Measured real thermal drift is about 1.5 m
  over 3 min, so about 0.08 m over a default 10 s DISARM_DELAY wait.
- Fixed wing (fly_forward) is excluded; QuadPlane VTOL is included.
- Only the takeoff is tested; touchdown uses the same two conditions.
