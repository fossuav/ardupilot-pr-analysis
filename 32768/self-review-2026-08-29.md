# Self-review and simplification (2026-08-29)

A `/pr-review` pass over the PR branch before re-requesting review, with the
fixes it led to. The arm-only conclusion in `analysis.md` stands; what changed
is everything that had grown around it. All numbers are from SITL runs on a
clean worktree build of the branch.

## Outcome

| | before | after |
|---|---|---|
| commits | 37 | 11 |
| files / lines | 28 / +738 -130 | 15 / +288 -39 |
| vehicle code touched | Copter, Plane | Copter |
| new parameters | `HGT_RESET_ALT`; `HOME_RESET_ALT` semantics and default changed | none |
| DAL / Replay | `RHGT` and `RHG2` messages, two handlers | unchanged |

Series now on `pr-baro-drift-minimum` (320f53ce01):

```
AP_NavEKF3: report the public origin height from getOriginLLH
AP_NavEKF3: leave EKF_origin.alt alone in resetHeightDatum
AP_NavEKF3: only reset height datum with baro or GPS height source
AP_NavEKF2: only reset height datum with baro or GPS height source
AP_NavEKF3: refresh on-ground references in resetHeightDatum
AP_AHRS: refresh published state after resetHeightDatum
Copter: clear baro drift at arm time via height datum reset
autotest: add Copter baro-drift-at-arm and rearm AMSL tests
autotest: relax Clamp altitude lower bound for baro noise
autotest: relax heli StabilizeTakeOff bound to match PosHoldTakeOff
autotest: add QuadPlane update_home AMSL regression test
```

Every C++ commit builds on its own; the mechanical gate (whitespace, flake8,
astyle on added lines, prefixes, ASCII) is clean.

## What the review found

Three must-fix items and eight should-fix. The ones that changed the design:

**Plane's home froze after a >10 m elevation change.** The branch changed
`HOME_RESET_ALT` from 0 to 10 and gated `set_home()` on a GPS-vs-origin
displacement. `AP_Arming_Plane::arm()` only forces home to the current
location when `update_home()` returns true, so after landing at a different
elevation home stayed at the takeoff site. QuadPlane SITL, VTOL landing 160 m
below the origin, on the ground: altitude above home **-160.3 m** with the
branch default, **0.0 m** with `HOME_RESET_ALT=0`; AMSL 5.0 m in both. Plane's
NAV_TAKEOFF completion, RTL altitude, fence and QuadPlane throttle suppression
are all home-relative. The freeze bought nothing for AMSL. Plane vehicle code
is now back at master.

**The origin-vs-GPS tolerance gate was redundant.** `getPosD()` reports
`position.z + (public_origin.alt - ekfGpsRefHgt)`. The full reset zeroes
`position.z` and re-anchors `ekfGpsRefHgt` to GPS altitude, so with GPS the
reported height above origin already loses the drift and keeps a real
elevation change without any gate. The Kalaupapa re-arm test gives identical
numbers with `HGT_RESET_ALT` at 10 (skip) and 0 (full reset): AMSL 76.3 m,
XKF1.PD 89.07 m on both sides of the arm. Without GPS the gate cannot
evaluate (`gpsGoodToAlign` false) and always fell through to the full reset.
With the gate gone, `HGT_RESET_ALT`, the Plane changes, the DAL/Replay
messages and the AHRS float plumbing all went with it. This also answers the
open review question about moving the parameter into common code.

**Intermediate commits did not build or run.** 73a825a9bb declared
`resetHeightDatum(float)` twice in `AP_AHRS_NavEKF3.h` (six commits broken
until 77b0057284); arducopter.py carried literal conflict markers for four
commits; the new tests called `delay_sim_time()` without the mandatory
`reason` until the last commit. Several bodies described changes not in their
diff or reversed by a later commit. Rebuilt as the series above.

**Two test relaxations hid measured regressions** - see the heli finding
below; the 0.2 m BaroDriftClearedAtArm bound was restored to 0.1 m (measured
0.023 m and 0.000 m with 9.2 m of drift injected).

## New finding: the reported origin was not consistent with posD

Removing the gate made `FarOrigin` climb without bound after the arm-time
reset. Instrumented, not inferred: with an origin set by
`SET_GPS_GLOBAL_ORIGIN` before the filter starts, `common_origin_valid` is
cleared by the filter re-initialisation and never restored (the core's
restore-from-public-origin path returns early because `validOrigin` is already
set). `NavEKF3::getOriginLLH()` then falls through to the core, which reports
the corrected reference height `ekfGpsRefHgt`, while `getPosD()` is referenced
to the public origin.

```
                     origin alt   local z   AMSL    origin - z - AMSL
FarOrigin pre-arm      1466.3       0.0    1466.3       0.01
FarOrigin post-arm      584.1     882.2     584.1    -882.2      <- inconsistent
Kalaupapa post-arm      165.3      89.1      76.3       0.01     <- common_origin_valid set
```

