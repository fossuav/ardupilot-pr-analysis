# Flow lane: re-entering relative aiding zeroes a velocity that was right (EKF3, upstream)

PR #34941, opened 2026-10-30 (this directory was
`pending-flow-aiding-reentry/` until then). Found 2026-10-30 on SFD-O4
log61 (3408138/639) and seen six more times on log65 (3408138/646), both
on the SmallFastDrone 4.7.2 beta `52b1d36f`. Real-flight numbers inline;
no logs committed.

## Status (one line)

Upstream behaviour, characterised on two real flights; both replay exactly
on the beta. Fix and autotest open as #34941 (head `247d0fb74e`),
replayed on both flights (see the last two sections). It is the
root of the SFD-O4 Loiter that did not stop (log61), with the terrain
lookup in `../33585/` deciding which way the velocity was wrong when the
pilot switched. 2026-11-04: tridge requested changes over a hard turn or
flip with no flow reading; measured on logs 61-70 and a SITL harness,
and a pass/fail test written for the PR (local `r1104/34941-tilt`,
`ca8ddec8a6` on top of the harness commit, to fold), see the last
section. Not pushed; not answered on the PR yet.

## What happens

Flow is not fused past 45 deg of tilt (`tiltOK`, `DCM33FlowMin` 0.71). On a
flow-only lane (core 1 under `EK3_SRC_OPTIONS` 8) a sustained steep attitude
in acro therefore starves it of flow. After 5 s `flowFusionTimeout` takes it
from AID_RELATIVE to AID_NONE, `readyToUseOptFlow()` is still true, so the
next cycle puts it back into AID_RELATIVE, and the mode change calls
`ResetVelocity()`, which zeroes horizontal velocity whenever the mode is not
AID_ABSOLUTE (`AP_NavEKF3_Control.cpp` `setAidingMode()`,
`AP_NavEKF3_PosVelFusion.cpp` `ResetVelocity()`). Derived from the source;
the timings and speeds below are measured. In the log it is the pair
"EKF3 IMU1 stopped aiding" / "started relative aiding", 5-6 ms apart.

The velocity it discards was good. Five seconds on the IMU alone had kept it
within about 0.5 m/s of GPS:

| Log | Drop | GPS speed | Core 1 before | Core 1 after | Tilt over 45 deg in the 5 s before |
|---|---|---|---|---|---|
| log61 | 220.5 s | 18.6 m/s | 17.9 (220.0 s), 18.1 | 0.8 | from 215.7 s (innovations frozen) |
| log65 | 51.4 s | 18.7 | 18.9 | 0.3 | 100% |
| log65 | 113.4 s | 22.2 | 17.5 | 4.3 | 100% |
| log65 | 128.2 s | 18.5 | 39.2 (already wrong) | 0.7 | 100% |
| log65 | 144.9 s | 12.9 | 11.4 | 2.5 | 56% |

(Times are normalised to the first message, as `log_extract.py` prints them.
log65 also dropped at 78.0 s and stayed out for 4.6 s, re-entering at 82.6 s
with core 1 at 0.1 against GPS 18.2.)

## What repairs it, and when nothing can

Nothing re-anchors a zeroed flow velocity except #33484's single-axis
lockout reset, and that needs the AGL KF valid and a range sample within
500 ms. log65, mostly inside the range finder's reach, had three, each
repairing a velocity zeroed by a re-entry (`../33484/`, 2026-10-30): 4.7 to
18.9 m/s, 0.1 to 20.7, 1.7 to 16.1. Where no reset followed, core 1 stayed
wrong for 8 s or more (after 113.4 s: 4-8 m/s against 16-25).

log61 was above the 15 m range finder, so no reset could run. Core 1 ran
away to 37-48 m/s between two more drops (235.3 and 240.3 s), ended 200-340 m
from GPS, and read 0.3-0.9 m/s while flying at 13 m/s when the pilot
selected Loiter at 255.8 s. Loiter seeded its velocity I term from the
31 deg lean (6 m/s/s), saw no motion and held the lean as if into wind
(PIDE.I 6.0 rising to 8.9). Loiter on the GPS lane later stopped from
10.5 m/s in 1.8 s, so Loiter is not at fault.

