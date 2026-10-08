# AGL KF: clear the velocity when the height rests on its floor


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
reliable: the land detector stayed set through a whole cqc-copter flight
(analysis repo `notes/cqc_height_datum_reset_status.md`), while
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
| Raise `EK3_AGL_ABIAS_P` 0.05 -> 0.3 instead of gating the bias on the floor | Fixes log19 about as well (worst gap -1.00 -> -0.30 m, section 6), and 0.3 is what Lucid v2 flew. But it speeds the bias everywhere, in flight included, to cure a defect that is only on the ground, and the operator wants to keep a low value. The gate does it at 0.05. |
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

## 2026-10-08: pushed

Head ec3c439aec -> 7f83487786: the two floor-hold commits (931be4dc21, 7f83487786) on top of the five flown ones, review fixes folded in before the push. Not yet flown.
