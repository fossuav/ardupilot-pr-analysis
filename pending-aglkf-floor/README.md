# AGL KF: clear the velocity when the height rests on its floor

**Not yet opened.** Rename this directory to the PR number when it is, and move
the row in the root README with it.

Two commits on `SmallFastDrone-4.7.1-beta`, to be lifted onto master:
`8461433db6` (AP_NavEKF3, the fix) and `7433f71001` (autotest). It is a master
PR and not one of the AGL KF stack in flight: the clamp came in with the AGL KF itself, which the SFD base
carries as a merged upstream PR, and #33359, #33478 and #33507 all stack on top
of it. Numbers below were taken at `8461433db6` unless another commit is named.

## Summary

`UpdateAglKf()` clamps the AGL height to the on-ground range finder reading.
While the vehicle sits on the ground the prediction and the measurement are then
both the floor, so the innovation is zero, nothing corrects the velocity or the
bias states, and whatever bias error the filter picked up in its first seconds
integrates into the velocity for as long as the vehicle is there. It is unbounded
in ground time.

The clamp is one-sided, and that is the whole mechanism: an error that points up
lifts the height off the floor, restoring the innovation so the bias is
corrected; one that points down presses the height into the floor, where the
innovation dies and the error latches. The fix gives the downward side the
behaviour the upward side already had.

```cpp
-    // AGL cannot go below the on-ground sensor reading
-    aglKfH = MAX(aglKfH, rngOnGnd);
+    if (aglKfH < rngOnGnd) {
+        aglKfH = rngOnGnd;
+        aglKfV = MAX(aglKfV, 0.0f);
+    }
```

## Conclusion

Confirmed on four real flights, by Replay of the flight that exposed it, and by
a regression test that fails without it. Ready to open once the SITL prerequisite
below is settled.

## Key findings

### 1. The wind-up, and what it costs the takeoff (tier 1, SFD-O4 log9)

Over the 88 s between EKF start and lift-off, `XKFA.VAgl` ramped linearly from 0
to **-7.15 m/s** at about 0.084 m/s2, with `XKFA.Bias` frozen at **-0.0796** from
4.6 s onwards - which is the entire ramp rate. `Valid` stayed 1 and `HAglStd`
0.13 throughout: the filter was confident and wrong.

The takeoff pays for it. Four seconds go on unwinding that velocity, so `aglKfH`
held the 0.05 m floor through a climb to 3 m. `selectHeightForFusion()` fuses
`aglKfH` in place of the raw range finder while the range finder is the height
source, so the main filter's height rose at **0.22 m/s against a true 1.02 m/s**
(range finder +1.03 and baro +0.95 agreeing) and then stepped **+2.21 m** at
93.776 s when the source went back to baro. `getHAGL()` returns `aglKfH` too, so
AP_GroundEffect's `above_alt` release had no working height either and the
takeoff window latched 4.1 s against a `GNDEFF_TMO` of 2 s.

Independently confirmed by reconstructing the fused height measurement as
`XKF3.IPD - XKF1.PD`: 0.51 to 0.60 m flat through the whole climb, which is
`aglKfH` at 0.05 plus the 0.46 m arm datum, then jumping to the real height at
the switch.

### 2. Replay of log9, code before against after (tier 1b, same sensor stream)

| metric | before | after |
|---|---|---|
| samples with the height on its floor and velocity < -1 m/s | c0 1313, c1 1341 | c0 **0**, c1 2 |
| worst floor velocity | -9.25 / -7.45 m/s | **-0.71** / -2.22 m/s |
| unexplained one-sample height move | 2.17 / 2.13 m | **0.43** / 1.94 m |
| EKF height slope 89.9-92.6 s (truth +1.02 m/s) | +0.22 m/s | **+0.82 m/s** |
| height error vs range finder, 89-96 s | mean -0.93, worst -2.39 m | **-0.40 / -0.72 m** |
| optical flow velocity resets | 7 | 5 |

`plots/aglkf_1_replay_ab_log9.png`. This is the honest before/after: one flight,
identical sensor stream, only the code differs.

### 3. The same bias error with the fix in (tier 1, log11 and log12)