The takeoff target converted through the reported origin (584) while the
controller flew on posD (882 below it). This is reachable on master with a
Plane periodic reset; Copter had simply never reset on this arm path. Fix:
the frontend always reports the public origin height (taking the location
from the primary core so nothing is reported before a core has an origin).
The re-arm test now asserts `origin - z == AMSL` on both sides of the arm
(mismatch 0.01 m) and FarOrigin passes.

A first attempt fixed `getPosD()` instead (drop the public/reference term).
That passed FarOrigin and failed the Kalaupapa consistency check - the term is
exactly what keeps posD consistent with the fixed public origin in the normal
GPS-origin case. Recorded here because it looked right for an hour.

## Heli StabilizeTakeOff: the mechanism was baro recalibration noise

61f49a04c4 loosened the bound from 0.1 m to 1.0 m citing "baro noise from
rotor wash". SITL's baro has no downwash model. Measured after the 20 s runup:

| configuration | post-runup altitude |
|---|---|
| reset at arm, default `SIM_BARO_RND` 0.2 | -0.081, -0.118, -0.118 m |
| reset at arm, `SIM_BARO_RND` 0.2 explicit | -0.194 m |
| reset at arm, `SIM_BARO_RND` 0 | 0.008 m |
| no reset (home locked) | 0.005 m x3 |

`AP_Baro::update_calibration()` re-zeroes from a single pressure sample, so
the post-arm zero carries one sample of baro noise and the EKF settles on it
over ~10 s (Plot E). `copter.parm` sets `SIM_BARO_RND 0`, which is why the
Copter tests hold 0.1 m and the heli does not. The 1 m bound stays, matching
PosHoldTakeOff, with the message corrected.

![E](plots/E_heli_baro_recal_noise.png)

## Behaviour to know about

- Reported origin (`GPS_GLOBAL_ORIGIN`) does not move at a reset. With GPS
  the drift comes out of height above origin.
- With a valid origin and no GPS, the reset carries the old height into
  `ekfGpsRefHgt`, so AMSL and height above origin are unchanged and the drift
  stays in them (XKF1.PD -9.12 m before, -9.06 m after). Master's
  `EKF_origin.alt += oldHgt` had the same effect. Only the baro calibration,
  buffers and vertical velocity are reset there.
- A mid-air re-arm with unlocked home (rudder disarm in a manual-throttle
  mode) does a full reset airborne: for copters the EKF's `onGround` is
  `!motorsArmed`. Master already moved home in that case. Documented, not
  guarded; gating on `onGroundNotMoving` would skip the reset in wind.
- The terrain reference is re-taken after the reset; the base class captures
  it before Copter's arm code runs.

## Corrections to earlier notes in this archive

- `design-notes.md` section 2 calls Plane's GPS gate on the periodic reset a
  bug. `analysis.md` reversed that (the gate is protective) and that is the
  position that stands. The convergence gate and interval design in
  `design-notes.md` no longer exist in any branch.
- The June PR description said the Kalaupapa test covers a "~500 m" cliff;
  the site is 165 m above the sea. Commit messages saying HGT_RESET_ALT "0
  uses a 10 m default" were reversed by later commits in the old series.
- The 0.1 m post-arm bar "occasionally tripped" on the periodic build, not on
  arm-only.

## Test results on the final series

All passing on the clean build: `BaroDriftClearedAtArm`,
`AmslAltPreservedOnRearmAtDifferentElevation`, `Clamp`, `EK3AccelBias`,
`EK3_AccelBiasInhibitOnGroundMoving`, `HomeAltResetTest`, `FarOrigin`,
`RudderDisarmMidair`, `GPSViconSwitching`, `AHRSSwitchBackendPositionReset`,
`EK3_OGN_HGT_MASK`, `EK3_OGN_HGT_MASK_climbing`, `CommonOrigin`,
`LoiterToGuidedHomeVSOrigin`, `Helicopter.StabilizeTakeOff` (x2),
`QuadPlane.AmslAltPreservedAfterUpdateHomeAtDifferentElevation`,
`Plane.EK3HeightDatumResetFlushesBuffers`. The EK3 accel-bias tests pass in
their master form; the "inject bias from boot" change from the periodic era
was dropped.

Not covered: hardware, non-SITL boards, a Replay run on a real log. The Codex
cross-check completed for the DAL/Replay slice only (usage limit); the other
slices have a Codex cold read but no verification of the findings.

## Reproduce

```
git checkout pr-baro-drift-minimum        # 320f53ce01
./waf configure --board sitl && ./waf copter && ./waf plane && ./waf heli
Tools/autotest/autotest.py --no-configure test.Copter.BaroDriftClearedAtArm,AmslAltPreservedOnRearmAtDifferentElevation,FarOrigin
Tools/autotest/autotest.py --no-configure test.Helicopter.StabilizeTakeOff
Tools/autotest/autotest.py --no-configure test.QuadPlane.AmslAltPreservedAfterUpdateHomeAtDifferentElevation
```

Build the vehicles in separate waf invocations: `./waf copter plane heli` in
one run failed the arduplane link with unrelated undefined symbols on this
machine, and linked fine run alone.

Plot E: `python3 plots/make_plots.py` from `32768/`, data in `data/heli/`.
