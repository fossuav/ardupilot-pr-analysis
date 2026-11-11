# AGL KF: clear the velocity when the height rests on its floor


## 2026-11-10: a SITL landing that reproduces the coast (from #35077)

The touchdown coast that reproduced only erratically here (3 mm and
0.37 m in two runs) reproduces with master's AGL KF in #35077's landing
test, on branch `flow-hgt-min-on-ground` with `EK3_OPTIONS` 8. The leg is
ALT_HOLD with `PILOT_SPD_DN` 0.5 and `RNGFND1_MIN` raised to 0.2 once
airborne, as SITL's range finder reads 0 on the ground. The height read
0.48 m at touchdown and climbed to 0.86 m over 4.6 s, until the 5 s
timeout. Not yet run with this PR's coast stop. Details in
`../35077/README.md`.

## 2026-11-10: four touchdowns on a customer quad (tier 1)

Beta `7b00f3b5` (this PR's floor velocity clear and coast stop), one IMU,
ARK Flow with its range finder on DroneCAN. At all four touchdowns, logs
15, 16, 18 and 20 (1245450/43-47), the AGL KF held 0.10-0.13 m from the
range loss to the disarm: no coast. A -0.58 m/s velocity cleared within
0.5 s (log16, 284.7 s).

## 2026-10-07: rebased onto master and squashed to two commits (head `c3204a1836`)

Done for #33507, which is stacked on this PR and was approved on 2026-10-07
with a request to squash. #34457 itself has no approval yet (AP-Review
COMMENT).

Squash map (old commit -> new), for review comments and CI runs that cite
the old SHAs: #34457's 764e4d4399, 5b814ea367, 2ae32c99ce, 55bd80a81b ->
`371a25c015` (AP_NavEKF3); 32d62e6685, f8651ffaeb, 69add987bc, 52c6ffbe30
-> `c3204a1836` (autotest). #33507's 7a14003440, 87ad9d25ca, 3c61823f21,
5f7b34a19f, 5ff859ed28, 342d104874 -> `decedef717` (AP_NavEKF3);
b578d499cc, 78cfc5979f, e4b58c2504, cedaf68d1e, 4e858b1068, 28b59bd51b ->
`ac92f50e6d` (autotest). Backups: `pre-squash/pr-aglkf-floor-velocity-20261007`
(55bd80a81b), `pre-squash/pr-agl-kf-zbias-20261007` (28b59bd51b).

Checks: squashed on the old base `e204ca77a8` the trees equal the old heads
exactly; after the rebase each PR's own +/- lines are identical to before.
The one conflict was `AP_NavEKF3.h`, where master had changed `_options` to
`AP_UInt32` on the line above `_aglKfAccelBiasPnse`; kept master's type.
`AGL_ABIAS_P` (var_info2 index 12) collides with nothing. At the new heads:
OpticalFlowAGLKfFloorVelocity and OpticalFlowAGLKfNoCoastBelowMin pass on
#34457 alone; those and OpticalFlowAGLKalmanFilter pass on #33507; copter,
plane and Replay build; copter and plane build with
EK3_FEATURE_OPTFLOW_AGL_KF 0. Both were flight tested at their pre-squash
heads (in the SFD beta through refresh10), so squashing is allowed.


### Superseded before pushing: #34457 kept as five commits

The two-commit shape above was never pushed. #34457's message described
three separate EKF fixes, so they stay separate commits, each followed by
its test, in the original order (the floor test needs the decay gate, which
is what exposes the latch): `42de1d07f1` floor velocity clear (764e4d4399),
`8e40047bf8` decay after a fusion gap (5b814ea367), `2622d00aba` floor test
(32d62e6685, its registration indent fixed in place), `d3df572550` coast
stop (2ae32c99ce + comment 55bd80a81b), `ec3c439aec` coast test
(f8651ffaeb + 69add987bc + 52c6ffbe30). #33507's own two follow:
`cc269a57cf` (AP_NavEKF3), `d48bf30698` (autotest). Final trees equal the
two-commit versions tested above; on the old base they equal the old heads.
Every commit builds and is flake8-clean, and the floor test passes at its
own commit. Heads: #34457 `ec3c439aec`, #33507 `d48bf30698`, force-pushed
2026-10-07; reply to the approval:
https://github.com/ArduPilot/ardupilot/pull/33507#issuecomment-6039192730

## 2026-10-02 second review round: the landed hold replaced by a coast stop (pushed as `18276345bf`)