log11's bias froze at **-0.0806**, within a thousandth of log9's -0.0796, and its
velocity stayed at **-0.0009 m/s** over 62 s rather than running to -7.2. That
residual is one prediction step of the frozen bias (0.08 x 12 ms = 0.00096),
which is exactly what the clamp leaves behind. Same bias error, opposite outcome.

log12 is the strongest control: a **487 s** ground dwell, 5.5x log9's. Bias froze
at -0.0154, `VAgl` was 0.0000 at arming and worst -0.0120 across 4852 pinned
samples. Unfixed, that bias integrates to **-7.5 m/s**.
`plots/aglkf_2_ground_windup.png` is log9 against log12.

log10 and log14 also carry the fix with no wind-up and no height step.

### 4. What the fix does not do: in-flight aiding churn (tier 1b, Replay of log17)

log17 is an acro flight on the fixed build whose raw numbers invite a wrong
claim: flow aiding stop/start pairs fell from log9's 16 to 4 and flow velocity
resets from 7 to 1. That is the flight profile, not the fix. log17 spent 39.4 %
of its acro past the flow tilt limit against log9's 66.7 %, at a median 17.8 m
against 26.3 m, with 73.6 % above the 15 m range finder cap against 90.1 %.

Replaying log17 through both code versions removes the profile entirely - and
log17 flew with `EK3_PRIMARY` 0, so the flow lane was a passenger and the
trajectory was GPS-driven, which is the condition Replay needs to be exact:

| on log17's own sensor stream | without the fix | with it |
|---|---|---|
| AGL KF floor velocity, core 0 / core 1 | **-5.92 / -6.00 m/s** | **-0.06 / -0.06** |
| samples on the floor below -1 m/s | 831 / 769 | **0 / 0** |
| optical flow velocity resets | 3 | **1** |
| aiding-mode transitions, core 0 / core 1 | 2 / 6 | 2 / 6 |
| AID_RELATIVE / AID_NONE, core 1 | 88.5 % / 11.1 % | 88.5 % / 11.1 % |
| AGL KF valid, core 1 | 70.8 % | 70.8 % |
| peak excursion, core 1 | 285.0 m | 286.8 m |

**The aiding-mode transitions are identical**, and so is how much of the flight
the flow lane spent relative-aided. The churn in acro is the flow tilt limit and
the range finder ceiling, which this change does not touch, and the PR must not
claim it. What moves is the ground wind-up, which is what the fix is for, and the
flow velocity resets - 3 to 1 here, 7 to 5 on log9.

`aglKfValid` is unchanged because it tracks range finder fusion recency, not the
velocity state.

### 5. Not a recent regression (tier 1)

log6 and log7, on firmware `797f6854`, reach `XKFA.VAgl` -6.5 m/s. The behaviour
is as old as the AGL KF.

## Measured and rejected

| Alternative | Why not |
|---|---|
| Bound `aglKfV` to a fixed range instead of clearing it at the floor | Caps the wind-up without stopping it. The takeoff still starts from a large wrong velocity, so the height still lags and still steps, just less. |
| Also clear the velocity at the measurement-update clamp | Left alone deliberately. There the innovation is real and the correction is informed; clamping is only enforcing the physical bound on the output, and killing a legitimate descent correction there would be a new fault. The 2 residual samples on core 1 in the Replay "after" column come from this path and are in flight, not on the ground. |

## Rejected finding, recorded so it does not come back

A session concluded the wind-up is **intermittent**, keyed on the sign of the
early velocity error, citing log9 and log10 as a same-firmware natural A/B. It is
wrong and was committed before it was caught. log10's binary was built from an
uncommitted tree, so its banner reported the last commit (`ee3bda1f`) rather than
what was compiled: log10 *had* the fix, and there was no control flight. The
one-sidedness of the clamp is real and is why the fix works, but nothing supports
calling the bug rare - log9, log6 and log7 all wound up.

The general lesson, which cost a day: **a version banner dates the tree only as
far back as its last commit.** Check the build against the source timestamps
before reading a flight as a control.

## Still owed

