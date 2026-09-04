# PR #32972 - review response, 2026-09-04

Covers the rebase onto the rewritten #32768, the automated review of
2026-09-03, and three commits added in reply. All numbers here are SITL
unless stated; no logs are committed.

Branch went 0e2cb01baf -> 263f181a18, eight commits on 1c88a3bf62
(#32768 head). `git range-diff` across the rebase reported `=` on all
eight, so nothing was dropped or re-resolved.

## The twelve red CI checks were one cause, and not a code fault

Every failing job (eleven `test size` boards plus colcon) died at the same
place, before compiling anything of this PR:

```
CONFLICT (content): Merge conflict in ArduCopter/AP_Arming_Copter.cpp
error: could not apply d2f256e46e... Copter: clear baro drift at arm time via height datum reset
```

That is CI rebasing the PR onto master and hitting *this* branch's stale
copy of a #32768 commit. #32768 had been rebased onto newer master
(123 files of upstream movement) while #32972 still carried the old
copies. Rebasing the five ground-effect commits onto
`origin/pr-baro-drift-minimum` cleared all twelve; `mergeable` went
CONFLICTING -> MERGEABLE with no source change.

Worth recognising the shape: N identical failures in jobs that do not
build the changed subsystem, naming a file the PR never touches, is a
stale-base signature rather than N bugs.

## Review point 1: the ResetHeight suppression had no time bound

Upheld, but the reviewer's stated reason does not hold and the real one
is worse.

The review said `AP_AHRS::set_takeoff_expected()` "carries no timeout of
its own". It does: `AP_AHRS::update_flags()` clears both flags 1 s after
the last call, and `AP_GroundEffect` caps the takeoff window at 5 s
(`AP_GROUNDEFFECT_TAKEOFF_MAX_MS`).

What defeats the cap is its anchor, not the cap:

```cpp
// AP_GroundEffect.cpp
if (!throttle_up && land_complete) {
    _state.takeoff_time_ms = tnow_ms;      // re-stamped every cycle
```

and Copter supplies

```cpp
// ArduCopter/baro_ground_effect.cpp
const bool throttle_up = flightmode->has_manual_throttle() && channel_throttle->get_control_in() > 0;
```

`has_manual_throttle()` is false in ALT_HOLD, so `throttle_up` is false
there whatever the stick does, the timer is re-anchored every cycle, and
`max_timeout` never expires. A copter armed and idling in ALT_HOLD holds
`takeoff_expected` indefinitely. Before this change a genuinely failed
baro was masked for the whole time.

This extends the note in README.md ("in Stabilize the outer gate can also
close 5 s after the first throttle"): in Stabilize it can, in ALT_HOLD it
cannot.

Fix: the suppression now runs at most
`gndEffectHgtResetSuppressMax_ms` = 5000 from when it first engages, the
window cleared when both flags clear. Because the suppression re-stamps
`lastHgtPassTime_ms`, the practical effect is that one suppression cycle
is allowed and the next timeout resets.

## Review point 2: the resetHeightDatum() narrowing belongs to #32768

The review flagged `resetHeightDatum()` newly rejecting BEACON and
EXTNAV as an undocumented behaviour change in this PR. It is
`d290a65f78 AP_NavEKF3: restrict when the height datum reset is
performed`, in #32768's series. The review diffed #32972 against master,
which swallows the base. The 73 lines of quadplane.py it cited are from
the same place (#32768's update_home AMSL test, unrelated to ground
effect). Nothing changed here for it.

## Review point 4: the vehicle gate does cover quadplane VTOL

Marked unverified in the review. `Plane::update_fly_forward()` sets
`fly_forward(false)` whenever `quadplane.in_vtol_mode()`, and again for
`in_assisted_flight()`, so `assume_zero_sideslip()` is false and
`!assume_zero_sideslip()` passes. The gate excludes a quadplane only once
it is in forward flight, or a tailsitter in `is_in_fw_flight()`. That is
the intent.

## Key finding 4: GLOBAL_POSITION_INT.relative_alt is the baro, not the EKF

This is a measurement hazard for every test in this area, and it cost a
worthless test before it was caught.

```cpp
// AP_AHRS.cpp, get_relative_position_D_home()
if (!get_relative_position_D_origin(originD) || !_get_origin(originLLH)) {
    ...
    posD = -AP::baro().get_altitude();
```

`GCS_MAVLINK::global_position_int_relative_alt()` calls that, and
`get_relative_position_D_origin()` fails while the EKF vertical position
is unhealthy - which is `!hgtTimeout && filterHealthy && !hgtNotAccurate`
(`AP_NavEKF3_Control.cpp:794`). So exactly when a height-failure test is
doing its work, the MAVLink altitude silently becomes the raw barometer.

Measured: the first cut of `BaroGroundEffectResetSuppression` asserted on
`relative_alt`, reported a clean reset to -21.685 m, and **passed
identically with the bound compiled out**. `XKF1.PD` for the same run sat
at 0.01 for the entire 42 s the vehicle was armed, on both cores. The
test had been reading the barometer through the fallback for the whole
period and calling it a height reset.

`LOCAL_POSITION_NED.z` has no such fallback: `send_local_position()`
returns without sending when `get_relative_position_NED_origin_float()`
fails, so the message is absent rather than substituted. The test now
uses it.

README.md's "watch XKF1.PD" reproduction advice is right for this reason;
anything driven off MAVLink altitude is not.

## The new autotest and its A/B

`BaroGroundEffectResetSuppression` (Copter): `SIM_BARO_GEFF_M=30`,
`DISARM_DELAY=0`, ALT_HOLD, armed and left at idle.

Why 30 m: the sim applies `geff * (1 - h_agl/2)` while throttle > 0, and
on the ground `h_agl` is about 0.55 m, so the baro reads 21.69 m low.
After the ground-effect innovation shift (`gndBaroInnovFloor + gndMaxBaroErr`
= 3.5 m at the default DZ) the innovation is about -26.5 m against a
gate of `sq(5) * (P[9][9] + 16)`, i.e. about 400. Measured `XKF4.SH`
settled at 1.06, just over the 1.0 threshold, so the gate fails
continuously and `hgtTimeout` (10 s with GPS vertical velocity) fires for
real. This is the only way to reach the suppression branch;
`BaroGroundEffectAtTakeoff` cannot, because its held reference keeps the
innovation inside the gate.

| build | `LOCAL_POSITION_NED.z` | result |
|---|---|---|
| with the bound | holds ~0, then 21.70 m held 5 s | PASS |
| bound compiled out | 0.009 m indefinitely | FAIL |

The failing arm is what makes the test worth having. Compiling the guard
out and re-running is now the standard check for a new test here.

## Key finding 5: the pre-takeoff anchor can engage in mid-air

Prompted by the review's flag-gating instinct, aimed at a different
flag.

The anchor's fourth condition is `dal.get_time_flying_ms() == 0`. That
resolves to `!likely_flying` (`AP_Vehicle.h:175`), and on Copter
`likely_flying` is set only from `!ap.land_complete`
(`land_detector.cpp:249`). `land_complete` is forced true by a mid-air
disarm and, once armed again, is cleared only by high throttle output
(`land_detector.cpp:77`). It is the same flag that made #32768 add
`ap.disarmed_in_air`, and the anchor has no equivalent.

Instrumented `fusingGndEffectHgtRef` transitions and flew a 500 m
takeoff, Stabilize, throttle down, mid-air disarm, re-arm while falling:

```
DBG IMU0 gndEffRef=1 toff=1 tdwn=0 tfly=0     <- at the re-arm, in the air
   ... ~9 s of free fall at 17 m/s ...
DBG IMU0 gndEffRef=0 toff=0 tdwn=0 tfly=0
```

So the anchor does engage in flight, and held a reference that was about
150 m stale by the time it released. No height error resulted - the
innovation gate rejects a reference that far out, and the estimate
tracked the 476 m fall to within 1.4 m throughout on IMU plus GPS
vertical velocity.

The exposure was in the margin, not the outcome. `hgtTimeout` needs 10 s;
the anchor released at about 9 s. Had it persisted past 15 s (timeout
plus the new suppression window), `ResetHeight()` would have reset onto
`hgtMea`, which is the stale reference, for a 150 m error. The new
suppression bound is what makes that reachable at all, so it is a hazard
this PR introduced. What released `takeoff_expected` at 9 s was not
established - the anchor logic above says the timer is re-stamped every
cycle - so the 1 s margin is observed, not understood, and not something
to rely on.

Fix: drop the reference once its own innovation is too large.

```cpp
if (fusingGndEffectHgtRef &&
    fabsF(stateStruct.position.z - posDownGndEffectRef) > frontend->gndEffectHgtRefInnovMax_m) {
    fusingGndEffectHgtRef = false;
}
```

`velPosObs[5]` is `posDownGndEffectRef` while the reference is in use, so
that difference *is* the reference's innovation; the guard drops it
exactly when the height gate would reject it. No new state, no timer.

Measured after the change, same flight profile: releases at `innov=5.6`,
well under a second into the fall, with `toff` still 1 - released by the
guard, not by the flag. The on-ground path is unchanged (`innov=0.0` at
engage, normal release on `tfly`).

Coverage gap, deliberate: the bad outcome was never reproduced, because
the anchor released before 15 s in every run. The guard rests on the
mechanism and on the release measurement above, not on a reproduced
failure. A test would need the anchor held past 15 s, which needs a fall
longer than SITL gave from 500 m.

## Regression set

Run against the rebased branch after each change:
`BaroGroundEffectAtTakeoff`, `BaroGroundEffectResetSuppression`,
`HeightDatumKeptOnMidairRearm`, `BaroDriftClearedAtArm` - all pass.

## Commits added

Left as `fixup!` commits for review rather than squashed:

| fixup of | change |
|---|---|
| `AP_NavEKF3: suppress ResetHeight during baro ground effect` | 5 s bound on the suppression window |
| `autotest: add BaroGroundEffectAtTakeoff test` | `BaroGroundEffectResetSuppression` |
| `AP_NavEKF3: hold the pre-takeoff height during ground effect spool-up` | drop the reference on its own innovation |

## Still open

- The takeoff-command gap (README.md finding 1) is unchanged: the anchor
  still ends at the first real throttle in most configurations, and there
  is still no test for it.
- The parameter description still does not say that a negative
  `EK3_GND_EFF_DZ` assumes a rangefinder or other anchor (README.md
  finding 2).
- `AIReview` is on the PR, but nothing in `.github/workflows/` reads it;
  the report is produced by the external dev-call batch at
  uav.tridgell.net, so a push does not trigger a re-review.