## Prior art in the stack

#33568 already exempts one edge: it skips the velocity and position resets
on AID_ABSOLUTE -> AID_RELATIVE (`PV_AidingModePrev != AID_ABSOLUTE ||
PV_AidingMode != AID_RELATIVE`), because a GPS-to-flow fall back on a
moving vehicle stepped velocity 5.9 m/s (`../33568/`, 2026-09-15). The
re-entry here is the same mistake on the NONE -> RELATIVE edge.

## Fix to try (not written, not measured)

Keep horizontal velocity across a NONE -> RELATIVE re-entry when the lane
left RELATIVE moments ago, inflating its variance for the time spent on the
IMU alone rather than resetting it; or do not let the timeout fire while the
tilt gate is the only reason flow is not being fused. Which is better is a
measurement, not an argument.

## Replay

Both logs replay exactly on the beta (log61 core 1 to 0.1 m/s through
256 s; Replay built at smallfastdrone `0cb49e7dfb`, which is `52b1d36f` plus
an autotest commit). The A/B owed: the fix against the flown code on log61
(core 1 speed at the 255.8 s Loiter switch, GPS 13.4 m/s) and log65 (core 1
against GPS after each of the six drops). Recorded in `../REPLAY_LOGS.md`.

## Rule

Candidate, not queued: a reset replaces a state only with an estimate
better than the one it discards. Time since the last measurement alone is
not evidence the state is bad. Offered 2026-10-30, not yet confirmed.

## 2026-10-30 (later): prototyped and replayed

The timeout's own comment says it is for flow "rejected for too long". A
sample the tilt check withheld was not rejected, so the prototype counts
the timeout from the later of the last fused and the last withheld sample
(`flowTiltWithheldTime_ms`, set where `SelectFlowFusion()` skips
`FuseOptFlow()` on `tiltOK`). Rejected flow still times out after 5 s and
resets as before. Skipping the reset on the NONE -> RELATIVE re-entry
alone would not work: the velocity is zeroed on the way *out*, at the
RELATIVE -> NONE change, which also resets the height to baro.

Local branch `pr-ekf3-flow-reentry` on master `278a68a57a`, commit
`d2bebe7f32`, not pushed. SITL copter builds; `OpticalFlow`,
`OpticalFlowLocation` and `OpticalFlowLimits` pass. No autotest for the
change itself yet: it needs a flow-only vehicle held past 45 deg for over
5 s.

Replay through a port to the beta (`52b1d36f` plus the same four hunks, a
detached scratch worktree), flow core against GPS over the whole flight:

| Log | Speed error rms / p95 | Time over 3 m/s off | Worst position error | Aiding timeouts | Lockout resets |
|---|---|---|---|---|---|
| log61 (639), flown code | 9.5 / 21.8 m/s | 47% | 466 m | 4 | - |
| log61, prototype | 4.0 / 8.8 m/s | 33% | 313 m | 0 | - |
| log65 (646), flown code | 9.2 / 19.0 m/s | 45% | 333 m | 6 | 3 |
| log65, prototype | 2.6 / 5.2 m/s | 18% | 95 m | 0 | 0 |

At log61's Loiter switch (255.8 s, GPS 13.2 m/s) core 1 reads 10.6 m/s
instead of 1.2, and 9.3 with `EK3_OPTIONS` bit 2 off, so the terrain
lookup no longer decides it; why it still reads about 3 m/s low at 25 m,
above the range finder, is not established. Replay feeds the terrain
heights the flight looked up at core 1's flown position, which this
change would have moved, so log61's terrain path is not fully tested. On
log65 the three lockout resets are no longer needed: they were repairing
the zeroed velocities. log63 (643), hovers and full-stick Loiter, replays
identically (0 of 5568 XKF1 records differ).