- ~~The test's helpers are a prerequisite~~ - settled by stacking on #33507.
  `SIM_SONAR_OFFSET` is **not** a prerequisite, contrary to an earlier note here:
  master defines it (`AP_GROUPINFO("SONAR_OFFSET", 57, SIM, sonar_offset, 0)`)
  and the branch carries `4afd3b3524` only because the 4.7 base predates it. What
  master lacks is `xkfa_recent_mean` and `xkfa_peak_abs`, which arrive with
  #33507's range finder excursion test and need its bias-state code to pass.
  Rather than duplicate them, the PR branch carries #33507's seven commits
  cherry-picked **patch-identical**, so whichever merges first the duplicates
  drop out when the branch is replayed onto master. Verified rather than
  assumed: all seven patch-ids match the upstream originals (`72da83dea5ce`,
  `3d232028922a`, `2d7f8c8b3d39`, `526114696b0d`, `51fa15d07ed8`,
  `78f8068e1242`, `3e3f77500555`), which is the comparison git itself makes.
  #33507 already uses this pattern for its own decay commit against #33478's
  copy.
- **The ground-effect release timing is unmeasured by Replay**, which feeds the
  recorded `takeoff_expected` and so never exercises the release path at all.
  log10's "terrain offset reset from baro" fires 2.0 s after NOT_LANDED, exactly
  `GNDEFF_TMO`, where log9 never emits it; that message is latched on the ground
  effect clear edge, so its timestamp is the release. One flight, and the absence
  in log9 has more than one possible cause, so it is corroboration, not proof.

## Tests

`OpticalFlowAGLKfFloorVelocity` (`7433f71001`) is the regression test. It settles
the AGL KF on the ground, steps the reported range up 3 m and back down, and
asserts the velocity has not latched downward once the height returns toward the
floor.

**It fails without the fix**: -1.361 m/s against -0.0007 with it, so the -0.5
bound has an order of magnitude either side. The assertion is one-sided, because
an upward velocity lifts the height off the floor and corrects itself; a second
assertion checks the height came back down, since the velocity proves nothing if
the provocation never reached the clamp. The two builds differ only inside
`if (aglKfH < rngOnGnd)`, so the difference is itself proof the branch was taken.

Injecting an accelerometer bias was tried first and does not work: the main
filter learns it back out of `velDotNED` through the on-ground zero-velocity
fusion, so the residual the AGL KF would integrate disappears.

Sixteen Copter flow, AGL KF, ground effect and source-set tests pass at
`7433f71001`, including: `OpticalFlowAGLKalmanFilter`, `OpticalFlowFocusHeight`,
`FlowFocusHoldAfterLanding`, `FlowHeightMinTerrainPath`, `FlowCeilingDoesNotBackUp`,
`OpticalFlowLimits`, `OpticalFlowGPSLossAiding`, `OpticalFlowFallbackKeepsAbsolute`,
`FlowGyroZBiasNoYawReference`, `FlowAidingRestartsWithoutYawFusion`, and the three
`BaroGroundEffect*`.

## File map

| Path | What |
|---|---|
| `plots/aglkf_1_replay_ab_log9.png` | Replay A/B on log9, code before vs after |
| `plots/aglkf_2_ground_windup.png` | log9 against log12, the ground dwell |
| `plots/make_plots.py` | regenerates both |

No `data/`: every input is a real flight and this repo is public. The logs are
named above and resolved by `find_log.py`; their fingerprints are in the private
index named in REPLAY_LOGS.md.

## Reproduce

```sh
export AP_LOG_ROOTS=<wherever SFD-O4 lives>

# figure 2, straight from the flights
cd plots && ./make_plots.py

# figure 1 needs the Replay pair first, from the log-analyze skill
replay_sweep.py --label before --keep-dir /tmp/ab log9.bin   # tree without 8461433db6
replay_sweep.py --label after  --keep-dir /tmp/ab log9.bin   # tree with it
./make_plots.py --replay-before /tmp/ab/before-log9.bin.BIN \
                --replay-after  /tmp/ab/after-log9.bin.BIN
```

`replay_sweep.py` reports the floor-velocity and height-step columns in the table
above directly. Build Replay for **sitl** and check the build log names
`build/sitl/tool/Replay`: a board-configured tree builds a different binary while
the sweep runs the stale sitl one, which produced a null A/B that read as "the
change does nothing".
