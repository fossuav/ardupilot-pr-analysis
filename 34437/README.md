# PR #34437 - AP_Math: keep angle shaping in float

[ArduPilot/ardupilot#34437](https://github.com/ArduPilot/ardupilot/pull/34437),
branch `andyp1per/pr-angle-shaping-float`, opened 2026-09-19 at
`d61612b6f0` on master `368dc0c428`. One commit, AP_Math only.

## What it does

`shape_angle_vel_accel()` works in float but called `shape_pos_vel_accel()`,
which takes `postype_t`. With double positions (`HAL_PROGRAM_SIZE_LIMIT_KB >
1024`) every call converted both angles to double, subtracted and converted
back; on a 2 MB F4 or an RP2350 those are four software calls per shaped
axis per loop in the attitude controller. The float body is now a static
helper taking the position error; the `postype_t` function takes the
difference and calls it, and the angle form passes its wrapped error
straight in. A float overload would clash with the `postype_t` one when
positions are float.

Position shaping is unchanged. The attitude controller passes an angle of
zero, so its results are bit for bit the same; AP_Follow's non-zero angle
differs by float rounding only.

Found in #32995's core0 profile (see
[../32995/bench-2026-09-19.md](../32995/bench-2026-09-19.md)). It is small -
about 0.1% of core0 there, estimated from the call rate - and most of the
software double cost on that board is legitimate position arithmetic. The
same patch is `cc87a7b9c7` on the RP2350 branch.

## Evidence

- `Control.test_shape_pos_vel_accel`: nine cases against outputs of master's
  implementation, covering angle zero and non-zero, the wrap both ways,
  disabled and active velocity limits, non-zero desired acceleration and two
  position cases with asymmetric limits, all clear of the jerk limit. It fails
  if the wrap is dropped or if the moved body loses the acceleration
  feedforward (both checked by mutation).
- Copter.ModeAltHold and Copter.ModeFollow pass in SITL at `d61612b6f0`
  (ModeFollow covers the AP_Follow caller).

## Review findings answered

- First test compared two wrappers of the same new helper, and the jerk limit
  (0.17 per step with those constants) flattened its outputs: replaced with
  the golden-value test above (both reviewers).
- "The position case will fail in SITL because 1000.02 rounds to float":
  refuted, it passed in SITL - ArduPilot builds with
  `-fsingle-precision-constant`, and the expected value was generated under the
  same flag. The fragility was real, so the cases now use positions exact in
  both float and double (1000 + 1/32, -250 + 1/32).
- Test name, the long call line, and the doc block now sitting on the static
  helper: renamed, wrapped, and left (`control.h` documents the public
  function).
