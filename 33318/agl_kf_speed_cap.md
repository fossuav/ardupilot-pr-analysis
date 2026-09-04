# Related finding: the optical-flow speed cap ignores the 2-state AGL KF

Found while analysing log279 (the twitch). Separate from the AC_Loiter fix and
from the drag-model scaling discussion - it is a plumbing gap in EKF3 that makes
the twitch worse, and is probably its own small PR against the AGL-KF feature.

## Two height-above-ground estimators, two consumers

EKF3 has two estimates of height above ground when flying on optical flow:

- legacy single-state terrain offset `terrainState` (logged `XKF5.HAGL` as
  `terrainState - position.z`);
- the IMU-aided 2-state AGL KF (`aglKfH`/`aglKfV`, rangefinder + IMU, logged
  `XKF6`), gated by `EK3_OPTIONS` bit 3 (`AglKfForOptflow`). Its stated purpose is
  to "decouple optical flow scaling from errors in the main filter's vertical
  position state."

The flow path uses them inconsistently:

| consumer | code | estimator used |
|---|---|---|
| flow **velocity** scaling | `AP_NavEKF3_OptFlowFusion.cpp:337-338` | 2-state KF `aglKfH` (when option on + valid) |
| flow **speed cap** + nav-gain scaler | `AP_NavEKF3_Outputs.cpp:428,430` | legacy `terrainState` (always) |

`getEkfControlLimits()` returns the speed cap that reaches `AC_Loiter` via
`AP::ahrs().getControlLimits()` (`AC_Loiter.cpp:322`), where it becomes
`gnd_speed_limit = MIN(LOIT_SPEED, ekfGndSpdLimit)` (`AC_Loiter.cpp:327`) - the
denominator of the drag term (`AC_Loiter.cpp:350`). So even with the AGL KF
enabled, the cap (and the drag term that PR #33318 made visible in the
feed-forward) rides the drift-prone legacy estimator.

## log279 evidence

`EK3_OPTIONS = 24`, so bit 3 is on and the AGL KF was valid for the whole flight.
The two estimators over the Loiter:

| estimator | min | max | mean | notes |
|---|---|---|---|---|
| `XKF6.HAgl` (2-state KF, used for velocity) | 0.05 | 0.97 | 0.27 | smooth, valid 100%, tracks the rangefinder |
| `XKF5.HAGL` (terrainState, used for the cap) | -0.24 | 1.91 | 0.39 | noisy, goes negative, overshoots the 1.02 m sensor max |

So the velocity estimate position control consumes is correctly scaled by the
clean KF, but the cap swings on the noisy `terrainState`: `(FLOW_MAX-1)*HAGL`
ranges ~0.15-2.87 m/s and `drag_decel` snaps jab-to-jab with it. That cap noise is
a direct contributor to the twitch, on top of the over-large drag magnitude.

## Proposed change (small, surgical)

Make `getEkfControlLimits()` use `aglKfH` when `AglKfForOptflow` is enabled and
valid, mirroring the flow-velocity path, and share one height term between the
speed cap and the nav-gain scaler:

```cpp
// AP_NavEKF3_Outputs.cpp, getEkfControlLimits(), AID_RELATIVE branch
ftype heightAboveGndEst = MAX((terrainState - stateStruct.position[2]), rngOnGnd);
#if EK3_FEATURE_OPTFLOW_AGL_KF
if (frontend->option_is_enabled(NavEKF3::Option::AglKfForOptflow) && aglKfValid) {
    heightAboveGndEst = MAX(aglKfH, rngOnGnd);
}
#endif
ekfGndSpdLimit = MAX((frontend->_maxFlowRate - 1.0f), 0.0f) * heightAboveGndEst;
ekfNavVelGainScaler = 4.0f / MAX(heightAboveGndEst, 4.0f);
```

This de-noises the cap and stops it collapsing below physical (negative
`terrainState`). It does not change the drag *magnitude* - the cap is still treated
as a terminal velocity, which is the separate scaling issue - but it removes the
jab-to-jab variation in the brake. Gated entirely by `AglKfForOptflow`: with the
option off, behaviour is byte-for-byte unchanged.

## Status

Change applied locally on the 4.7-beta branch. The feature is compiled into SITL
(`EK3_FEATURE_OPTFLOW_AGL_KF = EK3_FEATURE_OPTFLOW_FUSION`).

SITL confirms:
- builds clean;
- no regression - GPS `ModeLoiter`, flow with the option off, and flow with the
  option on all pass and fly stably;
- the option-off / AGL-KF-invalid path is byte-for-byte the prior behaviour (the
  refactor shares one height term but `MAX(h, rngOnGnd)` then `MAX(h, 4.0)` is
  algebraically identical to the original for the nav-gain scaler).

SITL coverage: an earlier attempt never reached `aglKfValid` in the
optical-flow autotest config (no `XKF6` logged) and this branch was validated
by code review, option-off equivalence and log279 (AGL KF valid 100 %, clean
`XKF6`). Update: the #33484 and #33507 autotests reach `aglKfValid` in SITL
with `EK3_OPTIONS=8` (upstream bit 3) and `set_analog_rangefinder_parameters()`.
The earlier attempt most likely set the SmallFastDrone-branch bit (16). The
branch is therefore testable; the message is `XKFA` upstream (`XKF6` on the
SmallFastDrone branch).

#33569 makes the nav-gain constant tunable (`EK3_FLOW_GAIN_H`) but keeps
`terrainState - stateStruct.position[2]` as the height term, and #33568 gates
both outputs on reaching AID_RELATIVE. Neither adopts `aglKfH` here, so this
change still stands on its own and now also de-noises the scaler #33569
tunes. Candidate for a standalone PR against the AGL-KF feature rather than
part of #33318.
