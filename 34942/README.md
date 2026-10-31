# PR #34942 - EKF3: fix the on-ground height check and apply it without a vertical velocity

Analysis archive for [ArduPilot/ardupilot#34942](https://github.com/ArduPilot/ardupilot/pull/34942).
Branch `pr-ekf3-gnd-hgt-check` (andyp1per fork), base `master` at
`278a68a57a`. PR head `3da7a8cf2e` (eight commits), force-pushed
2026-10-31 over the opened head `a1fbfbcdc7` (five commits, 2026-10-30,
kept locally on `pre-rework/pr-ekf3-gnd-hgt-check-20261031`). The flight evidence is from the T25 airframe on the
SFD 4.7.2 beta; numbers are cited inline and no flight logs are committed.

> **Read this before changing the code.** The two "Measured and rejected"
> tables below (at the rework, and at `a1fbfbcdc7`) list the versions of
> this change that look right and measured worse, each with the number that
> settled it. Several of them were the first design, and a pre-arm hold was
> built three ways before it was dropped.

## Status (one line)

Opened 2026-10-30 after four /pr-review rounds (verdict COMMENT). Reworked
2026-10-31 after Flight test 3 and three more review rounds (`3da7a8cf2e`,
pushed with the PR body updated): Replay and SITL validated, Copter, Plane and Sub autotests
pass; unflown; on by default, which the PR argues as a bug fix and a
maintainer may want discussed first.

## The flight

T25 `0cb49e7` vertical runaway (2818322/52), 2026-10-30, SFD beta
refresh11 topup5 (`0cb49e7dfb`), MicoAir743v2 board 002F003C:

- 94.0 s: switch disarm (RC5, option 153) at about 1.2 m. Free fall, and
  the impact clips IMU0, the only EKF IMU (`EK3_IMU_MASK` 1): `VIBE.Clip`
  14 to 41.
- On the ground the EKF keeps `XKF1.VD` at +4.7 m/s. Vertical velocity
  variance is about 0.003 against a baro R of 4, the baro is rejected
  (`XKF4.SH` > 1) from 97.6 s, and `XKFM.OGNM` stays 0, so no stationary
  zero-velocity fusion runs. Optical flow keeps the core in AID_RELATIVE, so
  the AID_NONE-only on-ground tests do not apply.
- 100.58 s: re-armed with VD 4.28 m/s and the EKF 23 m below its take-off
  height. VALT climbs to about 6 m with the throttle at minimum; the pilot
  switches to ACRO at 103.8 s. A height timeout, which zeroes velD on the
  ground, was due at about 102.6 s.
- 288-302 s: a hop and a clipped landing leave the EKF climbing 1.3 m/s on
  the ground; re-armed at 288.08 s with VD 1.43 m/s, and VALT later holds
  the EKF at 7.2 m with the vehicle at 1.3 m.

The 29 Oct runaway on the same board, T25 `308a7e73` (2818322/45), has two
more arms of the same kind: 52.10 s (VD 1.12 m/s) and 62.90 s (-2.87 m/s).
Its cause in flight is #32473's; the arms are what matter here.

### Why nothing refused those arms

- `hgtInnovFiltState`, the filter behind the on-ground height test in
  `healthy()`, has not moved on a passing sample since `5d00b7d042`
  (Copter-4.1.0), which put the `lastHgtPassTime_ms` update in the gate
  ahead of the filter that takes its step from it. **Measured**: Replay of
  all 14 logs below on refresh12 `2e2936166d`, unmodified, read it at
  exactly 0.00 at every one of the 52 arms (2026-10-30, shadow-filter
  instrumentation `data/replay/instrument-shadow.diff`).
- The test only applies in AID_NONE: EKF2's `04165a60a7` (2015), which
  EKF3 inherited, kept it out of aided modes for false positives from GPS
  and baro disturbances on the ground and during launch.
- #32768's arm-time height datum reset zeroes velD but is skipped when
  `ap.disarmed_in_air` or `moving_vertically` (|VD| >= 1 m/s), and the
  latch clears only when the EKF's VD is low, so it is skipped on exactly
  these arms (derived from the source, not measured; `EKF_ALT_RESET` is
  absent at 17.98, 100.58 and 288.08 s in the flight log).

## The change at `a1fbfbcdc7`

1. `8828291f3f` the filter gets its own update time, `hgtInnovFiltTime_ms`,
   set wherever the pass time was before `5d00b7d042` (including
   `ResetHeight()`), so its step is again the time since it last ran.
2. `f40ed7c0fc` the height test moves into `onGroundHgtError()`, shared by
   `healthy()` and the per-core pre-arm check, which reports
   "EKF3[n] height error Xm"; per-core checks run before the unhealthy-core
   report. No arming decision changes.
3. `3cf2fcb866` the test applies in aided modes while no vertical velocity
   is measured: a new `lastVelDFuseTime_ms` (GPS or ExtNav vertical velocity
   fused in an aided mode, not the stationary zero velocity) or
   `prevBodyVelFuseTime_ms`, within 2 s, exempts.
4. `82abc5737b` every on-ground height sample feeds the filter, a rejected
   one clipped at the gate.
5. `a1fbfbcdc7` autotest `EK3HardLandingRearm`.

### Superseded 2026-10-31 by the rework at `3da7a8cf2e`

Flight test 3 (below) was an arm the head could not refuse (its filter
read -0.21 m there), and the premise of commit 3 above, that a fused GPS
vertical velocity corrects the error itself, measured wrong: after a SITL
impact the GPS vertical velocity was fused until the error reached 2.8 m/s
and rejected from then on. The list above is left in place as what was
reviewed and opened on 2026-10-30.

## The rework at `3da7a8cf2e` (2026-10-31, force-pushed over `a1fbfbcdc7`)

Base unchanged, `278a68a57a`. Eight commits:

1. `d6825422d5` filter time step (as `8828291f3f`).
2. `f2b487cb55` `onGroundHgtError()` and the "height error" pre-arm reason
   (as `f40ed7c0fc`, message adds the DCM-fallback note).
3. `4d0a453b5d` the test in aided modes unless a measured velocity
   **agrees** with the state in the vertical: `measuredVertVelAgrees()` is
   GPS or ExtNav vertical velocity fused in an aided mode in the last 2 s
   (`lastVelDFuseTime_ms`) with `|innovVelPos[2]| < 0.5` and
   `velTestRatio < 1`, or body velocity fused in the last 2 s with the
   norm of all three `innovBodyVel` axes under 0.5.
4. `c7fc88ce75` rejected samples clipped at the gate (as `82abc5737b`).
5. `bf1ea90b4e` `updateMovementCheck()` caps each sample's input to the
   gyro and accel rate-of-change filters at `2 * EK3_OGNM_TEST_SF * limit`.
6. `7cf54da6dd` the height test is skipped while `velDotNEDfilt.z` is over
   0.5 g down (falling).
7. `21a8e3a683` at the first height sample after the vehicle reads still
   (`onGroundNotMoving`), once per rest (`velDCheckedAtRest`): if no
   measured vertical velocity agrees and `|velD| > 0.5`, `ResetHeight()`,
   clear the filter, and send "EKF3 IMUn vertical velocity reset at rest".
8. `3da7a8cf2e` `EK3HardLandingRearm` rewritten.

Guidance carried in the PR and in commit 7: after a drop or a hard landing,
leave the vehicle on the ground and still for at least a second before
re-arming. Andy chose this over a pre-arm hold (see "Measured and rejected,
at the rework").

### The flight: Flight test 3 (t25-0cb4-ft3, 2818322/55)

Same T25 board and firmware (`0cb49e7dfb`; MAVLink optical flow, no GPS:
`GPS1_TYPE` 0, `EK3_SRC1_VELXY` 5, `EK3_SRC1_VELZ` 0), 2026-10-30. Log time.

- 354.12 s: switch disarm at about 1.5 m; the vehicle tumbles for about
  1.2 s and is still for about 0.3 s.
- 355.92 s: re-armed 1.8 s after the drop with the flown EKF at `XKF1.VD`
  1.04 m/s (the error was there in flight: 1.02 against a range-finder rate
  of 0.26 to 0.3 m/s), the flown stillness flag not set at the arm, no new
  clipping. VALT then climbed from 2.3 to 4.4 m with the stick at minimum.
- The head at `a1fbfbcdc7` would not have refused it: its filter read
  -0.21 m at that arm (Replay, 2026-10-30).
- Flown height innovation (`XKF3.IPD`) times the sign of VD: -2.82 m 0.3 s
  into the fall, recovering through 0 at about 355.5 s, about 0.4 m at the
  arm. That is why a height-innovation test would have missed it.
- Other findings on this log: the acro-exit fix held; #31274's boot ESC.Err
  still 79%; the pilot used the EKF reset (aux 187) at 138.63 and 334.32 s;
  flow QMIN latch failsafes (median quality 59 against QMIN 60).

Replay follows the flight exactly to 138.62 s (baseline Replay against the
flown `XKF1`), where the pilot's reset, which is not in the DAL, is not
reproduced. Arms after that are what the changed firmware would have
estimated without the pilot's resets.

### Replay (tier 1b), 2026-10-31, at the rework

Build: refresh12 `2e2936166d` plus `data/replay/stages-v2.py` 1 2 3 4 5 G 6
and `data/replay/instrument-v2.diff`. 15 logs, 65 arms. Outputs, log names
replaced by index ids: `data/replay/score-v2-2026-10-31.txt` (scorer
`score-v2.py`, which also fixes the aiding-mode labels of `score.py`:
EKF3's 0/1/2 are ABSOLUTE/NONE/RELATIVE) and `arms-v2-2026-10-31.txt`
(`arm_table.py`).

| | arms | at `3da7a8cf2e` |
|---|---|---|
| went up with a flown VD of 1.0 to 4.3 m/s | 6 | 4 refused (t25-0cb4-run 17.98, 100.58; t25-308a-run 52.10; t25-0cb4-ft3 355.92 on the diverged replay); t25-0cb4-run 288.08 arms after the rest reset with 0.00 m/s; t25-308a-run 62.90 goes up with -1.25 m/s (flown -2.87) |
| other MicoAir arms | 39 | 10 refused, 8 re-arms 1.1 to 3.9 s after a disarm and 2 first arms |
| SFD-O4 | 20 | none refused |

All 14 refusals are on the height error, filter 1.1 to 4.4 m, replayed VD
under 0.5 m/s at 7. Apart from 62.90, every allowed arm goes up under
0.6 m/s (max 0.56). 62.90 is an EKF whose accel bias the #32473 fault
corrupted in flight: the rest reset zeroes the velocity and clears the
filter, the bias builds the velocity again, and the filter has not
re-accumulated 1 m by the arm.

The free-fall skip (commit 6) applies, over all 15 logs, only during the
falls after the disarms in the air on t25-0cb4-run (94.48-95.08 s) and
t25-308a-run (45.30-45.80 s) and for 0.3 s of handling at boot on
t25-0cb4-run (12.98-13.28 s). Those windows move when the EKF resets
itself (the five-second unhealthy reset), so the replayed state at later
arms differs on those two logs; without commit 6 (`arms-nohold-noskip`)
62.90 went up with 0.09 m/s after a forced reset and the 6 big-error arms
were 1 refused and 5 armed at 0.26 m/s or less.

The cap (commit 5) alone, replay against replay over every disarm-to-arm
pair (`cap-compare-2026-10-31.txt`): on seven MicoAir logs the check now
asserts before the next arm after four disarms where it never did (0.9 to
5.3 s after them, 2.5 s on the runaway) and 0.1 to 1.5 s sooner after seven
others. On SFD-O4 every difference from baseline is the cap's: five logs
bit-identical, three (log56, log57, log59) changed once on the ground, by at
most 0.05 m/s and 0.3 m. The MicoAir never reads still before the next arm
in 18 of its 38 disarm-to-arm intervals, even with the cap; SFD-O4 always
does.

The `velTestRatio` term in commit 3 changed no replayed sample on any of the
15 logs (XKF1 core 0 compared sample by sample).

### SITL (tier 2), at the rework

`EK3HardLandingRearm` at `3da7a8cf2e` with each change taken out
(`data/sitl/variants-v2.sh`, `data/sitl/variants-v2-2026-10-31.txt`; run on
the same EKF at scratch `fin8`):

| build | result | leg |
|---|---|---|
| the series | passes (also twice at `3da7a8cf2e` itself) | |
| master's EKF | climbed 0.88 m after the throttle cut | GPS quick re-arm |
| commit 1 out | EKF never reports the error | no aiding, baro step |
| commit 2's reason out | "Waiting for 3D fix" | no aiding, baro step |
| commit 3 AID_NONE only | EKF never reports the error | flow, rejected baro |
| commit 3 exclusion on fusion alone | climbed 0.89 m | GPS quick re-arm |
| commit 3 exclusion out | "EKF unhealthy after a baro step" | GPS baro step |
| commit 3 `velTestRatio` out | passes: SITL cannot reach it | |
| commit 4 out | EKF never reports the error | flow, rejected baro |
| commit 6 out | re-arm refused mid-fall ("height error 4.2m") | flow, re-arm while falling |
| commit 7 out | climbed 0.89 m | GPS quick re-arm |
| commit 5 out | not run: SITL cannot produce the shock | |

A clean vehicle rises 0.06 to 0.11 m after the throttle cut; the limit is
0.6 m.

GPS baro steps applied and removed on a still, disarmed GPS copter
(`data/sitl/gps_step_updown.txt`, run on the series with the agreement
exclusion): 2 and 3 m on and off never refuse, peak |VD| 0.33 m/s; 5 m on
never refuses (0.49 m/s), 5 m off refuses for about a second ("height error
2.2m", 0.51 m/s), identically on two repeats. Without the exclusion
(`data/sitl/gps_step_probe_v2.txt`) 3 to 10 m steps refused within 0.8 to
1.4 s, then reset.

Sharp impact for the `velTestRatio` term (`data/sitl/sharp_impact_probe.txt`):
50 m/s/s for 0.1 s after the drop, re-armed 1 s later, eight runs with and
without the term: the EKF read about 0 m/s at the arm in every run and both
builds behaved alike (peak 3.5 to 3.8 m, landed in 2.6 to 2.8 s; one
"Accels inconsistent"). The 5 m/s jump stayed inside the GPS gate, so the
stale-innovation case was not reached.

The in-air re-arm in SITL also shows master's height datum reset at arming
when home is not set: VD went from 5.05 to 0.41 m/s and PD to 0 at the arm
while the vehicle was still falling. #32768 deals with that reset.

Regression at the rework: 27 Copter autotests (the 21 above plus Parachute,
ThrowMode, ShipTakeoff, ArmFeatures, RudderDisarmMidair and the new test),
3 Plane (Parachute, ParachuteSinkRate, DeadreckoningNoAirSpeed) and 26 Sub
autotests pass on the EKF of `3da7a8cf2e`. Flash on MatekF405 Copter, which
compiles out body odometry: +784 bytes, no warnings.

## Measured and rejected, at the rework

| change | argument for | result | code state |
|---|---|---|---|
| Exempt aided modes on fusion of a vertical velocity alone | a fused GPS vertical velocity corrects the error | after a SITL impact the GPS vertical velocity was fused until the error reached 2.8 m/s and rejected from then on; the GPS quick re-arm climbed to 3.85 m against 1.50 m with agreement (prototype harness), and fails the test | `a1fbfbcdc7` commit 3 |
| Agreement on the last fused innovation alone | it is what the EKF used | it only changes when a sample is fused, so one rejected outright leaves the last good one in place for up to 2 s (inspection; SITL did not reach it) | scratch |
| Body-velocity agreement on the Z axis alone | the vertical axis | on a tilted vehicle the vertical projects onto body X/Y (inspection, review round 1) | scratch |
| Reset at every height sample while still | also clamps any velocity a still vehicle reports | a 0.7 m/s/s bias on one IMU was reset every 0.8 s (39 times) and never learned (XKF2.AZ 0.000); EK3AccelBias, EK3_AccelBiasZeroVelOptFlow, EK3_AccelBiasInhibitOnGroundMoving and EK3_ZeroVelFusionNotUsedWithGPS failed | scratch `fin2` |
| Defer the rest check while a measurement agrees | a stale pre-impact agreement could use up the check | on a GPS vehicle on a moving ship whose bias pulled the state off the GPS, the check fired when agreement lapsed: EK3_ZeroVelFusionNotUsedWithGPS failed | scratch `fin4` |
| Pre-arm hold while the vehicle is not still with an unconfirmed VD | covers a re-arm before the reset (Flight test 3) | a disarmed falling vehicle reads as moving, so on Copter and Blimp, which run the EKF pre-arm check on every arm forced included, a flow-only vehicle disarmed in the air could not be re-armed | `96cdc69f54` |
| Hold whenever disarmed with an unconfirmed VD, exempting falls by acceleration (> 0.5 g down) | also covers a velocity that builds after the rest check | drag slows a long fall below 0.5 g after about 1 to 1.5 s, and the hold came back mid-fall; three reviewers rated it must-fix | `794589001b` |
| Hold only while the height innovation agrees in sign with VD by > 0.5 m | the height sensor tracks a real fall, a lift, a deck | Flight test 3's arm read about 0.4 m, still recovering from the fall's -2.8 m | analysis only |
| Pre-arm hold at all | Flight test 3 | dropped (Andy, 2026-10-31): guidance "still for at least a second" instead; a range-finder ground check was offered and not taken | - |
| Gate the height test on `onGroundNotMoving` | the reset's own evidence; reads moving in any fall | the MicoAir never read still before the next arm in 18 of 38 intervals; Replay refusals fell from 12 to 2 and four arms with a real error went up with 0.9 to 1.5 m/s (`arms-gate-onground-2026-10-31.txt`) | scratch `fin7` |
| Test: train of +-80 m/s/s bias steps as the shock for the cap | rings the rate terms like an impact | each step lasts a parameter round trip: 16 m/s of VD, "EKF attitude is bad", "Accels inconsistent"; every variant failed for unrelated reasons | scratch |
| Test: SITL accel noise as the shock | an impact is noise-like | `SIM_ACC*_RND` applies only with the motors running | inspection |
| Test: GPS baro-step leg passing on 10 s healthy out of 12 | tolerant of jitter | without the exclusion the refusal lasts under a second, so the leg passed | first rewrite |
| Test: 5 m GPS baro step | larger margin | its removal pulls VD 0.51 m/s off the GPS and refuses for about a second with the exclusion in place | scratch |
| Test: impact held 0.5 s by a fixed delay | simple | its size depended on parameter-set latency; at 2 m/s the faulty climbs (0.65 to 0.74 m) sat on the 0.6 m limit; held until VD > 4 m/s they rise 0.83 to 0.89 m against 0.06 to 0.11 m clean | scratch |
| Test: in-air re-arm from 3.5 to 7 m | short leg | the harness took 0.8 to 2.3 s to re-arm, so the arm reached the vehicle after touchdown; 25 m, with the baro glitch set before the disarm | scratch |

## Review history, at the rework

All 2026-10-30/31, before the push of `3da7a8cf2e`.

- Round 1 at `96cdc69f54` (five Claude reviewers, six Codex cold reads):
  the pre-arm hold refused a re-arm while falling (must-fix); the window
  between stillness and the reset; a velocity that builds after the latched
  check; body-frame Z only; stale agreement; naming and comments; test
  timing and coverage-as-trace. Fixed in a round that then broke
  EK3_ZeroVelFusionNotUsedWithGPS (deferred check, reverted).
- Round 2 at `794589001b` (one Claude, four Codex cold reads, one audit: 15
  of 19 closed): the acceleration exemption fails under drag (three readers,
  must-fix). The hold was dropped.
- Round 3 at `cd2f766381` (one Claude, three Codex cold reads, one audit):
  the revived height test itself can refuse a re-arm during a fall
  (must-fix). Stillness gate measured and rejected; free-fall skip taken.
- Final cold reads of the skip and the whole diff at `3da7a8cf2e`: nothing
  requiring a code change.

Findings rejected or left, with the reason:

- "Steady vertical motion reads still and the rest reset zeroes a real
  velocity" (raised every round): the stated limit, once per rest, with an
  agreeing GPS vertical velocity preventing it; a positive test on the height
  innovation would have missed Flight test 3.
- "The once-per-rest check is consumed on a stale agreement": deferring it
  broke bias learning (measured above).
- "A velocity that builds after the check is not reset": deliberate; left to
  the height test, whose filter the reset clears. Keeping the filter through
  the reset would cover it and refuse a clean quick re-arm for 2 to 3 s;
  offered, not measured.
- "ResetHeight() adopts the sample before its gate": shared with the existing
  height-timeout reset; recoverable through the height test.
- "Zero timestamps read as agreement for 2 s after boot": VD is 0 then.
- "Clipping at the gate bounds the filter under 1 m when the gate is small":
  true; on Sub (`EK3_ALT_M_NSE` 0.01) the test cannot fire, before or after
  the series. Documented in the PR.
- "Per-core reasons ahead of healthy() can mask a worse fault message":
  settled at `a1fbfbcdc7`; the arming decision is unchanged.
- "The velocity innovation is written before the gate" (Codex audit, round
  3): refuted, `innovVelPos[0..2]` is written only in the fusion loop.
- "Acceleration does not prove a fall" (final cold read): over 15 logs the
  skip applied only in two real falls and 0.3 s of boot handling, and the
  test resumes at once.

## Evidence

### Replay of the flights (tier 1b), 2026-10-30

Build: SFD beta refresh12 `2e2936166d` (its EKF3 is identical to the flown
`0cb49e7dfb`) plus the head's EKF changes applied with
`data/replay/stages.py` 1-4 and the verdict logging in
`data/replay/instrument.diff`. Scored with `data/replay/score.py`; output in
`data/replay/score-2026-10-30.txt`. The same verdicts came out of the
previous stage of the series (the 1 s exclusion window, no body velocity
term), arm for arm.

| arm | flight VD (m/s) | filter (m) | verdict |
|---|---|---|---|
| t25-0cb4-run 17.98 | 1.53 | 0.01 | refused as unhealthy: the EKF had reset itself on the boot divergence and was still realigning (replay VD 0.26) |
| t25-0cb4-run 100.58 | 4.28 | 8.73 | refused, height error |
| t25-0cb4-run 288.08 | 1.43 | 1.00 | refused, height error, at the threshold |
| t25-308a-run 52.10 | 1.12 | 0.00 | refused as unhealthy, realigning after a reset the height error triggered |
| t25-308a-run 62.90 | -2.87 | 2.69 | refused, height error |

Other arms refused on the MicoAir board type, 9 of 27 (t25-0cb4 at 15.68,
175.88, 482.48, 494.88 s; t25-0cb4-run at 194.38, 218.18, 261.08,
441.88 s; t25-308a-run at 92.60 s):

- eight are re-arms 1.1 to 3.9 s after a disarm, with the filter at 1.0 to
  3.5 m and flight VD 0.37 m/s or less except 92.60 s (-0.62 m/s);
- t25-0cb4 15.68 s is the log's first arm, where Replay cannot follow the
  flight: the flight's own arm-pending bootstrap reset at 14.68 s is not
  in the DAL.

None of the 20 arms on SFD-O4 (log54-log65) is refused; core 1 there runs
AID_ABSOLUTE without a measured vertical velocity, so the test applied.
On the ground, 68.7 s in height error across 24 episodes and 7 forced
resets, all on the MicoAir logs (td25-op-0e2c is the other board of the
same type: 2 resets, no refused arm).

What Replay cannot show: once the replayed EKF resets itself it no longer
follows the flight's EKF, so verdicts after a reset are what the changed
firmware would have estimated, not what flew. 288.08 s is borderline: it
read 0.88 m on an earlier stage of the series (before the gate clip and
the reset-time stamp) and 1.00 m at the head; which change moved it was not
isolated. The pilot's and the vehicle's response to a refusal are not
modelled.

On the drop itself (Replay of an earlier stage, unclipped rejected samples,
2026-10-30): the filter stayed under 0.65 m in the fall, 94.08 to about
95.2 s, and crossed 1 m at 96.38 s, 1.2 s after touchdown, so a re-arm
during the fall would not have been refused.

### SITL (tier 2)

`EK3HardLandingRearm` at `a1fbfbcdc7` with each EKF change taken out
(`data/sitl/variants.sh`, 2026-10-30, `data/sitl/variants-2026-10-30.txt`):

| build | result |
|---|---|
| the series | passes |
| master's EKF | fails: the EKF never reports the error |
| commit 1 out (time step from the last pass) | fails: the arm is accepted |
| commit 2's pre-arm reason out | fails: "PreArm: AHRS: Waiting for 3D fix" |
| commit 3 out (AID_NONE only) | fails: the EKF never reports the error |
| commit 3's exemption out | fails in the GPS leg: the 10 m baro step makes the EKF unhealthy |
| commit 4 out (fused samples only) | fails in the tight-gate leg: unhealthy only at the height timeout, 5.2 s after rejection began |

The SITL logs of the first two rows are in `data/sitl/`.

Baro step on a disarmed GPS copter fusing GPS vertical velocity
(`data/sitl/gps_step_probe.txt`, 2026-10-30, on the series at
`ec1cf6fbf5`, whose exemption window was 1 s with no body velocity term;
the head's window and term only widen the exemption):

| step | with the exemption | without |
|---|---|---|
| 2 m | healthy | healthy |
| 5 m | healthy | unhealthy for about 4 of 20 s, height error up to 2.2 m |
| 10 m | healthy | unhealthy for about 6 of 20 s, height error up to 4.3 m |

Baro drift while disarmed (`data/sitl/drift_probe.txt`), 0.01, 0.03, 0.1
and 0.3 m/s for 90 s in AID_NONE, AID_RELATIVE (flow) and AID_ABSOLUTE
(GPS): no height-error refusal and no forced reset in any case, at
`9617ec874a` (EKF identical to the head). The steady innovation at
0.3 m/s, a property of the fusion and not of this check, was 0.45 m
without aiding, 0 on flow and 0.74 m with GPS. 0.3 m/s is far beyond real
baro drift; the numbers show direction, not a real-world size.

On master's EKF the first version of the test re-armed with the EKF at
3.7 m/s down and 10.4 m below its take-off height (2026-10-30). On a fork
harness flown in VALT (refresh12 plus the first design, scratch only), the
unfixed vehicle climbed to 14.0 m and 20.5 m with the throttle at minimum
for re-arms 5.6 and 3.6 s after the drop, the fixed one 0.42 and 0.54 m.

21 related Copter autotests (EK3, optical flow, baro, arming, takeoff,
AltHold) pass at `9617ec874a`.

## Measured and rejected

| change | argument for | result | code state |
|---|---|---|---|
| Filter on the time since the previous pass (a local copy of `lastHgtPassTime_ms`) | one line; restores a moving filter | its step grows through every gap and bad-IMU sample, so it is not a 2 s filter; it caught 288.08 s only because of that | first design, `1586bc787a` |
| Apply the test in every aiding mode | simplest extension | a 5 m baro step on a disarmed GPS copter fails it for about 4 s; it reverses `04165a60a7` where its reason applies | round 1 |
| Reuse `(useGpsVertVel \|\| useExtNavVel) && !velTimeout` as "vertical velocity measured" | the EKF already uses it for the height timeout | on a flow vehicle with a GPS fitted it reads true (GPS has vz, flow keeps `velTimeout` false) while GPS is never fused in AID_RELATIVE, so it would skip the test where it is needed (derived from the source, not measured) | round 2 |
| Filter fused samples only | the pre-4.1 behaviour | with `EK3_ALT_M_NSE` 0.5 the baro is rejected before the filter reaches 1 m; the first design armed with the EKF at 5.73 m/s and 24.2 m low, and the series without commit 4 has a 5.2 s window | first design and round 2 |
| Feed rejected samples unclipped | a rejected sample is the largest disagreement | one 22 m outlier fails the test at a 10 Hz baro (derived, not measured) | round 2 |
| Clear the filter at a height-timeout reset | avoids a forced reset once the height is reset | not taken: an error large enough to time the height out may have corrupted the accel bias, which only the forced reset relearns (judgement, not measured) | round 3 |
| On-ground velD threshold at arm | separates the replayed arms as well | would refuse a legitimate re-arm while falling, where the baro agrees with the motion (derived) | before review |
| Test: accel pulse on one IMU | the flight clipped one IMU | trips "Accels inconsistent", which also refuses the arm on master, so the test cannot fail | before review |
| Test: fixed 3 s wait before arming | simple | races the 5 s forced reset with 1.5 to 2 s of margin on a quiet host | round 1 |
| Test: drop `SIM_TERRAIN` 0 | a review asked what it was for | terrain tiles left by `EK3_OptflowTerrainScaleHeight` move the range finder's ground to 0.54 m and the test fails on every build | round 2 |
| Test: re-arm straight after a normal landing | the case the Replay refuses | the filter is zeroed while armed, so the leg cannot fail; removed | round 3 |

## Review history

All on 2026-10-30, before opening.

- Round 1 at `1586bc787a` (5 Claude reviewers, 5 Codex cold reads):
  REQUEST CHANGES, 3 must-fix - the tight-gate escape, the unanswered
  reversal of `04165a60a7`, and the five-second reset claimed for GPS
  vehicles - plus 9 should-fix.
- Round 2 at `ce2585bc2f` (2 Claude, 6 Codex cold reads and an audit of the
  34 round-1 findings: 22 closed, 2 partial, the rest PR-description
  items): outlier clipping, the untested exemption, commit order, the
  stale filter after a height reset, body velocity, the 1 s window, wording.
- Round 3 restructured the series (helper and pre-arm reason before the
  behaviour change) and added the GPS leg; round 4 (2 Codex cold reads at
  `9617ec874a`) added the passing-gate assertion and the ExtNav wording.

Review findings rejected, with the reason:

- "A flow vehicle with a GPS fitted may never recover until reboot":
  refuted, `ResetHeight()` sets `velocity.z = 0` on the ground at the height
  timeout.
- "The forced reset loses a GCS-set origin": refuted,
  `InitialiseFilterBootstrap()` restores the core's origin from
  `public_origin`.
- "The pre-arm reorder lets 'vel error' outrank the unhealthy text": kept;
  it is the more specific reason, and the arming decision is unchanged.
- "Plane and Rover need a vehicle guard": no, the EKF carries no
  vehicle-class code; the affected configurations are listed in the PR.
- "Baro drift and zero-velocity fusion make the revived test fire": not at
  0.01 to 0.3 m/s (measured above); vertical motion above about 0.6 m/s with
  the IMU still (a lift, a Sub floating up) would, extrapolated, not
  measured.
- "A rescue re-arm during the fall can be refused": not on the flight's
  drop (above).

## Open

At the rework (2026-10-31):

- Pushed 2026-10-31 and the PR body patched; no review or CI result on the new head yet.
- Unflown. The reset at rest leaves "EKF3 IMUn vertical velocity reset at rest" in the log, which is the trace a flight has to show.
- A re-arm in the window before the vehicle reads still goes up with the error (Flight test 3's case); the PR tells users to wait a second.
- A long fall slowed by drag below 0.5 g brings the height test back; steady vertical motion read as still gets one wrong reset.
- Keeping the height filter through the rest reset (covers a bias-built velocity like t25-308a-run 62.90) is unmeasured.

At `a1fbfbcdc7`:

- The MicoAir false refusals: 9 of 27 ordinary arms, all quick re-arms
  after the EKF settles 1 to 3.5 m off the baro on landing. The 1 m
  threshold is the existing one; a 2 m threshold would, from the table,
  keep 100.58 and 62.90 s and drop most of them (not measured).
- No Plane, Rover or Sub SITL run; nothing has flown; not on the SFD beta.
- On by default (ARCH-19): a dev-call or Discourse thread may be wanted.
- Flash cost not measured.
- EKF2 is unchanged; whether its AID_NONE-only rule should follow is open.

## On the SFD stack: refresh12 topup3 (2026-10-31)

`3da7a8cf2e` cherry-picked onto refresh12 at topup2's tip (`35e04e1064`)
as `e78e5ccda2`..`992bb00935` and test `1806c9af22`, locked as
`2e70bccdc5`. Not promoted: on this stack it breaks four tests, one of
them the test failing in the PR's own CI.

- The seven EKF3 commits apply clean, and the result is byte-identical to
  `data/replay/stages-v2.py` 1 2 3 4 5 G 6 applied to the same tip, so the
  rework's Replay covers this code (it ran before topup1 added #34941).
  The test needed its registration by hand and 4.7's `takeoff(alt_min=)`.
- SFD's AGL KF velD (#33478, `EK3_OPTIONS` bit 4, on in SFD's default 92)
  never counts as agreement: `lastVelDFuseTime_ms` is stamped in the
  `fuseVelData` branch of `FuseVelPosNED()`, and the AGL KF fuses through
  its own `fusingAglKfVel` branch. Replay of t25-0cb4-run, t25-0cb4-ft3 and
  t25-308a-run (all `EK3_OPTIONS 92`) on topup3 never set the stamp, and
  reproduced the rework's figures: the 93.98 s drop reset at rest after
  2.7 s with VD 4.67 and the 100.58 s arm refused on the height error;
  t25-308a-run 54.70 reset after 5.4 s with VD -2.19 and 62.90 went up
  with -1.34 (`data/sfd-topup3/stale_probe.out`).
- `EK3HardLandingRearm` passes. With the seven EKF3 commits reverted, and
  its mechanism checks turned into reports (`probe_test.py`), the flow
  quick re-arm arms at 5.19 m/s with no reset and climbs 0.76 m with the
  throttle at minimum (0.07 m on topup3). The GPS quick re-arm arms at
  1.32 m/s but rises only 0.11 m, where master's EKF climbed 0.88 m in the
  rework's table.

Broken on the stack, each run alone, failing on topup3 and passing with
the seven EKF3 commits reverted:

| test | on topup3 | why |
|---|---|---|
| MAV_CMD_SET_EKF_SOURCE_SET (master's) | "Failed to get EKF.flags=831": after set 2 and back to set 1 the EKF never regains a position ("Need Position Estimate", "Check mag field" xy diff 121 rising to 241) | the PR's CI fails the same way (sitltest-copter-tests1e on `3da7a8cf2e`). Bisect on the stack: commits 1-4 pass, 1-5 fail, so commit 5 (`bf1ea90b4e`, the stillness check cap). Mechanism not established |
| AccelBiasMovingPlatform | EKF unhealthy on the ground, "EKF3[1] height error" 1.5-2.0 m, never ready to arm | `SIM_PLAT_ACC_Z -1` for 60 s disarmed: the EKF reads VD -2.4 to -6 m/s on the ground with GPS velD rejected in both builds; without the PR it arms anyway |
| Copter.Replay | as above | its accel bias inhibit leg is the same platform, 30 s; VD -5.97 m/s disarmed without the PR, and it arms |
| VibrationRectificationBiasLearning | "EKF3[1] height error" 1.4-3.8 m after the bit-2 leg's landing | core 0 reads VD up to 1.7 m/s on the ground for two minutes in both builds (300 of 431 disarmed samples over 0.5 m/s without the PR), and the next flight arms anyway without it |

The last three are the PR doing its job: the EKF really is wrong on the
ground, and the tests (SFD's, carried with #32471 and #32473) assume
arming regardless. The VRF case is also a #32471 question: with
`ACC_ZBIAS_LEARN` bit 2 the EKF sits at up to 1.7 m/s after landing.
MAV_CMD_SET_EKF_SOURCE_SET is not of that kind and blocks the PR's CI.

Also seen:

- EK3_ZeroVelFusionNotUsedWithGPS failed once in the full set and passes
  alone. The copter rides a ship at 15 m/s with GPS, and the test injects
  `SIM_ACC2_BIAS_Z 0.7`. While core 1 learned it, a SITL deck bump ("SIM
  Hit ground at 1.06 m/s") started a new rest, and the rest reset fired
  with GPS velD being fused but disagreeing by over 0.5 m/s. AZ then sat at
  0.65 against 0.7. That is the case the design note in commit 7 warns
  about (resets stopping bias learning), reached with a measured velD
  present.
- Copter.Parachute fails with and without the PR on 4.7: 4.7 prints
  "BANG!  Parachute deployed" with two spaces, and master's test waits for
  one. Unrelated.
- SmallFastDronev1 copter: 45,012 bytes free, 824 fewer than topup2.

Open:

- MAV_CMD_SET_EKF_SOURCE_SET and commit 5, on master: the CI failure, the
  bisect points at the cap. Not reproduced on master here.
- Whether the moving-platform and VRF tests should expect the refusal, or
  the refusal is too eager for a GPS copter whose velD is rejected.

Files: `data/sfd-topup3/` holds the scripts (`instrument_stale.py`, the
Replay and SITL logging; `stale_probe.py`, per-disarm rest checks;
`why_disagree.py`, `vd_disarmed.py`, `probe_test.py`, `bisect_srcset.sh`,
`cmp_34942_stages.sh`) and `stale_probe.out`. They name scratch paths from
the session that ran them.

## File map

At the rework:

- `data/replay/stages-v2.py` - the rework's EKF changes as text edits (stages 1 2 3 4 5 G 6; 7 is the dropped hold)
- `data/replay/instrument-v2.diff` - verdict logging with bit 2 as `measuredVertVelAgrees()`
- `data/replay/score-v2.py`, `data/replay/arm_table.py` - scorers (score-v2 fixes the aiding labels)
- `data/replay/score-v2-2026-10-31.txt`, `arms-v2-2026-10-31.txt` - the rework's Replay
- `data/replay/arms-gate-onground-2026-10-31.txt` - the rejected stillness gate
- `data/replay/arms-nohold-noskip-2026-10-31.txt` - the series without commit 6
- `data/replay/cap-compare-2026-10-31.txt` - stillness timing with and without the cap
- `data/sitl/variants-v2.sh`, `variants-v2-2026-10-31.txt` - the test with each change removed
- `data/sitl/gps_step_updown.txt`, `gps_step_probe_v2.txt`, `sharp_impact_probe.txt` - probes with results

At `a1fbfbcdc7`:

- `data/replay/stages.py` - the head's EKF changes as text edits, stages 1-4
- `data/replay/instrument.diff` - the verdict logging (XKFM layout, core +
  50) used for the head's numbers
- `data/replay/instrument-shadow.diff`, `data/replay/score_shadow.py` - the
  shadow-filter logging and scorer behind the "0.00 at every arm" number
- `data/replay/run_replay.sh`, `data/replay/score.py`,
  `data/replay/logs.txt` - running and scoring; the log ids
- `data/replay/score-2026-10-30.txt` - the head's per-arm output, log names
  replaced by their index ids
- `data/sitl/variants.sh`, `data/sitl/variants-2026-10-30.txt` - the test
  with each change removed
- `data/sitl/insert_harness.py`, `data/sitl/drift_probe.txt`,
  `data/sitl/gps_step_probe.txt` - the throwaway probes
- `data/sitl/timing.py` - pulse, rejection and unhealthy times from a run
- `data/sitl/EK3HardLandingRearm-a1fbfbcdc7.BIN`,
  `data/sitl/EK3HardLandingRearm-master-ekf.BIN` - SITL logs of the test

## Reproduce

Replay, from a beta checkout (smallfastdrone-beta):

```sh
git worktree add --detach ../wt-34942 2e2936166d && cd ../wt-34942
git submodule update --init --recursive
for st in 1 2 3 4; do python3 <archive>/34942/data/replay/stages.py . $st; done
git apply <archive>/34942/data/replay/instrument.diff
./waf configure --board sitl && ./waf replay
# resolve each id in data/replay/logs.txt to a path with find_log.py and
# ../analysis/logs/REPLAY_INDEX.md, one path per line, into loglist.txt
<archive>/34942/data/replay/run_replay.sh build/sitl/tool/Replay loglist.txt out
python3 <archive>/34942/data/replay/score.py loglist.txt out
```

The scorer names logs by file name; the archived output renames them to
their index ids.

SITL, from an ArduPilot checkout at `a1fbfbcdc7`:

```sh
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.EK3HardLandingRearm
OUT=/tmp/v34942 <archive>/34942/data/sitl/variants.sh "$PWD"
# probes, in a scratch tree only:
python3 <archive>/34942/data/sitl/insert_harness.py . <archive>/34942/data/sitl/drift_probe.txt ABDriftProbe
Tools/autotest/autotest.py test.Copter.ABDriftProbe
git checkout -- Tools/autotest/arducopter.py
```