Supersedes the landed hold recorded below. A second Codex cold read
confirmed two must-fix rows against it: `takeoff_expected` and the land
detector are not independent in an automatic throttle mode (Copter passes
`throttle_up` only for manual throttle modes, so a stuck land detector
keeps re-anchoring AP_GroundEffect's timer and holds `takeoff_expected`
latched), and keeping the filter valid stopped the 5 s
re-initialisation while the covariance kept being predicted. Chosen
instead (the user's option A): with the sensor out of range low, no range
sample for 200 ms and the main filter not climbing faster than 0.25 m/s,
zero `aglKfV`. No landed flag, no validity change; the timeout and
re-initialisation are master's.

Replay at the head against `7505d332d9`: after touchdown, while still
valid, the height peaks at 0.06-0.17 m where it coasted to 0.16-1.14 m
(log27, log28); every in-flight value and every takeoff unchanged on
log22, 25, 27, 28 (log22's differences are all on the ground while both
arms were already invalid). `OpticalFlowAGLKfNoCoastBelowMin` replaces
the landed test: a 1 m range step in a hover, then `RNGFND1_MIN` above
the reading; height rise 0.357 m without, 0.000 m with. A landing provoked
the coast only erratically in SITL (3 mm and 0.37 m in two runs).

Cost, accepted: a touch-and-go re-initialises the filter, so on #33507
the bias variance reopens to 1.0 at the second takeoff (beta Replay of
log28: 0.977, against 0.018 with the hold), the same state every first
takeoff starts from; flow lane tracking 0.67 against 0.66 m RMS.

`plots/aglkf_landed_hold.png` shows the abandoned hold and is not in the
description.

## 2026-10-02 /pr-review of the landed hold: reworked (pushed as `7381308bf6`)

Squashed and pushed 2026-10-02 as `7381308bf6` (fast-forward). The PR description is not yet updated.

REQUEST CHANGES on `7568122335`, from a Codex cold read, confirmed:
`takeoff_expected` stays latched up to 5 s after liftoff, so a range
finder failing low in a slow hover then would pin the AGL height in
flight, and the comment claimed it could not. The landed test is now
`takeoff_expected` and `time_flying_ms == 0` together. Neither alone is
reliable: the land detector stayed set through a whole tester C's copter flight
(the private analysis repo), while
`takeoff_expected` is released by AP_GroundEffect's own timer within 5 s
of throttle-up whatever the land detector says, so in flight both must be
wrong at once and only in that window.

Codex also said refreshing the fusion time stamp suppresses the
re-initialisation at the next takeoff. Measured by Replay at this head
against `7505d332d9` (core 100/101 decoded by hand), flow lane AGL height
against the range finder over the first 20 s of each takeoff:

| takeoff | old head | hold, every held filter kept valid | hold, only a valid one kept valid |
|---|---|---|---|
| log22 129.4 s | 0.150 / -0.29 | 0.216 / -0.43 | 0.150 / -0.29 |
| log25 51.7 s | 0.175 / -0.31 | 0.237 / -0.47 | 0.175 / -0.31 |
| log27 43.1 s | 0.035 / -0.06 | 0.065 / -0.14 | 0.035 / -0.06 |
| log28 36.9 s | 0.110 / -0.17 | 0.156 / -0.30 | 0.110 / -0.17 |
| log28 88.8 s (touch-and-go) | 0.041 / +0.12 | 0.039 / +0.12 | 0.039 / +0.12 |

(RMS / worst, m.) On master the filter has already timed out armed on
the ground before a first takeoff, and re-initialising from the first
reading tracked better than continuing from the held state. The hold now
refreshes the time stamp only for a filter that is still valid, which is
the touch-and-go it is for. Landings unchanged: log27 1.52 -> 0.05 m,
176 -> 0 invalid; log28 68 -> 0 and 159 -> 0 invalid.

The test now requires the landed samples to cover the window and every
height to be finite on the floor; without the hold it failed again (93 of
112 invalid, coasting to 0.37 m in that run).

## 2026-10-02: hold the AGL KF on the ground after a landing (since pushed, see above)

Branch `pr34457-port` on `7505d332d9`: `7568122335` "AP_NavEKF3: hold the
AGL KF on the ground after a landing" and `45852b4417` "autotest: check the
AGL KF holds the ground while landed". #33507 is restacked on top of it
(`pr33507-port`). Not pushed; needs a `/prepare-for-push` grant.

A range finder below its minimum delivers no reading, so after a landing
the AGL KF coasts on the velocity the touchdown left: SFD-O4 log27
(`STAT_BOOTCNT` 564) climbed from 0.1 to 1.61 m sitting armed on the ground
and went invalid after 5 s; on log28 (566) the touch-and-go then took off on
a re-initialised filter with the bias std back at 0.98. The hold puts the
height on the floor with zero velocity, and keeps the filter valid, while
`takeoff_expected`, the sensor reports out of range low, no range sample is
arriving and the main filter's vertical velocity is under 0.25 m/s.

Two earlier versions, measured on the beta by Replay and discarded: without
the last two terms the hold also fired at a normal first liftoff, where the
sensor stays below its minimum for a few hundred ms after the vehicle
moves, and wiped the IMU-sensed climb (flow lane height moved up to 0.77 m
on log22). With them log22 is byte-identical and the remaining effect is a
few samples at the start of a slow climb (0.07 m of AGL height on log25).

The out of range low time stamps (`rngOutOfRangeLowTime_ms`, its reset and
its update in `readRangeFinder()`) are the same lines #34292 adds, so the
two merge without a conflict in them.

Replay (the beta's identical hold, core 101): log27 after landing 1.61 ->
0.05 m, 176 -> 0 invalid samples; log28 bias std one second into the second
takeoff 0.977 -> 0.018. Flown on log30 (`f547e6f7`): four landings, AGL
height exactly 0.050 m and valid throughout each, every later takeoff with
its learnt bias.

`OpticalFlowAGLKfLandedHold` (new): `RNGFND1_MIN` 0.5 so the sensor reads
out of range low on the ground, fly, land, sit armed 12 s. Without the hold
the filter went invalid 2.4 s after touchdown (100 of 114 landed samples);
with it 0 of 110, height at most 0.100 m. SITL leaves almost no touchdown
velocity, so the 1.6 m coast does not reproduce; the timeout does.
`OpticalFlowAGLKfFloorVelocity` still passes, and both pass on the
restacked #33507.

Figure: `plots/aglkf_landed_hold.png`, from `plots/make_landed_hold_plots.py`
(log27 and log28 flown, against Replay with the hold).

## Restacked 2026-09-30 at `7505d332d9`: now on master, #33507 on top

AP-Review's 2026-09-30 round on #33507 found the decay gate (`df8c4cdb0b`, then
#33507's first commit) leaves the floor velocity unbounded without this fix, so the
stack was reversed. This PR now sits on master with three commits: the velocity
clear (`c824700eaa`), then the decay gate (`3cb6b8b75c`, reworded "after a range
finder fusion gap"), then the test (`7505d332d9`). The clear lands first so no
commit carries the gate without it. Title now "AP_NavEKF3: AGL KF velocity decay and
floor wind-up".

The test's -0.5 bound did not survive the move. Without the bias state underneath,
the unfixed velocity latches at -0.4311 / -0.4375 m/s (two runs) and the test
passed on the broken code. Bound now -0.1: +0.0001 with the clear, -0.437 without
(fails), -0.0010/-0.0011 with #33507 on top, where the unfixed value is -3.5.

The commit messages no longer cite `aglKfB`, and the flight figures in the
description are labelled as from a build carrying #33507's bias state; every flight
here was. The 0.62 -> 0.18 m/s decay figure was measured on #33507's tree.

**Open as [#34457](https://github.com/ArduPilot/ardupilot/pull/34457)**,
opened 2026-09-21 from `pr-aglkf-floor-velocity` at `9b74c85f80`.

2026-09-29: two local commits on top, **not pushed**: `d42f9dc86d`
(AP_NavEKF3, no bias learning while resting on the floor) and `6bb08e8f98`
(autotest). They answer section 4(a) of the 2026-09-22 automated review. See
section 6. The PR description has not been updated for them yet.

**Pushed 2026-09-29 at `5a086b2cd9`**, stacked directly on #33507 at
`b8ee18a23e` (newer master, `b832113b10`). The floor bias gate and its test
moved to #33507 before the push, where the bias state lives, as `129d602eb6`
and `b8ee18a23e`; `d42f9dc86d` and `6bb08e8f98` below are those commits as
they first stood here. This PR's own two commits are now `ee7a6b42d0` (the
velocity clear, with the clamp made NaN-safe as `!(aglKfH >= rngOnGnd)`) and
`5a086b2cd9` (the test). Description rewritten and the AP-Review round
answered the same day.

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

### Superseded 2026-09-30 by a check of what `797f6854` carries

`797f6854` already has the decay gate (`imuSampleTime_ms - lastAglRngFuseTime_ms >
aglKfRngGapMax_ms`, OptFlowFusion.cpp:996 there), so log6 and log7 show the wind-up
on a gated build, not on master. On master the ungated decay runs on about three
steps in four and keeps the floor wind-up small (AP-Review's model: -0.2 m/s after
88 s at 0.08 m/s/s, against -7 with the gate). The -6.5 m/s above is left as
measured; what it does not show is that master winds up. The claim was dropped from
the PR description.

### 6. The bias the floor froze, and what it costs after liftoff (tier 1 and 1b, SFD-O4 log18-21)

Four more flights on `5adc2ea0`, which carries `8461433db6`. The velocity fix
holds: ground dwells of 63-97 s, bias frozen at -0.058 to -0.065, `VAgl`
within -0.009 to +0.037 m/s on every core, no takeoff step. The acro churn on
log18, 20 and 21 (15, 14, 14 aiding stops) tracks the tilt limit, as section
4 says: in the 5 s before each of the 43 stops, tilt allowed flow fusion at
most 18 % of the time.

log19, a gentle LOITER takeoff to 2.2 m, shows what the fix leaves. The flow
lane (core 1, no GPS, AGL KF velocity fused as velD under `EK3_OPTIONS` bit 4)
sank to **1.0 m** below baro, GPS, the range finder and core 0 after the
climb, and took 20 s to come back. `HAgl` was flat at 2.0 m while `VAgl` read
-0.2 m/s for 5 s, and the bias moved -0.062 -> +0.005 over 10 s of flight.

The bias was never a ground residual. It was fitted to the filter's own
start-up: from 2.27 s after boot (std 1.0) to 5.1 s it went 0 -> -0.062
while the AGL height rose 7 mm at up to 0.03 m/s. The height then pinned to
the floor, and with both the height and its measurement at `rngOnGnd` the
update kept running at full bias gain on a zero innovation: std 0.20 -> 0.016
by liftoff with nothing learned. log18 is the same (-0.064). This is the
defect the review's section 4(a) named, and the confidently wrong bias its
notes predicted "would matter if it were ever extended to fly afterwards".

`d42f9dc86d` sets the bias gain to zero while both are on the floor (a NaN
height counts as on the floor). The Joseph form update stays consistent for
any gain. Replay at `5adc2ea0`, which reproduces the flown cores to 0.000 m,
core 101 on log19:

| | flown | `EK3_AGL_ABIAS_P` 0.3 | zero bias gain on the floor |
|---|---|---|---|
| worst height gap to core 100 | -1.00 m | -0.30 m | +0.28 m |
| gap mean / RMS | -0.26 / 0.42 m | 0.00 / 0.09 m | +0.14 / 0.17 m |
| AGL KF height error, level, RMS | 0.083 m | 0.042 m | 0.037 m |
| AGL KF velocity error, RMS | 0.074 m/s | 0.047 m/s | 0.042 m/s |
| bias std at liftoff | 0.016 | | 0.233 |

Logs 18, 20 and 21 are unchanged except log21's worst early sag, 2.87 ->
1.96 m. log5 and log7, on `797f6854`, keep worst ground `VAgl` at -0.005 to
-0.006 m/s with and without it, so the section 3 behaviour is untouched.
Those two stand in for log9 and log12, which did not resolve on the machine
used on 2026-09-29.

log18's level AGL KF error reads 0.69 -> 0.80 m under both 0.3 and the gate.
All of it is one 53-sample window at +139 to +149 s, RTL straight after acro,
where the bias swings to -0.57 in every arm and the error is 2 m regardless.
It is a separate post-acro effect, not a cost of either change, and is not
explained yet.

## Measured and rejected

| Alternative | Why not |
|---|---|
| Bound `aglKfV` to a fixed range instead of clearing it at the floor | Caps the wind-up without stopping it. The takeoff still starts from a large wrong velocity, so the height still lags and still steps, just less. |
| Raise `EK3_AGL_ABIAS_P` 0.05 -> 0.3 instead of gating the bias on the floor | Fixes log19 about as well (worst gap -1.00 -> -0.30 m, section 6), and 0.3 is what tester E's quad flew. But it speeds the bias everywhere, in flight included, to cure a defect that is only on the ground, and the operator wants to keep a low value. The gate does it at 0.05. |
| Re-open the bias variance (to at least 0.1^2) on the `onGround` falling edge, as well as the gate | Measured 2026-09-29, byte-identical output on logs 18-21: with the gate the std is already 0.233 at liftoff, so the `MAX` never bites. Adds a state flag for nothing on these flights. |
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
  2026-09-29: log18, 20 and 21 emit it 1.9, 2.0 and 2.0 s after NOT_LANDED;
  log19 never does. Derived from the source, not measured: the message is sent
  only if the active height source is baro at the clear edge, and log19 was near
  1 m then, around the 0.9 m `EK3_RNG_USE_HGT` threshold. log9, pinned at the
  floor on the range finder source through its climb, fits the same reading.
- ~~**Push `d42f9dc86d` and `6bb08e8f98`**, update the PR description, and answer
  the review's 4(a) with section 6's numbers. The review's section 1 (the `if`
  clamp dropped `MAX()`'s NaN sanitisation) is still unanswered.~~ Done
  2026-09-29: pushed at `5a086b2cd9` with the gate moved to #33507, section 1
  fixed, description and reply posted.
- The fix commit's last paragraph says "The test is written so a NaN..." and
  means the floor check, not the autotest. Reword before pushing.
- Name log19 in REPLAY_LOGS.md alongside log9 (done 2026-09-29).

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

`6bb08e8f98` adds a second assertion to the same test, after its 15 s settle
on the floor: the bias std must not have collapsed. 0.0470 to 0.0472 with
`d42f9dc86d` over three runs, 0.0175 without it on every one of five (the
review measured 0.0173), so the 0.03 bound has about 1.6x either side. The
gated value is well under the 1.0 the filter starts at because SITL's range
noise lifts the measurement off the floor now and then, and those samples
still teach the bias. With both commits, `OpticalFlowAGLKfFloorVelocity`,
`OpticalFlowAGLKalmanFilter` (bias tracks the injected 0.338, excursion peak
0.027), `EK3_AccelBiasZeroVelOptFlow`, `OpticalFlowLimits` and `OpticalFlow`
pass.

Re-measured 2026-09-29 at `5a086b2cd9`, where the test also requires the
height to start on the floor and rise at least 2 m with the step, and reads
only samples that are all valid: -0.0009 to -0.0011 m/s with the velocity
clear and -3.53 to -3.61 without it, three runs each; rise 3.21 to 3.25 m.
These are a different measurement from the -1.361 above, which was taken on
the 4.7 base before the floor bias gate; the automated review measured -2.76
to -2.84 at `9b74c85f80`.

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

## Tidy round (2026-10-03, local, not pushed)

New commits on `f8651ffaeb`: registration re-indent (flake8 E131); the
no-coast test now asserts its provocation (VAgl >= 0.015 m/s after the step,
0.030-0.040 measured, valid finite samples only; RFND OutOfRangeLow
throughout) - without the coast fix the height still rises 0.34-0.37 m; the
coast-stop comment says it applies up and down. Floor test figure re-measured
on this head: -0.430/-0.431 m/s without the clear, so it stands.

Pushed 2026-10-03: f8651ffaeb -> 55bd80a81b (fast-forward).
Reply posted 2026-10-03: https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-5973590521

## 2026-10-08: AP-Review ACCEPT at `ec3c439aec`

The squash kept the reviewed lines identical; each commit builds and passes
flake8. Answered its question on flight testing:
https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-6056080176

## 2026-10-08: floor behaviour on fourteen flights, and a coast the stop missed

All of logs 31-44 flew the floor commits. Armed on the ground before
takeoff the AGL KF height stayed within 0.02 m of its floor on every log;
after touchdown within 0.07 m, except one lane after an acro sortie whose
main filter read 0.3-0.57 m/s climbing on the ground. The coast stop leaves
anything faster than 0.25 m/s to the IMU, so it never fired and the AGL KF
height coasted 0.28 -> 1.8 m.

fix2/34457 (two new commits on ec3c439aec, not pushed, not flown): with the
range last read within 0.5 m of the floor, no reading for 1 s and still out
of range low, an AGL KF height 0.3 m above that last reading is held on the
floor until a reading or the low reports stop. The last reading is recorded
for every sample, fused or not, and starts out of reach so nothing latches
before a reading. Replay: the coast held at the floor, the other 13 logs
unchanged. SITL OpticalFlowAGLKfNoCoastAfterTouchdown (accel offset on the
ground, main filter velD 2.8 m/s): 0.30 m rise with the hold, 2.42 m
without.

Rejected on the way: a 1 s timeout alone zeroed a real liftoff (+0.36 m/s,
log44); keying on the floor instead of the last reading pinned a liftoff on
a range finder whose minimum is well above its clearance (review); no latch
left a 0.35 m sawtooth. Known gap: a range finder whose minimum is over
0.5 m above its clearance never gets the hold.

### Superseded 2026-10-11 by 0c76bb6a54: the last reading is the last fused one

"Recorded for every sample, fused or not" let a reading the AGL KF gate
rejected arm the hold in flight. SITL at 22821432da
(OpticalFlowAGLKfNoFloorHoldInHover, 10 m hover, one 0.2 m Good reading
then out of range low): the AGL KF height was held at 0.10 m, still
valid, from 1.0 s after the reading. On the fix branch the last reading is
recorded only where the filter fuses it or re-initialises from it, and the
same run holds 9.97 m. No reason for counting rejected readings was ever
recorded here. The Replay result above was taken on the every-sample
version and has not been re-run on the fused-only one (see the 2026-10-11
section). Left in place because it is what the hold was measured as when
it went to the PR.

## 2026-10-08: pushed

Head ec3c439aec -> 7f83487786: the two floor-hold commits (931be4dc21, 7f83487786) on top of the five flown ones, review fixes folded in before the push. Not yet flown.

### Superseded 2026-10-11: flown on Q25v1, where the hold is inert

The floor hold has since flown on Q25v1 (per the 2026-10-11 AP-Review
triage, not re-checked here). Q25v1's range finder never reports
OutOfRangeLow, so `rngOutOfRangeLowTime_ms` stays 0 and the hold can never
arm there: those flights neither exercise nor clear it. It still has no
flight on a sensor that reports out of range low.

## 2026-10-08: on the 4.7 beta (topup13)

Carried as 29fef9c3a2 and db4abcbff0. OpticalFlowAGLKfNoCoastAfterTouchdown failed its precondition there: the 4.7 SITL range finder reads 0.55 m on the ground, not the ~0.1 m the test assumed, so RNGFND1_MIN 0.5 never took it out of range low. Beta commit 80626ee223 sets RNGFND1_GNDCLR from the RANGEFINDER reading on the ground and raises the minimum 0.4 m above it; owed to this PR, where it is a no-op on master. Beta: 0.29 m with the hold, 1.47 m with the OptFlowFusion change removed.

Pushed as 22821432da (2026-10-08), fast-forward on 7f83487786, message reworded for master. On master the test passes with a 0.27 m rise (0.30 m before).

### Superseded 2026-10-11: the 0.55 m is SITL's terrain tile, not the 4.7 build

What the SITL range finder reads on the ground depends on whether AP_Terrain
has the CMAC tile, not on the branch. With the tile (SIM_TERRAIN 1, the
default) `height_agl` is taken over SRTM terrain, which at CMAC home is
583.54 m against the 584 m home: about 0.55 m on the ground. Without it the
flat earth fallback reads 0.0 m. Evidence: the main clone, where the beta
ran, carries a populated `terrain/S36E149.DAT` (2.1 MB); fresh worktrees
have an empty one and log TERR Status 1, Loaded 0, and read 0.0 m (the
"~0.1 m" assumption was never measured; RNGFND1_GNDCLR's default is 0.1).
#33507's CI run at c34e097cc4 had the tile (TERR TerrH 583.536, CHeight
0.554, Loaded 504) and its RFND read 0.56 m on the ground, status Good with
RNGFND1_MIN 0.5, which is the "range finder was not below its minimum"
failure there. So 80626ee223's change is not a no-op on master: it is what
makes the test pass wherever the tile is present, CI included (measured
2026-10-11, below).

## 2026-10-11: AP-Review round at 22821432da, fixes

Local branch `fix/pr-aglkf-floor-velocity` on 22821432da, not pushed. For
the squash: fixups 0c76bb6a54 (AP_NavEKF3, into 931be4dc21), deaf5a44d2
(into 7f83487786), ed0346272e and b2ec664be9 (into 22821432da); amend!
6e3856216e (931be4dc21), 136ee6b5c0 (7f83487786, new subject "autotest:
check when the AGL KF holds its floor"), and two for 22821432da: 174a38a812
then b0cd0a7b9b, which supersedes it (the first still blamed the 4.7
build). Applying the fixups at their autosquash positions with a scratch
index reproduces the branch tip's tree exactly.

Same in-flight pin as the 2026-10-02 landed hold (":83-86" above), which
was rejected because `takeoff_expected` could pin the AGL height in a slow
hover. The floor hold reintroduced the same failure class through a
different door, a rejected range sample, and the record said "fused or
not" without a reason.

| Finding | Status | Fix |
|---|---|---|
| F1 rejected short reading arms the hold in flight | RESOLVED | 0c76bb6a54: `aglKfLastRngHgt` written only after the gate accepts (`= hgtMeas`, next to `lastAglRngFuseTime_ms`) and at the 5 s re-init (`= aglKfH`); the write before the tilt return is gone. New test OpticalFlowAGLKfNoFloorHoldInHover (deaf5a44d2) |
| F2 RNGFND1_GNDCLR set to 0.0, below its 0.05 minimum | RESOLVED | ed0346272e/b2ec664be9: `max(reading, 0.05)`; message no longer claims ~0.1 m on master |
| F3 touchdown test's velD and rise checks pass on NaN | RESOLVED | deaf5a44d2: raises on any non-finite velD or valid-sample height first |

The new test: GUIDED takeoff to 10 m with `WP_RFND_USE 0` (without it the
GUIDED takeoff targets height above the range finder and the vehicle climbs
after the short reading, which spoilt the first draft: it failed at 1.20 m
because the filter legitimately accepted the reading as the copter rose
through it). At speedup 1, `SIM_SONAR_OFFSET` = 0.2 m minus the hover
reading, then `RNGFND1_MIN` 0.5 sent directly (no read-back), 3.5 s, restore.
It asserts a short Good RFND then status 2, HAglStd growth (one gate
rejection is x1.41), every XKFA sample from the short reading to 0.8 s
after the low reports valid, finite and above 5 m (else "provocation ran
too long"), and from then to the restore at least 20 samples, valid, finite,
min above 5 m. Margin: two rejections per run against about eight before
the gate accepts a 9.8 m innovation (derived from the source, not
measured).

All runs SITL copter, single EKF3 lane, worktree build (no terrain tile
unless stated):

| Run | Code | Result |
|---|---|---|
| FloorVelocity | 22821432da / fix tip | rise 3.10 / 3.10 m, HAgl 0.100 / 0.100, VAgl 0.0001 / 0.0001, pass / pass |
| NoCoastBelowMin | 22821432da / fix tip | step vel 0.037 / 0.039, rise 0.000 / 0.000, pass / pass |
| NoCoastAfterTouchdown | 22821432da / fix tip | GNDCLR set 0.0 / 0.05; velD 2.77 / 2.70; height 0.050-0.332 / 0.050-0.340; pass / pass |
| NoCoastAfterTouchdown, hold block removed | fix tip, temporary edit | velD 2.80, 0.063-2.191 m: FAIL "coasted 2.13 m" |
| NoFloorHoldInHover | 22821432da binary | short 0.30 s before low, std 0.125 -> 0.295, FAIL "held at 0.10 m" |
| NoFloorHoldInHover | fix tip, 3 runs | short 0.20 s, std 0.126 -> 0.288 / 0.284 / 0.284, height 9.97 m (32 samples), pass x3 |
| NoFloorHoldInHover, F1 fix reverted | fix tip, temporary edit, rebuilt | std 0.126 -> 0.293, FAIL "held at 0.10 m" |
| NoCoastAfterTouchdown, CMAC tile | fix tip | GNDCLR 0.5454, MIN 0.9454, status [2], 0.545-0.840 m, pass (first attempt died on "Did not get SYSTEM_TIME" at takeoff, host load 6.4; rerun) |
| NoFloorHoldInHover, CMAC tile | fix tip | std 0.125 -> 0.286, 10.52 m, pass |

flake8 clean on the tip and on the intermediate (7f83487786 + fixup) file.

The SFD beta (OptFlowFusion.cpp:1221 at 38c627cb2b) carries the same
every-sample write. The fix is the same three lines but does not apply as a
patch (core.h and both fusion-time contexts differ); the equivalent diff
is the PR's with `aglKfLastRngHgt = aglKfH` after the re-init's
`lastAglRngFuseTime_ms` and `aglKfLastRngHgt = hgtMeas` before
`aglKfLastHgtInnov = hgtInnov`. Not built or tested on the beta.

#33507 restacks onto the fix tip with no conflicts (33507/README.md).

Still owed:

- Replay of logs 31-44 with the fused-only record. Only log35 is on this
  machine (SFD-O4/refresh10), and the acro-sortie lane that motivated the
  hold is not named in this record. The amend! message 6e3856216e keeps the
  "Replay of fourteen flights" sentence from the old message: re-run it or
  drop the sentence before the squash. REPLAY_LOGS.md has no row for the
  floor hold.
- The floor hold has no flight on a sensor that reports out of range low.

Pushed 2026-10-11: `pr-aglkf-floor-velocity` `22821432da` -> `b17402187a` (force, autosquashed), 8 commits; final tree identical to the tested fix branch; copter and Replay build at the changed hold commit. Mechanical gate (/pr-review checks, with the new squashed-subject scan) clean. PR replies drafted, not posted.

Reply to the AP-Review round posted 2026-10-11 (issue comment 6110169753), the text drafted above.

### Note 2026-10-13: unflown fixes squashed into flown commits

The 2026-10-11 push (`b17402187a`) autosquashed review fixes that change behaviour into commits that had flown: the hold commit now also carries the change that arms the floor hold only from a fused reading. That breaks the rule now in the root playbook (never squash an unflown behaviour change into a flown commit), so the flight evidence recorded above for those commits covers the code before that push, not this part of it. Not rewritten again, to spare reviewers the churn; the beta carries the change as its own commit (topup15 `25b2081449`), and flight results on it will be recorded against that commit. From 2026-10-12 review fixes that change behaviour go on top as new commits.

Pushed 2026-10-13: `b17402187a` -> `a7841c86c4` (force): the touchdown test fix folded into the test commit that added it, with the merged message (test only, no behaviour change). The hold commit `a23f3bfc65` is unchanged. Mechanical gate clean. Replies not posted yet.

Reply to the second AP-Review round posted 2026-10-13 (issue comment 6134598251).

Pushed 2026-10-14: `a7841c86c4` -> `04341318b9` (force): the known-limit comment folded into the hold commit (comment only; every commit's code unchanged). Mechanical gate clean. Replies and description not posted yet.

PR description updated and reply to the third AP-Review round posted 2026-10-14 (issue comment 6153655917).

## 2026-10-14: AP-Review round at 04341318b9

COMMENT, nothing blocks; the review predates the 2026-10-13 description
update, which already covers what it asks (the floor hold and its tests,
"Tested on hardware" unticked).

## 2026-10-30: the landed hold after hard acro, SFD-O4 log65

Flight card item 1, on the beta `52b1d36f`. log65 (3408138/646): an acro
sortie to 56 m, then a LOITER landing (land complete 179.2 s) and 23 s armed
on the ground before disarm at 202.3 s, range finder out of range low
(0.01-0.02 m, stat 2). The AGL KF held its 0.05 m floor on both cores for
the whole time on the ground (core 0 read 0.53 at the touchdown sample, then
0.05 within 5 s). The main filters read `XKF1.VD` -0.20 to +0.68 m/s on the
ground, the positive end the touchdown itself; the climb they settled to
(-0.17/-0.19 at 189 s) is under the 0.25 m/s that defeated the coast stop on
log39. Passed.

Clarified 2026-10-31 by the squash audit: the range-reads-too-low hold
never engaged here or in any of 12 logs replayed with it removed, so the
floor above was held by the PR's other commits (the floor clear
`42de1d07f1` or the coast stop `d3df572550`), not that hold
(`squash-audit-2026-10-31/B.md`).

Shorter dwells the same day: log61 (3408138/639) 1.4 s, 0.07-0.08 m on both
cores; log63 (3408138/643) flight 2 6 s, core 1 0.12 m. The main filters'
terrain height read 0.4-1.8 m below the ground on log65 while landed; that
is `terrainState`, not the AGL KF.

## 2026-11-05: AP-Review at `713beeb50b`, and maintainer questions unanswered

AP-Review, COMMENT
(https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-6618771042).
Should-fix, new: if the AGL height reaches the floor before touchdown,
clearing its velocity there lets the landing deceleration push the height
up while the range finder reads Good (bot SITL: 2.4 m on the ground for
several seconds, 0.2 m without the line at OptFlowFusion.cpp:821; 3.0 m
with RNGFND1_GNDCLR 5 cm above the resting reading); its option, SITL
only, clears the velocity only while the main filter's vertical speed is
under 0.25 m/s. Not verified here. Also flagged: peterbarker's line
questions of 2026-10-14 (:825 "no reading the EKF can consume"?, :832
0.25?, :833 0.3?) and rmackay9's request the same day for a before/after
graph of the estimated velocity have no reply on the PR; the Replay A/B
plot above (plots/aglkf_1_replay_ab_log9.png) was made for it. Minor:
aglKfLastRngHgt and aglKfHeldOnFloor could move into master's new
AglKalmanFilter class.

### 2026-11-05: peterbarker answered; the touchdown should-fix reproduced

Replies posted in peterbarker's threads of 2026-10-14:
https://github.com/ArduPilot/ardupilot/pull/34457#discussion_r4479534281
(the comment was reworded since), #discussion_r4479534583 (0.25 m/s:
without it and the 200 ms term the stop fired at a normal liftoff, log22
0.77 m; the floor hold covers a main filter reading 0.3-0.57 m/s on the
ground), #discussion_r4479534829 (0.3 m: 13 of 14 flights within 0.07 m
after touchdown, the coast 0.28 -> 1.8 m).

rmackay9's graph: not answered. log9 is not available locally (the
boot 525-536 batch is missing). More important:
on the PR's merge base `802db19de1` OpticalFlowAGLKfFloorVelocity passes,
-0.0008 m/s (tier 2): master's decay, running on most steps, keeps the
floor wind-up near zero. The test comment's -0.431 m/s is this PR with
only the floor clear removed (re-measured -0.439). The -7.2 m/s of log9
came from a build carrying #33507's bias state. So a master-against-PR
velocity graph would not show the description's first line; that needs
a decision on how the description frames it.

AP-Review's touchdown should-fix, reproduced (tier 2): in
OpticalFlowAGLKfNoCoastAfterTouchdown's own landing (2.4 m/s descent
from 3 m) the AGL KF reaches its floor still carrying the descent, the
floor clamp clears it, and the impact deceleration then integrates a
full +2.4 m/s: worst height over the range finder after LAND_COMPLETE
+2.46 m (+2.45 with RNGFND1_GNDCLR 5 cm above the resting reading), for
about 7 s, range finder Good at 0.00 throughout. Seen on a real flight
too: log65 replayed (beta Replay) touches down 0.52 m over the range
finder on core 100.

| build | SITL landing | +5 cm GNDCLR | FloorVelocity | log65 touchdown (c100) |
|---|---|---|---|---|
| head | +2.46 m | +2.45 m | +0.0001 m/s, pass | +0.52 m |
| floor clear removed (diagnostic) | +0.10 m | +0.14 m | -0.439 m/s, fails | - |
| clear only while main filter abs(VD) < 0.25 m/s (bot's option) | +0.19 m | +0.35 m | +0.0001 m/s, pass | +0.04 m |

With the bot's option NoCoastBelowMin (0.000 m), NoFloorHoldInHover and
OpticalFlow pass; log27 and log28 replay unchanged in the sweep. Its one
side effect seen: on log65's acro sortie the AGL KF ran down to its floor
with no range data while descending at about 9 m/s, and the option no
longer zeroes that velocity (-9.9 / -11.5 m/s on cores 100/101, close to
the true descent rate; replay_sweep's floor-velocity column flags it).
The main EKF is unchanged by it: the first XKF1 difference is 1.3 s
before touchdown, where the option improves the landing; XKF5 flow
innovations differ by a count from 68.6 s. Not checked: log39, whose
main filter read 0.3-0.57 m/s on the ground (no fingerprint recorded),
where the option would leave the floor clear off while that lasts.
Builds: SITL worktree `r1105-34457` (PR head, variants applied in the
working tree and reverted), beta Replay worktree `r1105-beta-replay`.

### 2026-11-05 (later): the PR against master in SITL, and 34 real logs

The SFD-O4 logs are on the log server (log5-7, 9-17, 22-39, 61-65 copied
locally, 777 MB; log9 confirmed as boot 525).

Climb and descent in SITL, master's EKF (merge base `802db19de1`) against
the PR head, throwaway probe (flow, range finder, EK3_OPTIONS 8, ALT_HOLD to
8 m and back, flat ground so the range finder rate is the truth),
`plots/aglkf_3_climb_sitl.png`, tier 2:

| | master | PR |
|---|---|---|
| AGL KF velocity / true rate, climb | 0.52 | 1.00 |
| same, descent | 0.55 | 1.01 |
| worst AGL KF height error, climb / descent | 1.06 / 1.13 m | 0.29 / 0.41 m |

That is the change a pilot on master gets: master's decay halves the AGL KF
velocity in any climb or descent. The plot also shows two costs of the PR:
after the climb stops its velocity hangs near 0.3 m/s for a few seconds and
the height overshoots 0.3 m (master's decay used to damp that), and after a
1.4 m/s touchdown its height coasts up about 0.8 m for about 8 s (the
floor-clear double count below).

34 SFD-O4 logs replayed through the beta's Replay (which carries #33507's
bias state and this PR's landing code line for line), three builds: as is,
the floor clear removed, and the clear gated on main filter abs(VD) < 0.25
m/s (AP-Review's option). Tier 1b. AGL KF velocity on its floor while
sitting on the ground (before the first takeoff, and from 3 s after each
landing), per core-dwell:

| build | before takeoff, below -0.3 m/s (worst) | after landing, below -0.3 m/s (worst) | worst touchdown, height over range |
|---|---|---|---|
| as is | 0 of 68 (-0.22) | 0 of 59 (-0.06) | +0.52 m (log65; log38 +0.46, log12 +0.31) |
| floor clear removed | 25 of 68 (-0.74) | 20 of 60 (-7.07, log16) | +0.21 m |
| clear while abs(VD) < 0.25 | 0 of 68 (-0.22) | 2 of 58 (-0.66 log9, -0.35 log35) | +0.25 m |

Takeoff error and in-flight rms are identical across the three. So the
floor clear is needed on real flights (with the bias state), the touchdown
coast it causes is real but at most 0.5 m on these landings, and gating it
on the main filter's speed fixes the coast but lets the wind-up back after
two landings where the main filter read over 0.25 m/s on the ground.
Neither version is right; a threshold-free alternative is being looked at.

### 2026-11-05 (later): the floor as a measurement, prototyped

From a read-only analysis of the PR's constants (scratch, not recorded in
full): the clamp's velocity clear is the R = 0 case of fusing the floor as
a measurement, which is why it double-counts a touchdown. Prototype (not
for commit): no state clamp; when the AGL height is below rngOnGnd and no
range sample is due that step, fuse z = rngOnGnd, H = [1 0 (0)], R =
sq(EK3_RNG_M_NSE), Joseph update, no bias gain (as for any floor reading);
readers clamp the output (XKFA, getHAGL, the PosVelFusion and step-check
readers). No new constant. Two variants: with the coast stop and floor hold
kept, and with them removed.

SITL on the PR head (tier 2):

| build | touchdown repro (+5 cm GNDCLR) | FloorVelocity | NoCoastBelowMin | NoCoastAfterTouchdown | NoFloorHoldInHover, OpticalFlow |
|---|---|---|---|---|---|
| head | +2.46 m (+2.45) | +0.0001 pass | pass | pass | pass |
| soft floor | +0.21 m (+0.15) | -0.0000 pass | pass (0.000 m) | pass | pass |
| soft floor, stop and hold removed | +0.09 m (+0.11) | pass | fails, 0.37 m | fails, 2.43 m | pass |

Beta Replay, the 34 SFD-O4 logs (tier 1b), with the earlier three builds:

| build | pre-takeoff below -0.3 m/s | after landing below -0.3 m/s (worst) | worst touchdowns |
|---|---|---|---|
| as is | 0 of 68 | 0 of 59 | +0.52 (log65), +0.46, +0.31 m |
| soft floor | 0 of 68 | 3 of 60 (-0.64 log9, -0.38/-0.33 log35) | +0.25 (log37), +0.25, +0.24 m |
| soft floor, stop and hold removed | 0 of 68 | 3 of 59 | +0.77 (log39), +0.48, +0.36 m |

Soft floor against as is, per log: touchdown log65 +0.52 -> +0.04, log38
+0.46 -> +0.13, log12 +0.31 -> +0.05, log29 +0.24 -> +0.05; takeoff error and
in-flight rms unchanged (one log's rms +1.62 -> +1.75, one +2.85 -> +2.79).
log9's after-landing velocity under the soft floor creeps -0.03, -0.06,
-0.09 m/s at 10, 15, 30 s; its -0.64 is a transient about 45 s after
landing where the as-is build reads +0.63 m/s too (handling, not wind-up).

So the soft floor fixes AP-Review's touchdown double count with no new
constant and keeps the ground wind-up small, and the coast stop and floor
hold answer a separate mechanism (an accel residual lifting the height
while the sensor reads too low), which the floor cannot. Their constants
still need ARCH-24 treatment; the analysis's suggestion is an upper bound
fused while the sensor reports out of range low (min_distance times the
tilt), which needs min_distance carried in the DAL (a Replay log format
change).

### 2026-11-05 (evening): the soft floor and named limits on the branch (local, not pushed)

`r1105/34457-sf` on the PR head `713beeb50b` (fast-forward), five commits:

- `88a32cdb07` AP_NavEKF3: FuseAglKfHeight(), the range update moved out
  (no behaviour change: log27 replayed through Replay before and after,
  0 EKF records differ).
- `1f0abd73bf` AP_NavEKF3: fuse the floor (R = sq(EK3_RNG_M_NSE), steps
  without a range sample) instead of clamping and clearing the velocity;
  the state may sit below the floor, so getHAGL() and XKFA clamp.
- `53f7be5d37` autotest: OpticalFlowAGLKfTouchdown, three landings at
  about 2.5 m/s, height within 0.5 m of the range finder for 10 s after
  each. The double count shows on about three landings in four, so one
  landing alone missed it in a quarter of runs (an earlier draft with the
  ground clearance 5 cm above the reading made it rarer, 1 in 4, so that
  idea was wrong). Head fails 3 of 3 runs (2.53-2.55 m); the fix passes 3
  of 3 (0.11-0.25 m over nine landings). OpticalFlowAGLKfFloorVelocity's
  comments updated.
- `1535dabf58` AP_NavEKF3: rngFreshTime_ms (500) and
  rngOnGndNoDataTime_ms (200) named at readRangeFinder() and the height
  source selection (objects identical before and after).
- `5e4346a261` AP_NavEKF3: the coast stop and floor hold use those names
  and four named limits with their evidence (aglKfStillVelZMax_m_s 0.25,
  aglKfFloorHoldNoRngTime_ms 1000, aglKfFloorHoldNearFloor_m 0.5,
  aglKfFloorHoldCoast_m 0.3; object identical before and after).

Margins (original logs; 34 SFD-O4, 23 Q25v1 from tester A's MicoAir 2.5 inch
folder, fingerprint 2818322):

| limit | evidence |
|---|---|
| 0.25 m/s | SFD-O4 landed under the coast stop's other conditions: main filter abs(VD) p50 0.016, p99 0.19, max 0.69 m/s (48k samples; 9 flights exceed 0.25 briefly) |
| 1000 ms | 41 SFD-O4 liftoffs from below the sensor minimum: first reading 0.14-0.39 s, one 1.03 s (log38), then 0.04 m above its last reading |
| 0.5 m | 16 SFD-O4 landed losses of range: last reading within 0.12 m of the floor |
| 0.3 m | with the floor fused, SFD-O4 landings rose at most 0.25 m above the range finder (64 core-landings) |
| Q25v1 | its MAVLink range finder never reports too low: the coast stop and hold never act (all four soft-floor builds replay identically) |

Which block does the work, with the floor fused (SFD-O4 replays): without
the floor hold, identical to both kept (0 of 64 landings over 0.3 m);
without the coast stop, 5 of 64 (log37 0.41, log38 0.36, log39 0.36 m).
log39's 1.8 m coast, the reason the hold was added, does not reproduce on
today's beta code without the hold (+0.23 m, clear and coast stop kept):
the coast stop catches it now. The hold never engages on any of the 57
logs; it stays because the case it models (an accel error on the ground
with the main filter reading over 0.25 m/s and the sensor too low) is
possible, and OpticalFlowAGLKfNoCoastAfterTouchdown provokes it (fails
2.41 m without the hold). Records checked: nothing else depends on the
hold or that test (#33507 runs it as part of its stack).

Q25v1 replay of the soft floor (all 23): touchdowns 0.47 -> 0.11, 0.58 ->
0.31, 0.63 -> 0.26, 0.42 -> 0.19 m; later 16 flights unchanged in takeoff
and in-flight error but one takeoff (0.19 -> 0.24 m). The 7 earliest
(vertical runaway period) wind up on the ground under either build and
the fused floor lets more through (worst -1.70 against -0.54 m/s); two of
their takeoffs worse (1.11 -> 1.28, 1.23 -> 1.54 m), one better. Not
EK3_ABIAS_P_NSE: 15 of the 23 flew 0.005, including the unaffected 18-23.

Tests at `5e4346a261`: FloorVelocity (-0.0001 m/s), Touchdown,
NoCoastBelowMin, NoCoastAfterTouchdown, NoFloorHoldInHover, OpticalFlow,
OpticalFlowLimits, Replay pass; copter, plane, Replay build; gate clean;
check_branch_conventions passes. Open: #33507 restacks onto this (its
three-state filter needs the floor fused with no bias gain, as the beta
prototype did); the beta does not carry the soft floor.

Quick review at `5e4346a261`: gate clean, one Codex cold read of the five commits (no issues found). Pushed 2026-11-05 as a fast-forward, `713beeb50b..5e4346a261` on `pr-aglkf-floor-velocity`.

Climb probe re-flown at the pushed head (`plots/aglkf_4_climb_sitl_fused_floor.png`): velocity / true 1.01 and 1.02, worst height error 0.28 / 0.40 m; the touchdown coast is gone (height stays on the floor, velocity dips to -0.4 m/s and settles in about 4 s); the 0.25 m overshoot after the climb stops remains. Also checked for the description: on log9 the fused floor holds the pre-takeoff dwell at -0.01 m/s (no floor handling -0.51 on today's code); replay_sweep's own floor-velocity column for log9 reads -8.8 m/s with the fused floor against -1.1 with the clear, but that is in-flight floor contact with no range data (the descent kept in the velocity), not ground wind-up. On the beta the main filter's records differ slightly between the clear and the fused floor from early in each flight (the AGL KF feeds velD fusion and flow scaling there); in-flight height error and takeoffs unchanged across the 34. Posted 2026-11-05: description rewritten (leads with the halved climb velocity on master; the fused floor, the named limits, the costs); reply to rmackay9 https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-6657687701 (graph to be attached by hand); reply to AP-Review's touchdown should-fix https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-6657688047; follow-ups in peterbarker's threads #discussion_r4480275715 (0.25) and #discussion_r4480276044 (0.3).

## 2026-11-06: the fused floor flown, SFD-O4 log78

SFD-O4 log78 (flown 2026-11-05 indoors), beta topup11 `52ec3c77`, which
carries this PR's 11-05 commits as `1bf3d76145`, `ab0260f547`,
`64115088c0`, `4718d30adf` and the tests `6df2392ac4`, `1a7ec50d81`, with
#33507's bias state under them. Flow lane primary, EK3_OPTIONS 94. Four hops
in ALT_HOLD to 1-2 m, each ended by a full-rate descent (1.1-1.9 m/s at
touchdown, 6.5-7.7 g), a disarm and a re-arm 2.4-3.1 s later. On the ground
the range finder read 0-0.04 m (out of range low), so the floor was the AGL
KF's only height reference. As flown, `XKFA.HAgl` held 0.05-0.20 m on both
cores until each next arm.

Replay with `ab0260f547` reverted (the clamp and velocity clear back)
against the as-flown Replay, which matches the flight. Worst AGL KF height
from touchdown to the next arm, tier 1b:

| landing | core | fused floor (as flown) | clamp and clear |
|---|---|---|---|
| 1 | 0, 1 | 0.19 m | 0.19 m |
| 2 | 0 | 0.22 | 0.25 |
| 2 | 1 | 0.25 | 0.39 |
| 3 | 0 | 0.16 | 0.18 |
| 3 | 1 | 0.18 | 0.45 |
| 4 | 0 | 0.22 | 0.50 |
| 4 | 1 | 0.28 | 0.28 |

So `1f0abd73bf` has flown and acted: the touchdown lift the clear
double-counts reached 0.39-0.50 m on three of eight core-landings, and the
fused floor held every landing to 0.16-0.28 m. The cost seen: at the arm
after landing 2 the fused floor still read 0.20/0.18 m against 0.05 m with
the clamp, as the floor is fused with R = sq(EK3_RNG_M_NSE) rather than
set. Squash decision: `squash-audit-2026-10-31/O4-2026-11-05.md`.

## 2026-11-06: the touchdown test over flat ground, pushed

`717595bef8` autotest: OpticalFlowAGLKfTouchdown sets SIM_TERRAIN 0. Over
the CMAC terrain tile the range finder read 0.55 m on the floor, and the
test failed waiting for 0 ("Failed to attain RangeFinderDistance want
0.0, reached 0.55"). A/B: fails with the tile, passes with terrain off.
Test-only, three lines; no quick review. Pushed as a fast-forward,
`5e4346a261..717595bef8` on `pr-aglkf-floor-velocity`.

### 2026-11-06: AP-Review at `717595bef8` (COMMENT), answered on `r1106/34457-tests` (`3c61127e59`, `d8da8db695`, not pushed)

`3c61127e59` makes OpticalFlowAGLKfTouchdown require at least 50 XKFA
samples per 10 s landing window, all valid and finite; 100 were measured,
all valid. Mutant (velocity clear restored, lifted samples logged invalid):
old test passed at 0.38-0.39 m with a real lift of 2.47-2.52 m, new test
fails. Real code 3/3, 0.11-0.22 m. A Codex audit found NoCoastAfterTouchdown
had the same hole: `d8da8db695` requires every sample valid and finite, at
least 20 of the 40 in a window shortened from 6 s to 5 s, since its last
second crossed the AGL KF's own 5 s range timeout and was invalid on the
correct build. A mutant whose hold gave up after 3 s and hid the lifted
samples passed the old test (34 valid, hidden 1.25 m) and fails the new one;
with the hold disabled it fails at 1.82 m; real code 3/3 at 0.28-0.29 m.
The member move was declined because it would churn #33507's restack. The
'test blimp' red is SIMCompare and unrelated.

Pushed 2026-11-06: `pr-aglkf-floor-velocity` `717595bef8..d8da8db695` (fast-forward). Reply posted: https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-6690425361

### 2026-11-07: AP-Review at `d8da8db695` (ACCEPT), the touchdown finiteness check (`r1107/34457-finite`, `e1c95f7d8c`)

One optional minor. e1c95f7d8c (local, r1107/34457-finite) makes OpticalFlowAGLKfTouchdown fail on any non-finite XKF1.VD sample in the 3 s before a landing, before it takes max() for the touchdown speed. max() returns a NaN that comes first, and NaN < 1.0 is false. A mutant that set the first sample of each window to NaN passed the old test, reading "touchdown at nan m/s", and fails the new one. The real code passes at 2.48-2.50 m/s with 0.11-0.15 m of lift. The floor-hold known limit is unchanged. Test-only, fast-forward.

Pushed 2026-11-07: `pr-aglkf-floor-velocity` `d8da8db695..e1c95f7d8c`. Reply posted: https://github.com/ArduPilot/ardupilot/pull/34457#issuecomment-6706616216

## 2026-11-07: three landings outdoors, SFD-O4 logs 84-86 (tier 1)

The SFD beta (refresh13 topup1, build reporting `ea9c6ab5`) carries this
PR at `d8da8db695`, with the head's test-only finiteness check
(`e1c95f7d8c`) ported as `71a1aa7623`. Three landings outdoors on GPS:
log84 (3408138/693) after 211 s of ACRO and a Loiter descent, log85 (695)
and log86 (697) after Loiter only. From land complete to disarm (0.9-2.0
s) `XKFA.HAgl` held 0.05 m on both cores on all three (0.06 m on log85's
core 1). These were short sits armed on the ground, so they say nothing
about a long armed sit.

Logs 87-88 (2026-11-07, same build, SFD-O4 3408138/699 and /701): after
ACRO and a Loiter descent, `XKFA.HAgl` held 0.05 m on both cores from land
complete to disarm (at once on log87, 1.6 s on log88).

## 2026-11-07: test fixes squashed, pushed

Pushed `e1c95f7d8c` -> `e6d636fab3` (force, 16 commits to 12, same tree;
backup `pre-squash/34457-1107`). The four touchdown test fixes
(`717595bef8`, `3c61127e59`, `d8da8db695`, `e1c95f7d8c`) fold into the
touchdown test `53f7be5d37`, now `e04b365f5d`. `d8da8db695` changes
`713beeb50b`'s lines, but goes here, after the fused floor it was
checked against: at `713beeb50b` (clamp and clear) its stricter check may
fail.

The fused floor (`841b88516b`, was `1f0abd73bf`) has flown and been
verified (log78 above, and it held 0.05 m on both cores at every landing
of SFD-O4 logs 84-88), but stays its own commit. Folding it into
`7387e2ac70` would move the structure commit `88a32cdb07`, rebase the
coast stop and floor hold onto the fused floor, and change the PR's
first commit. Left for the merge squash.

Two commit messages no longer name the airframes ("34 flights of one
quad", "23 flights of another quad").

## 2026-11-10: the floor hold's known limit, flown (tier 1)

The Q25v1 on the beta `7b00f3b5` indoors (2818322/188), its range finder
compromised: out of range low, reading 0 m, for 98% of a VALT flight at
1-4 m up. The coast stop held the AGL KF velocity at 0 while the sensor
read too low, and at 40.74 s the floor hold snapped the height from 0.36
to 0.05 m in the air: the limit the hold's comment states, "a range finder
that reads Good on the ground and then reports too low from liftoff while
in range (one returning zero on a lost return) pins the height to the
floor until the 5 s timeout". It went invalid at 41.3 s. Nothing reached
the control (VALT, baro height), but lockout resets (#33484) then scaled
the flow by the floor height and took the velocity to near zero.
