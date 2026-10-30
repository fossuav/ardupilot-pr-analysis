# Flow lane: re-entering relative aiding zeroes a velocity that was right (EKF3, upstream)

Not a PR yet. Found 2026-10-30 on SFD-O4 log61 (3408138/639) and seen six
more times on log65 (3408138/646), both on the SmallFastDrone 4.7.2 beta
`52b1d36f`. Real-flight numbers inline; no logs committed.

## Status (one line)

Upstream behaviour, characterised on two real flights; both replay exactly
on the beta. Fix and autotest on local branch `pr-ekf3-flow-reentry-v3`,
replayed on both flights, not pushed (see the last section). It is the
root of the SFD-O4 Loiter that did not stop (log61), with the terrain
lookup in `../33585/` deciding which way the velocity was wrong when the
pilot switched.

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
