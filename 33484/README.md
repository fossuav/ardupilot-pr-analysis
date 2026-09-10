# PR #33484 - recover horizontal velocity from a single-axis optical-flow lockout

Analysis archive for [ArduPilot/ardupilot#33484](https://github.com/ArduPilot/ardupilot/pull/33484).
Branch `pr-vel-flow-axis-gate` (andyp1per fork), base `master`, head
`bfb41f69a1` (11 commits) since the two flight-test fixes were pushed
2026-09-10. Real-flight
numbers are cited inline; no real-flight logs are committed here. Option bits
and log message names below are the upstream ones (AglKfForOptflow is
`EK3_OPTIONS` bit 3, the AGL KF logs as `XKFA`); the flights were flown on the
SmallFastDrone branch, where the same option is bit 4 and the message is
`XKF6`.

## Status (one line)

**Superseded in part on 2026-09-04 - see `split-and-quality-gate.md`.** The
floor is now its own PR (#34292) and the branch has gained `EK3_FLOW_QMIN`.
Everything below about the mechanism, the flights and the Replay tuning
still stands. First outdoor acro flight 2026-09-09: three resets, two
of them re-anchoring to a velocity a fifth of truth, all at the moment the
vehicle came back above the flow tilt gate. Both fixes written
2026-09-09, and the Replay sweep that tuned the threshold is what settled
them: the range-freshness gate suppresses all three outdoor misfires and
none of the indoor recoveries.

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

### Flight-tested in acro 2026-09-09: the recovery misfires at the tilt gate

First outdoor acro flight of the recovery (log7, not committed). Outdoor
BF_X quad, `EK3_SRC_OPTIONS=8` so a flow-only core ran beside a GPS core on
the same sensors, 1927 m of ACRO path at 14.0 m/s median and 20.6 m/s p95.
`EK3_FLOW_QMIN=0`, so the quality gate from `split-and-quality-gate.md` was
disabled and every lockout re-anchored.

`XKF7.FVC` reached **3** on the flow core, while only two statustexts were
emitted. Two of the three re-anchored to a badly wrong velocity:

| # | t (s) | cos(tilt) | flow core abs V before -> after | raw GPS |
|---|---|---|---|---|
| 1 | 217.376 | 0.732 (43 deg) | 13.98 -> **6.58** | 12.28 |
| 2 | 241.076 | 0.749 (42 deg) | 14.67 -> **2.87** | 12.71 |
| 3 | 241.576 | 0.792 (38 deg) | 4.31 -> 14.77 | 14.61 |

Steps of 8.6 and 12.5 m/s in one 100 ms sample; reset 3 was reset 2's
cleanup half a second later. Harmless on this flight only because the flow
core was never primary. On a flow-only vehicle each is a large velocity
step into the position controller at speed.

**It is not the 500 ms threshold.** All three fired in the first samples
after `cos(tilt)` climbed back through `DCM33FlowMin` (0.71). That gate
stops flow fusion and AGL KF range fusion together, so it both creates the
single-axis staleness the lockout detects and leaves `aglKfH` coasting at
the moment `ResetVelocityToFlow` needs it as a scale factor. Measured on
this flight:

- 28.6% of the ACRO segment sat below the gate - 15 runs over 0.5 s,
  longest 4.0 s - against 0.0% and 2.3% in the two LOITER segments. No
  indoor log in this record could have shown this.
- Through those windows the AGL KF coasts systematically low, because
  `aglKfV` holds a 1-2 m/s phantom descent and integrates it. Error
  against the tilt-corrected rangefinder: 0.22 m RMS below 18 deg of
  tilt, 0.40 m at 18-32 deg, 0.61 m at 32-45 deg, **2.18 m at 45-53 deg**,
  2.65 m beyond. Worst single sample -6.40 m.
- At reset 2, `aglKfH` was 2.20 m against a true vertical AGL of 6.23 m.

*Derived from the source*: `ResetVelocityToFlow` inverts the LOS model, so
the recovered velocity is linear in `range = heightAboveGndEst /
prevTnb.c.z`, and with bit 3 set `heightAboveGndEst` is `aglKfH`. A height
at a third of truth scales the re-anchor by the same third, which is the
direction and roughly the magnitude observed.

This is the same class as "What the recovery cannot fix: a wrong height"
above, and it revises the conclusion drawn there. That finding put a
5x-wrong flow-scaling height down to the vertical stack and called it not
this PR's problem. It is still the vertical stack's fault that the height
is wrong, but the reset consumes that height without checking it, and here
it consumed one whose staleness was already knowable from
`lastAglRngFuseTime_ms`. The fix below is cheap and belongs on this side.

### Proposed fix 1 (written 2026-09-09): gate the reset on range freshness

The reset requires `aglKfValid`, which survives 5 s without a range
fusion - long enough for the height to coast metres low. #33478 computes
`aglKfRngCurrent` (500 ms since the last fusion) for its velD gate;
master does not carry the `aglKfRngGapMax_ms` constant, but it does carry
`lastAglRngFuseTime_ms` and `aglKfValid`, so this branch can define its
own freshness window without stacking on #33478.

All three of these resets had been without range for longer than 500 ms,
so the gate would have suppressed all three. The open question is whether
it also suppresses the recoveries logs A/B/C wanted. That is answerable
without flying: rerun the existing Replay sweep with the gate in, on all
three logs, and read the excursion/reset table the same way. If the
indoor peaks stay near their 500 ms values the gate is free.

Consider pairing it with a blended rather than stepped re-anchor. 12.5 m/s
in one 100 ms sample is not a correction a position controller can absorb,
and the position-snap experiment already in this record shows that big
instantaneous corrections on this path make hold quality worse, not
better.

### Proposed fix 2 (written 2026-09-09): make the reset count visible

`flowVelResetWindowCount == 1` gates the statustext to once per
`FLOW_RESET_WINDOW_MS` (10 s) while `FLOW_RESET_MAX_IN_WINDOW` allows 5,
so up to four resets per window are silent. On this flight that read as
"two resets" when there were three, and the missing one was the
interesting half of a pair. `XKF7.FVC` has the truth but nobody reads it
live. Either put the count in the message or emit on every reset and let
the existing `flow aiding unhealthy` message carry the churn warning.

### Both fixes written 2026-09-09, and the open question is answered

`SmallFastDrone-4.7.1-beta` over base `fd37f6f5fa`:

| fix | commit (beta branch) | commit (this PR) |
|---|---|---|
| 1 range freshness | `23299c535c` | `bfb41f69a1` |
| 2 reset count visible | `ad8cc7fbf3` | `e49918639e` |

Both pushed to the PR 2026-09-10 and explained in
<https://github.com/ArduPilot/ardupilot/pull/33484#issuecomment-5617276651>,
which states the master caveat rather than leaving a reviewer to find it.

Fix 2 took the "emit on every reset" option rather than the count-in-the-
message-once option, and carries the running `flowVelResetCount` so the
statustext lines up with `XKF7.FVC`. The window still bounds the traffic:
`flowVelResetUnhealthy` sets at `FLOW_RESET_MAX_IN_WINDOW`, feeds
`flowFusionTimeout` in `AP_NavEKF3_Control.cpp:326`, drops the filter out
of `AID_RELATIVE`, and the reset path is gated on `AID_RELATIVE`, so five
messages per window is the ceiling. *Derived from the source, not
measured.*

**Withdrawn 2026-09-10, and it was labelled derived for exactly this
reason.** The derivation missed that the window has to be *reached*. It only
restarts on a reset more than `FLOW_RESET_WINDOW_MS` after the one that
opened it, so a reset period T reaches `floor(10000/T) + 1`, and
`FLOW_RESET_MAX_IN_WINDOW` needs T <= 2.5 s. For T between 2.5 s and 10 s the
count tops out at 4, `flowVelResetUnhealthy` never latches, and the messages
continue indefinitely - at T = 2.6 s that is 0.385 Hz against the old code's
0.096 Hz. Leaving `AID_RELATIVE` additionally needs `bodyOdmFusionTimeout`
(`Control.cpp:313`), so a vehicle fusing body odometry alongside flow never
leaves it and keeps resetting either way. There is no ceiling; the reset rate
is the only bound.

Fix 1 defines its own `FLOW_RESET_RANGE_MAX_AGE_MS` (500) locally rather
than using this branch's `aglKfRngGapMax_ms` member, so it ports to this
PR without stacking on #33478, as argued above. Independence of *code* did
not buy independence of *evidence*, though - see the master Replay result
below. The 500 ms is now justified against `AP_NavEKF3_Measurements.cpp`'s
own three-sample median freshness bound, which is on master, rather than
against #33478's constant, which is not.

The gate sits in the outer condition, not on the reset branch. On the reset
branch a stale range falls through without refreshing `flowFuseTimeAxis_ms`,
so the lockout predicate stays true on every later sample and the
low-quality branch above is re-evaluated on each one - a single poor sample
then latches `flowVelResetUnhealthy` for the flight. Found in review
2026-09-10, before anything was pushed.

#### The Replay sweep, rerun with the gate in

This is the measurement the section above asked for, and it is decisive:
**the gate is free.** Run 2026-09-09 at the commits above, gate present
vs the same tree with `23299c535c` reverted, everything else identical.

| log | resets, no gate | resets, with gate | peak excursion, either way |
|---|---|---|---|
| log7 (outdoor acro) | 3 | **0** | - |
| A | 10 | 10 | 2.8 m |
| B | 14 | 14 | 19.5 m |
| C | 5 | 5 | 28.6 m |

All three outdoor misfires are suppressed and not one indoor recovery is.
The indoor excursions are identical to the metre either way, which is the
stronger half of the result: the gate does not merely leave the reset
count alone, it leaves the trajectory alone.

**That result belongs to this branch, not to master (2026-09-10).** Replayed
on the PR's own master-based tree the same log fires **two** resets with the
gate and two without - it suppresses nothing there, because on master the
range is fresh at both. The 3 -> 0 above was measured on
`SmallFastDrone-4.7.1-beta`, which carries the AGL KF work of #33359 and
#33478; something in that stack is what lets `lastAglRngFuseTime_ms` go
stale at the tilt-gate crossings. Both write sites for that timestamp are
identical on the two trees, so the difference is in the surrounding
conditions and has not been run down. The commit against #33484 therefore
cannot claim this measurement, and says so.

The mechanism is the obvious one once measured. Indoors the rangefinder
is in range and the AGL KF keeps fusing it, so the range is always fresher
than 500 ms at the moment the lockout fires. Outdoors on log7 the
rangefinder was above its range and the tilt gate had stopped range
fusion, which is the same event that created the lockout.

**These excursion numbers are a different measurement from the threshold
sweep table earlier in this file, not a correction to it.** That table was
taken on the tuning branch at its own head; this one is base `fd37f6f5fa`
plus the six 2026-09-09 fixes, which include a `getHAGL` change and three
ground-effect changes. Read each table internally, not across.

Two notes on method, because both cost time:

- Replay logs its re-run cores at `C+100`; `C<100` in the output BIN is
  the original flight passed through. Reading `XKF1` without filtering
  reproduces the flight's own peak excursion exactly and looks like a
  result. `Tools/Replay/check_replay.py` is where that convention is
  written down.
- `XKF7`'s format record is lost to a reader desync in these logs, so the
  reset counts above are counted from the statustexts Replay emits. That
  is sound here only because the source logs were checked and carry none
  of their own: log C has 44 `MSG` records and not one is reset-related.

#### Still outstanding

- The blended re-anchor. Not attempted; still the right next question,
  and still a separate commit if it is done.
- Whether `SIM_FLOW_OFS` can drive a `DCM33FlowMin` crossing, which is
  what an autotest for the tilt-gate case would need. Not investigated.
  The existing `EK3_FlowAxisLockoutRecovery` passes with the gate in, so
  the recovery itself is still covered; what is uncovered is the misfire.

### Validation route for both

log7 carries `LOG_REPLAY=1`, so the acro half replays; logs A/B/C give the
indoor half. Both are the existing sweep harness, not new work. A SITL
test for the tilt-gate case would need a manoeuvre that crosses
`DCM33FlowMin` with flow enabled, which `SIM_FLOW_OFS` does not currently
provide - worth checking whether it can before assuming an autotest is
possible here.


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