## 2026-10-30 (later): reviewed, rewritten as v2

A /pr-review round on `d2bebe7f32` (Claude per-commit and whole-diff
readers, Codex verify and cold passes) asked for changes. The withheld
stamp was set on every update that had flow data and a bad tilt, whether
or not the lane fused flow at all, so a lane not using flow could hold off
its own timeout. Restarting the 5 s window from each withheld sample meant
flow that was rejected while level and withheld while banked, alternating,
never timed out (root playbook ARCH-5: a gate is judged by what it does
when it is wrong). The comparison was not wrap-safe, the comment
overstated what the stamp meant, the commit message claimed more than the
replay showed, and there was no autotest.

Two rewrites, both on master `278a68a57a`, were replayed through the beta
port on logs 61 and 65:

- R: keep the restart, gate the stamp on the lane fusing flow, and make
  both elapsed-time tests wrap-safe.
- P: count the withheld time instead (`flowWithheld_ms`), only while the
  lane fuses flow (`fuse_optflow`), adding at most 1 s per gap between
  samples (`flowSampleTime_ms`) so missing flow still counts as missing,
  and subtract it from the time since the last fusion. Zeroed wherever
  `prevFlowFuseTime_ms` is set.

R and P replay identically on both logs (0 differing records) and log63
is unchanged under either: log61 flow lane speed error rms 9.53 -> 3.97
m/s and log65 9.23 -> 2.56, aiding timeouts 4 -> 0 and 6 -> 0. They differ
only on mixed tilts, which these flights did not exercise; P is kept
because rejected flow still times out there (derived from the source,
not measured).

Local branch `pr-ekf3-flow-reentry-v2`, not pushed:

- `e04ef8c2ab` "AP_NavEKF3: do not time out flow aiding while the tilt
  check withholds it" (variant P, 16 lines in four files).
- `e0cf64b080` "autotest: check a banked flow lane does not time out":
  `OpticalFlowTiltNoTimeout` in tests1e. A control first sets
  `SIM_FLOW_ENABLE 0` and must see "IMU1 stopped aiding"; then a flow-only
  core is banked 55 deg in ACRO at 55-65 m (checked above 47 deg) for 7 s
  and must not time out. Fails on master 5 s into the bank, passes with
  the fix; flake8 clean.

`pr-ekf3-flow-reentry` (`d2bebe7f32`) is kept for comparison.

## 2026-10-30 (later): second review round, v3

A second round on v2 (Codex audit of the six round-1 findings, Codex and
Claude cold reads) closed all six and found nothing must-fix. Changed in
v3:

- The 1 s cap still credited the first second of a longer gap as
  withheld, against what the comment and message said. A gap of 1 s or
  more (EKF3's flow valid time, `flowDataValid`) now credits nothing.
  Replayed on the beta port: logs 61, 63 and 65 are identical to variant P
  (0 EKF records differ; only Replay's own startup EV timestamps and NaN
  fields compare unequal), so the numbers above stand for v3.
- The test reached the bank with flow back on only because `context_pop()`
  restored `SIM_FLOW_ENABLE`. It now turns flow back on and waits for "IMU1
  fusing optical flow".
- The level flow-loss control could not tell this design from one that
  never times flow out while tilted. A third subtest stops the flow at the
  end of the 7 s bank, still banked, and expects "IMU1 stopped aiding"
  4-10 s later. SITL, 2026-10-30, same test on three builds: master fails
  (times out 5 s into the bank), a variant that suppresses the timeout
  while tilted fails (no timeout when the flow stops banked), the fix
  passes (timed out 5.4 s after the flow stopped, roll at least 54.7 deg).
  Timed from before the parameter set; from after it, the first run read
  4.6 s, too close to the 4 s floor.
- The commit message now says the timeout fires once 5 s of rejected or
  missing flow has built up since the last fusion, however interleaved
  with tilts, and that while the tilt lasts the lane dead-reckons with its
  velocity variance growing. The header comment on `flowSampleTime_ms`
  no longer says only used samples set it.

Declined, with the reason:

- Reset `flowSampleTime_ms` on re-entry to relative aiding, so the first
  withheld sample cannot credit time from before entry. Re-entry needs
  flow within 200 ms (`readyToUseOptFlow()`), so the over-credit is one
  sample interval at most, and the timeout's `MIN()` stops it underflowing.
- Move `fuse_optflow` back inside a flow-data branch to save its
  evaluation on updates with no flow. A few comparisons; it would re-indent
  the existing block for nothing measurable.

For the PR text, not the code (derived from the source, not measured):
while a tilt lasts nothing bounds the coast. Before, the lane's velocity
was zeroed every 5 s with a variance set to the GPS velocity noise, which
is confident and wrong; now the variance grows, so when the vehicle levels
the innovation gate is wide and flow is accepted rather than rejected. A
vehicle that holds a flow lane past 45 deg for long periods (a tailsitter
in forward flight) would now coast for as long as it does; whether any
setup runs a flow lane there is not established.

Local branch `pr-ekf3-flow-reentry-v3` on master `278a68a57a`, not pushed:
`8412571a33` (EKF3) and `247d0fb74e` (autotest). Gate clean except the
73-character subject note. v2 (`e04ef8c2ab`, `e0cf64b080`) is kept.

## 2026-10-30 (later): opened as #34941

Pushed by Andy as `pr-ekf3-flow-tilt-timeout` (the v3 commits
`8412571a33` and `247d0fb74e` on master `278a68a57a`) and opened as
#34941 the same day. Before writing the description the replay A/B was
re-run on v3's own outputs, since the p95, time-off and worst-position
columns above had been measured on the first prototype: v3 reproduces
every figure (log61 rms 9.53 -> 3.97, p95 21.80 -> 8.83, over 3 m/s off
47.4% -> 33.3%, worst position against the GPS lane 466 -> 313 m; log65
9.23 -> 2.56, 18.99 -> 5.16, 45.0% -> 18.2%, 333 -> 95 m). The
description carries that table, the three-build autotest result and the
coast-while-tilted point; a before/after plot of flow lane speed against
GPS on both flights, as flown and with the change, is to be attached by
hand (gh cannot upload images).

## 2026-10-30 (later): on SFD refresh12

On SFD refresh12 (topup1: `649e160e9c`, test `42bd2a3b79`) the EKF
commit met #33484's and #34543's flow state in four additive conflicts;
the resolved diff against the stack is the PR's exactly.
OpticalFlowTiltNoTimeout passes there (timed out 5.2 s after the flow
stopped, roll held at 54.7 deg or more) and fails with the EKF commit
reverted ("flow lane timed out while banked"). Flight evidence is owed:
an acro hold past 45 deg on the flow lane inside the range finder's reach
(refresh12's `Tools/SFD/FIELD_PLAN.md`, "Additions for refresh12").

## 2026-10-31: flown, SFD-O4 logs 69 and 70

SFD refresh12 topup3, firmware `ea8cef60` (the flight card commit, same code as `f93bd10a`), flight card item 4. Flow ran on core 1 in both logs: log69 was
GPS-primary for most of its acro and log70 flow-primary throughout. They
held 18 stretches over 45 deg lasting more than 5 s: up to 31 s, 45-75 deg,
10-25 m/s, through flips.

Neither log has a "stopped aiding" / "started relative aiding" pair in
flight (log65 had six pairs, each zeroing core 1), and core 1's speed was
never zeroed. The range was good only in parts (log70 162-167 s and
217-222 s, 9.5-14 m), and there core 1 stayed within 1-3 m/s of GPS. Above
the range finder it read up to 14 m/s high (log69 129-136 s), which is flow
scale error. Replay matches both logs on both cores to 1e-7. Passed.

## 2026-11-04: tridge's hard-turn review, measured

tridge (CHANGES_REQUESTED, dev call 2026-11-04): a hard turn or a flip
with no flow reading in it could leave the lane worse with this change;
the usual answer is to take the first, possibly bad, reading after the
gap. Measured at PR head `247d0fb74e` against its base `278a68a57a`.

### The flights (tier 1)

`tools/tilt_recovery.py`: a stretch is a run of the flow core's own
cos(roll)cos(pitch) at or below 0.71; a flow update is an XKF5 record for
that core whose FIX/FIY/NI changed, accepted when NI is under 100; the
velocity error is core 1 against core 0, the GPS lane. XKF5 comes at the
flow rate, so times are to 0.1 s. Stretches of 1 s or more.

SFD-O4 logs 69 and 70, flown with this change (refresh12 topup3):

- 21 stretches of 5.0 to 19.3 s, the case the change alters. The first
  flow update after levelling was accepted after 17 of them; after the
  other 4 it was rejected 1, 2, 3 and 5 times and accepted 0.2 to 0.6 s
  after levelling. No timeout in either flight. The coasted velocity was
  2.2 to 13.9 m/s off at levelling (1.0 to 7.4 at the start of the
  stretch) and 0.4 to 7.8 m/s off 2 s later. Large coasted errors passed
  the gate: 10.3 m/s at 9 m HAGL after 14.4 s (NI 29), 8.4 m/s at 8 m
  after 19.0 s (NI 58). The velocity variance had grown with the coast.
- 17 stretches of 1.4 to 4.6 s, where the change does nothing. The first
  update was rejected after 6 of them, and flow was accepted again only
  after 0.3 to 9.8 s (1 to 39 rejected updates).

SFD-O4 logs 61 and 65, flown without it (beta `52b1d36f`): 6 stretches
of 5.4 to 14.1 s, each with the timeout firing inside it and the velocity
zeroed, 11.0 to 24.7 m/s off at levelling, the first update rejected
after 4; and 21 stretches of 1.0 to 4.4 s, the first update rejected
after 6, flow accepted again after up to 10.5 s.

So a lane that rejects the returning flow for seconds is real, but in
these flights it followed short stretches, on both builds. After the long
stretches this change covers, the returning flow was taken within 0.6 s.
Where rejection after a short stretch ran into a second tilt (log70
260.7 s and 303.4 s), the credit kept the lane from timing out, which
on master would have zeroed it at 20 and 14 m/s.

### SITL (tier 2)

`OpticalFlowTiltRecovery`, a measurement harness (local
`r1104/34941-harness`, `2e7606da05` on the PR head; also
`tools/OpticalFlowTiltRecovery-harness.patch`): core 0 on GPS flies the vehicle; core 1, flow only, is measured
against SITL truth. Turns banked 55 deg at 70 deg/s from 11 m/s for 3, 8
and 15 s; one FLIP, and three back to back; at 12 and 30 m; with a
compass yaw for the flow core, with none, and with a 3% gyro scale error
on all axes. A 1% yaw gyro scale error is on in every case. Both builds
also carry `tools/xkf5_all_cores.py`, a logging-only change so XKF5 is
written for the flow core (master logs the primary only); binaries md5
`1913fd01` (PR) and `d0e18d80` (base), different. Three runs each,
interleaved; median (range). Velocity errors are in each attitude's own
yaw frame.

| Leg | Build | Error at levelling m/s | First sample accepted | Error +2 s / +10 s | Position error at +10 s | Timeouts |
|---|---|---|---|---|---|---|
| compass 12 m, 8 s | base | 10.3 | 3 of 3 | 9.8 / 8.9 (1.1-8.9) | 127 m | 1 |
| | PR | 1.2 | 3 of 3 | 0.3 / 0.1 | 3.4 m | 0 |
| compass 12 m, 15 s | base | 10.4 | 1 of 3 | 9.3 / 1.2 | 150 m | 3 |
| | PR | 1.0 | 3 of 3 | 0.2 / 0.1 | 2.4 m | 0 |
| compass 30 m, 15 s | base | 10.8 | 3 of 3 | 10.9 / 5.7 | 203 m | 3 |
| | PR | 2.8 | 3 of 3 | 1.4 / 0.7 | 3.6 m | 0 |
| no yaw 12 m, 8 s | base | 10.3 | 3 of 3 | 9.7 / 9.7 (1.3-10.4) | 131 m | 1 |
| | PR | 1.4 | 3 of 3 | 0.2 / 0.1 | 6.2 m | 0 |
| no yaw 30 m, 15 s | base | 10.6 | 3 of 3 | 10.1 / 1.8 | 169 m | 3 |
| | PR | 2.4 | 3 of 3 | 0.9 / 0.3 | 3.5 m | 0 |
| gyro 3% 12 m, 15 s | base | 10.4 | 1 of 3 | 9.4 / 0.8 | 136 m | 3 |
| | PR | 2.9 | 3 of 3 | 0.8 / 1.4 | 10.0 m | 0 |
| gyro 3% 30 m, 15 s | base | 10.7 | 3 of 3 | 11.2 / 9.3 | 219 m | 3 |
| | PR | 7.1 | 3 of 3 | 3.7 / 1.9 | 10.5 m | 0 |

The 3 s turns and the flips, under 5 s, match where both lanes started
clean (compass 12 m 3 s: 0.5 m/s at levelling on both, accepted, no
timeout). Later short legs on the base inherit a lane still 1 to 5 m/s
off from the long turn before it, which its zeroed velocity is slow to
shed even with 8 s at rest between legs; the full table is
`data/OpticalFlowTiltRecovery-2026-11-04.csv`, regenerated by
`tools/sitl_csv_summary.py`. Over all 54 legs the PR accepted the first
returning sample every time and never timed out. The base timed out in
every 8 and 15 s turn and zeroed a velocity of about 10 m/s; it then
accepted flow, but the zero's small variance left it 6 to 12 m/s off for
5 s or more.

What SITL does not capture: its IMU is clean, so the coast drifts 1 to
3 m/s over 15 s (7 m/s with the 3% gyro scale error) where the flights
drifted 2 to 14 m/s. No SITL leg pushed the coast outside the gate, so
the PR's own worst case, rejected flow timing the lane out 5 s after
levelling, has not been produced in SITL or seen in flight.

### What this says about the variance widening proposed this morning

After a long stretch it would rarely fire (4 of 21 in flight, each
resolved by itself in 0.6 s; none in SITL). The long rejections are after
short stretches, on both builds, so widening there addresses an existing
gap rather than one this change opens. Those rejections may be right:
in log70 the range finder was out of range or had no data in the second
after levelling for 5 of the 6 short stretches whose flow was then
rejected, and in range for 7 of the 8 long stretches whose flow was
accepted (`RFND.Stat`). Without a range the flow is scaled by the
terrain estimate, which can be wrong, and taking the reading would pull
the velocity off. If it is written it is its own change, measured
against logs 61, 63, 65, 69 and 70.

Pass/fail check proposed for the PR from the harness: the 12 m, 8 s
compass turn, flow core velocity error 2 s after levelling under 2 m/s
and no "IMU1 stopped aiding" (PR 0.3 m/s in 3 runs, base 9.5 to 9.8).
That uses XKF1, which master logs for every core, so it does not need
the XKF5 change.

### The test for the PR (2026-11-04, later)

Andy's call: add a pass/fail test to the PR; he answers tridge with the
numbers. `OpticalFlowTiltTurnRecovery` keeps two of the harness legs at
12 m, flown in one flight: an 8 s banked turn with a compass yaw, then a
15 s turn with no yaw source for the flow core (dropped in flight, as
arming needs the cores' yaws to agree), with the 1% yaw gyro scale error
throughout. It reads only XKF1, which master logs for every core, and
SITL truth (SIM, SIM2), and fails if the flow core's velocity is more
than 2 m/s off 2 s after levelling or "IMU1 stopped aiding" is seen from
the start of a turn to 6 s after levelling. The other harness legs were
dropped for runtime.

The XKF5 logging change was reverted in both worktrees and both
binaries rebuilt: PR at `ca8ddec8a6`, md5 `549a3242`; base `278a68a57a`
with the test file copied in, md5 `87ce81f0`, the same as before the
logging change. Three runs each, 2026-11-04 (tier 2):

| Build | 8 s turn, compass yaw | 15 s turn, no yaw source | Result |
|---|---|---|---|
| PR `247d0fb74e` + test | 0.07, 0.05, 0.04 m/s, no timeout | 0.32, 0.32, 0.33 m/s, no timeout | pass 3 of 3 |
| base `278a68a57a` + test | 10.08, 10.07, 9.53 m/s, 1 timeout | 10.47, 11.49, 11.12 m/s, 3 timeouts | fail 3 of 3 |

The flow core's velocity error 2 s after levelling, against a 2 m/s
limit: the PR is at a sixth of it, the base at five times it. The turns
held flow off for 8.0 to 8.1 s and 15.1 to 15.3 s. Wall time about 6 to
7 s a run here, the same as the PR's OpticalFlowTiltNoTimeout on the
same host. Tools/scripts/check_branch_conventions.py passes and
arducopter.py is flake8 clean.

Rewriting the harness commit needs a push grant, so the test is a
second commit, `ca8ddec8a6`, on top of the harness commit `2e7606da05`.
Its message is the one the folded commit should carry; together they
add only the test (128 lines in arducopter.py against the PR head).

## 2026-11-04: test pushed and tridge answered

Pushed `247d0fb74e` -> `38635910f0` (fast-forward): OpticalFlowTiltTurnRecovery. Reply to tridge's review with the flight and SITL numbers: https://github.com/ArduPilot/ardupilot/pull/34941#issuecomment-6633996392
Plain-language explainer posted 2026-11-04 (master gives up after 5 s and is sure the vehicle stopped, so it rejects the first flow reading; this PR keeps a growing-uncertainty estimate, so the first reading is taken; flips and sub-5 s turns unchanged): https://github.com/ArduPilot/ardupilot/pull/34941#issuecomment-6634720930

## 2026-11-04 (night): AP-Review round 2 at 38635910f0

COMMENT. Low: the tilt credit is cleared only by an accepted fusion (OptFlowFusion.cpp:707), so after a tilt under 5 s whose first returning flow is rejected the lane coasts up to 5 s after levelling before timing out, where master times out 5 s after the tilt began (bot SITL, 4 s bank: 4.8 s against 0.8 s). That qualifies the reply and the explainer posted earlier ("a flip or a turn under 5 s is unchanged"): true when the first flow after levelling is fused, not when it is rejected. Correction drafted, not posted; whether to clear the credit when the tilt ends is Andy's decision. Minor (uncapped credit for long tilts) unchanged.

## 2026-11-06: reply posted

https://github.com/ArduPilot/ardupilot/pull/34941#issuecomment-6684179265

## 2026-11-07: flown again at the head, SFD-O4 log84 (tier 1)

The SFD beta (refresh13 topup1, build reporting `ea9c6ab5`) carries this
PR at the head `38635910f0`. SFD-O4 log84 (3408138/693): 211 s of ACRO
outdoors at 10-27 m/s and up to 50 m, core 0 on GPS and primary, core 1
on flow (`EK3_SRC_OPTIONS` 8), mostly above the 15 m range finder. Six
stretches held over 45 deg of tilt for 5.1-8.7 s, with the range finder
good for 0-29 % of each. Core 1 stayed in relative aiding from boot to
disarm, with no "stopped aiding" / "started relative aiding" pair and no
lockout reset (XKF7.FVC 0). Above 5 m/s its speed was a median 0.83 m/s
from GPS (95th percentile 2.33, worst 4.06), against 0.15 / 0.59 / 2.22
for core 0, which fuses GPS, so that part is the timing between the two.
As on logs 69-70 (2026-10-31, the earlier head), the lane was never
zeroed.
