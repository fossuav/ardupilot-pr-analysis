# PR #33484 - recover horizontal velocity from a single-axis optical-flow lockout

Analysis archive for [ArduPilot/ardupilot#33484](https://github.com/ArduPilot/ardupilot/pull/33484).
Branch `pr-vel-flow-axis-gate` (andyp1per fork), base `master`. Real-flight
numbers are cited inline; no real-flight logs are committed here. Option bits
and log message names below are the upstream ones (AglKfForOptflow is
`EK3_OPTIONS` bit 3, the AGL KF logs as `XKFA`); the flights were flown on the
SmallFastDrone branch, where the same option is bit 4 and the message is
`XKF6`.

## Status (one line)

**Superseded in part on 2026-09-04 - see `split-and-quality-gate.md`.** The
floor is now its own PR (#34292) and the branch has gained `EK3_FLOW_QMIN`.
Everything below about the mechanism, the flights and the Replay tuning
still stands.

Mechanism confirmed in code and in three flights, recovery Replay-tuned to a
500 ms threshold and flight-validated; the branch also carries the follow-on
near-ground flow floor (`EK3_FLOW_MIN_H`), flight-validated on a second
airframe. The PR description on GitHub still says 1 s and does not mention
the floor, the reset-churn demotion or the `XKF7`/`SIM_FLOW_OFS` additions.

## The problem

Indoor optical-flow Loiter "flyaway": on engaging Loiter after a manoeuvre the
vehicle commands a violent brake lean and departs. On a 5-inch flow quad
(MatekH743, ARK Flow, downward rangefinder, 4.7-beta6 SmallFastDrone build)
two acro-to-Loiter entries flew away while the one entry from a settled hover
held for 30 s (log A); with the AGL KF enabled the steady hold was solid but
the entries still flew away (log B).

It is not the AC_Loiter drag bug (#33318, already in that firmware), not flow
quality (`OF.Qual` ~82), not height (AGL KF valid, `HAglStd` ~0.11 m), not
yaw, and not real motion: during the runaway the vehicle is level (pitch
-0.4 deg) and the flow sensor reads zero translation (~0.003 rad/s). The
velocity is a phantom.

## The conclusion and why

Flow is fused one axis at a time, each against its own innovation gate, but
flow health is one shared `prevFlowFuseTime_ms`, and the AID_RELATIVE timeout
that would reset velocity fires only when both axes stop fusing. One axis
rejected continuously while the other passes therefore never times out; the
rejected component dead-reckons on residual accel bias without bound.

Log B, exit of the good Loiter at 74.9 s (flown, not committed):

| t (s) | XKF5.NI | FIX  | FIY        | XKF1.VN |
|-------|---------|------|------------|---------|
| 74.9  | 47      | 351  | -534       | +0.69   |
| 75.1  | 255     | -212 | -2731      | +0.18   |
| 75.9  | 255     | 37   | 2773       | -3.29   |
| 84-88 | 255     | +/-50..300 | 3700..6700 | -8.5 |

VN then ramps at a constant ~-0.6 m/s^2 to -9.7 m/s by 88 s and PN
dead-reckons to -78 m (-237 m at the second flyaway); VE stays ~-0.15 m/s
throughout, because the East-carrying axis keeps passing and keeps the shared
timer fresh. The runaway ended only at an unrelated bootstrap reset. Log A
shows the same at -3.5 m/s.

The fix tracks the fuse time per axis and, when one axis has been rejected for
longer than the threshold while the other still passes, re-anchors horizontal
velocity to the flow-implied velocity (invert the LOS model, rotate to NED,
keep the vertical component). It is gated on the AGL KF being enabled and
valid so the range used for the scaling is trustworthy; with the option off
the path is inert.

## Key findings

### 500 ms, from a Replay sweep over three logs

Log C (same vehicle, pure Loiter, `LOG_REPLAY=1`) replays trajectory-faithfully
(PN -44.6 m replayed vs -46.3 m flown), so its numbers compare to flight; logs
A/B contain acro and compare only across configurations. Peak horizontal
excursion (m) / reset count:

| threshold | log A | log B | log C   |
|-----------|-------|-------|---------|
| flight    | 221   | 246   | 46      |
| off       | 59/1  | 55/1  | 45/0    |
| 1000 ms   | 11/7  | 6/8   | 17/7    |
| 500 ms    | 4/10  | 4/23  | 5.5/10  |
| 300 ms    | 7/18  | 4/38  | 3.2/20  |
| 150 ms    | -     | -     | 12.5/48 |

500 ms is near-minimum on all three without the thrashing 300 ms causes and
the over-firing below it (re-anchoring to noisy flow on brief legitimate
rejections). The branch uses 500 ms (`FLOW_AXIS_LOCKOUT_MS`).

### EK3_FLOW_MAX is not the lever

Log C flew at 7.4 rad/s (the sensor maximum) and still flew away; replaying
log A at 7.4 vs the flown 2.5 is byte-identical; raw flow exceeds 2.5 rad/s
in 0.4-1.5% of samples, and the lockout happens at near-zero flow rate. It is
the innovation gate, not the rate clamp. Widening `EK3_FLOW_I_GATE` admits
genuinely bad flow and was rejected for that reason.

### Position snap on recovery: tried, flown, reverted

The obvious follow-on - also snap the locked axis's position back to a
pre-lockout anchor advanced by the recovered velocity - was built as an option
bit and flown on the same floor. It re-anchored to a stale anchor during the
frequent lockouts, jumped EKF position 0.7-1.9 m at each of 14 recoveries,
tripped "flow aiding unhealthy", and made the hold worse (PN std 1.1 m, ~4 m
wander vs ~0.3 m the flight before). Neither Replay nor SITL can exercise it:
clean SITL dead reckoning does not drift, so there is no phantom position for
a snap to remove. Verdict: a 500 ms velocity recovery re-anchors often enough
that residual position drift is small; a snap has nothing reliable to remove.

### What the recovery cannot fix: a wrong height

On a second airframe (4-inch flow quad, log58, SmallFastDrone firmware
1737eb04) the reset fired twice and the vehicle still leaned to one motor.
The EKF had done a false climb (`VD` -0.2 m/s, `AZ` +0.48, baro primary near
ground) so the flow-scaling height inflated 0.16 -> ~1.0 m against a true
0.2 m; with the height 5x wrong every flow update re-rails both axes
immediately. That is the vertical stack's problem (#33359, #33507, #33478),
not this PR's.

### The near-ground floor (`EK3_FLOW_MIN_H`, same branch)

A distinct lockout at the very end of the same airframe's logs 65/66: the
vehicle settled onto the floor unseen (EKF thought 1.5 m, rangefinder 1-4 cm)
and below ~10 cm the ARK Flow cannot focus. `OF.Qual` still read 63-102 while
`FIX/FIY` railed 463 -> 4188 -> -6745; the EKF handed the controller a
confident phantom `VE` of -1.05 m/s while stationary on the floor and Loiter
braked it to +14 deg of roll. The rangefinder was correct down to 1 cm, so the
floor gates flow on rangefinder height: below `EK3_FLOW_MIN_H` (default
0.1 m) in flight the flow is treated as zero motion, which also makes the
lockout reset re-anchor to zero rather than to garbage. Fixing this in the
controller instead would have it reason about flow focus physics; the defect
is that the EKF reports a phantom with a small covariance.

Flown on the 4-inch quad, log67 (not committed), on the descent through the
floor (rangefinder 0.115 -> 0.054 m), log65/66 vs log67: `FIX/FIY`
+/-2000-6700 -> +/-200-500; `NI` pinned 255 -> 3-40; phantom `VN/VE` +/-0.5 ->
+/-0.1 m/s; DesRoll/Pitch +/-14 -> +/-2 deg; lockout-reset messages at disarm
-> none. Operator: "althold type behaviour close to the ground but no sudden
lean". Known limit: zeroed flow does not pin velocity against a continuous
strong divergence force (a 1.5 m/s^2 accel bias ran to 27 m/s in an early
test); that is not the near-ground failure, which is bad flow on a nearly
stationary vehicle, so it is out of scope.

### Diagnostic signature and mitigation

`XKF5.NI` pinned at 255 with one of `FIX`/`FIY` small and the other in the
thousands, no "stopped aiding" message, and one of `VN`/`VE` ramping linearly.
Until the fix is in, engage Loiter only from a settled hover: both clean holds
entered below 0.2 m/s; every flyaway was an acro-to-Loiter switch at speed.

## What is here

```
33484/
  README.md    <- this file
```

No real-flight logs are committed. Logs A, B, C (5-inch quad) and 58, 65, 66,
67 (4-inch quad) are cited by number only. The two autotests' SITL BINs could
be added under data/.

## Reproduce

```
git checkout pr-vel-flow-axis-gate
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.EK3_FlowAxisLockoutRecovery
Tools/autotest/autotest.py --no-configure test.Copter.EK3_FlowMinHeightFloor
```

The first injects `SIM_ACC1_BIAS_X=1.5` under optical-flow ALT_HOLD with
`EK3_OPTIONS=8`: the reset fires and velocity stays bounded; with the option
cleared no reset fires and groundspeed diverges past 4 m/s. The second hovers
at 3 m with the floor at 5 m and injects `SIM_FLOW_OFS_X=0.7`: floor active
bounds groundspeed below 1 m/s, floor off lets it exceed 1.5 m/s. The Replay
sweep and the position-snap result are real-log only.

## Branches and people

- `pr-vel-flow-axis-gate` - the PR branch (10 commits at the time of writing:
  recovery, autotest, 500 ms, `XKF7` diagnostics, reset-churn demotion,
  option-bit fix, `SIM_FLOW_OFS`, `EK3_FLOW_MIN_H` and its autotest).
- Author: @andyp1per. No review yet.
- Related: #33359 / #33507 (the height stack the log58 case needs), #33498
  (the yaw-drift trap found on the same 4-inch airframe), #33497 (its flow
  sensor's half-rate fault).
