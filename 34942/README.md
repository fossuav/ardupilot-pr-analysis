# PR #34942 - EKF3: fix the on-ground height check and apply it without a vertical velocity

Analysis archive for [ArduPilot/ardupilot#34942](https://github.com/ArduPilot/ardupilot/pull/34942).
Branch `pr-ekf3-gnd-hgt-check` (andyp1per fork), base `master` at
`278a68a57a`. PR head `3c73e8b64b` (nine commits, squashed 2026-10-31,
see the note at the end); reworked at `3da7a8cf2e` (eight commits), force-pushed
2026-10-31 over the opened head `a1fbfbcdc7` (five commits, 2026-10-30,
kept locally on `pre-rework/pr-ekf3-gnd-hgt-check-20261031`). The flight evidence is from the Q25 airframe on the
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
maintainer may want discussed first. Late 2026-10-31: with the pilot's resets
repeated in Replay, Flight test 3's re-arm is not refused (VD 0.35 m/s, flown
1.05); the PR body is corrected, see "Flight test 3 with the pilot's resets repeated".

## The flight

Q25 `0cb49e7` vertical runaway (2818322/52), 2026-10-30, SFD beta
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

The 29 Oct runaway on the same board, Q25 `308a7e73` (2818322/45), has two
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

### The flight: Flight test 3 (q25-0cb4-ft3, 2818322/55)

Same Q25 board and firmware (`0cb49e7dfb`; MAVLink optical flow, no GPS:
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

#### Superseded 2026-10-31 by repeating the pilot's resets in Replay

With both resets repeated at their logged times, the flown code's replay
matches the flight to 1e-5 over 139-169 s and from 334.7 s to the end,
which holds the drop and the 355.92 s arm; see "Flight test 3 with the pilot's resets repeated".
The paragraph above is left in place because every earlier verdict on
this log's later arms rests on it.

### Replay (tier 1b), 2026-10-31, at the rework

Build: refresh12 `2e2936166d` plus `data/replay/stages-v2.py` 1 2 3 4 5 G 6
and `data/replay/instrument-v2.diff`. 15 logs, 65 arms. Outputs, log names
replaced by index ids: `data/replay/score-v2-2026-10-31.txt` (scorer
`score-v2.py`, which also fixes the aiding-mode labels of `score.py`:
EKF3's 0/1/2 are ABSOLUTE/NONE/RELATIVE) and `arms-v2-2026-10-31.txt`
(`arm_table.py`).

| | arms | at `3da7a8cf2e` |
|---|---|---|
| went up with a flown VD of 1.0 to 4.3 m/s | 6 | 4 refused (q25-0cb4-run 17.98, 100.58; q25-308a-run 52.10; q25-0cb4-ft3 355.92 on the diverged replay); q25-0cb4-run 288.08 arms after the rest reset with 0.00 m/s; q25-308a-run 62.90 goes up with -1.25 m/s (flown -2.87) |
| other MicoAir arms | 39 | 10 refused, 8 re-arms 1.1 to 3.9 s after a disarm and 2 first arms |
| SFD-O4 | 20 | none refused |

All 14 refusals are on the height error, filter 1.1 to 4.4 m, replayed VD
under 0.5 m/s at 7. Apart from 62.90, every allowed arm goes up under
0.6 m/s (max 0.56). 62.90 is an EKF whose accel bias the #32473 fault
corrupted in flight: the rest reset zeroes the velocity and clears the
filter, the bias builds the velocity again, and the filter has not
re-accumulated 1 m by the arm.

#### Superseded 2026-10-31 for q25-0cb4-ft3 355.92

Replayed with the pilot's resets repeated, on the beta at `c46a09ec56`
(this series as `3c73e8b64b`), 355.92 is allowed: filter 0.95 m, VD
0.35 m/s against the flown 1.05. 499.82 (1.2 s after a disarm, VD 0.07)
is refused instead. The table above is left as measured; its ft3 verdicts
after 138.62 s were taken on a state the flight never had. See
"Flight test 3 with the pilot's resets repeated".

The free-fall skip (commit 6) applies, over all 15 logs, only during the
falls after the disarms in the air on q25-0cb4-run (94.48-95.08 s) and
q25-308a-run (45.30-45.80 s) and for 0.3 s of handling at boot on
q25-0cb4-run (12.98-13.28 s). Those windows move when the EKF resets
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
| q25-0cb4-run 17.98 | 1.53 | 0.01 | refused as unhealthy: the EKF had reset itself on the boot divergence and was still realigning (replay VD 0.26) |
| q25-0cb4-run 100.58 | 4.28 | 8.73 | refused, height error |
| q25-0cb4-run 288.08 | 1.43 | 1.00 | refused, height error, at the threshold |
| q25-308a-run 52.10 | 1.12 | 0.00 | refused as unhealthy, realigning after a reset the height error triggered |
| q25-308a-run 62.90 | -2.87 | 2.69 | refused, height error |

Other arms refused on the MicoAir board type, 9 of 27 (q25-0cb4 at 15.68,
175.88, 482.48, 494.88 s; q25-0cb4-run at 194.38, 218.18, 261.08,
441.88 s; q25-308a-run at 92.60 s):

- eight are re-arms 1.1 to 3.9 s after a disarm, with the filter at 1.0 to
  3.5 m and flight VD 0.37 m/s or less except 92.60 s (-0.62 m/s);
- q25-0cb4 15.68 s is the log's first arm, where Replay cannot follow the
  flight: the flight's own arm-pending bootstrap reset at 14.68 s is not
  in the DAL.

None of the 20 arms on SFD-O4 (log54-log65) is refused; core 1 there runs
AID_ABSOLUTE without a measured vertical velocity, so the test applied.
On the ground, 68.7 s in height error across 24 episodes and 7 forced
resets, all on the MicoAir logs (q25v1-op-0e2c is the other board of the
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
- Keeping the height filter through the rest reset (covers a bias-built velocity like q25-308a-run 62.90) is unmeasured.

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
  its own `fusingAglKfVel` branch. Replay of q25-0cb4-run, q25-0cb4-ft3 and
  q25-308a-run (all `EK3_OPTIONS 92`) on topup3 never set the stamp, and
  reproduced the rework's figures: the 93.98 s drop reset at rest after
  2.7 s with VD 4.67 and the 100.58 s arm refused on the height error;
  q25-308a-run 54.70 reset after 5.4 s with VD -2.19 and 62.90 went up
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
| MAV_CMD_SET_EKF_SOURCE_SET (master's) | "Failed to get EKF.flags=831": after set 2 and back to set 1 the EKF never regains a position ("Need Position Estimate", "Check mag field" xy diff 121 rising to 241) | the PR's CI fails the same way (sitltest-copter-tests1e on `3da7a8cf2e`). Bisect on the stack: commits 1-4 pass, 1-5 fail, so commit 5 (`bf1ea90b4e`, the stillness check cap). Mechanism and fix: "The static yaw reference" below |
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

- MAV_CMD_SET_EKF_SOURCE_SET and commit 5: reproduced on the PR head and
  fixed by `dc76e048a6`, see "The static yaw reference" below.
- Whether the moving-platform and VRF tests should expect the refusal, or
  the refusal is too eager for a GPS copter whose velD is rejected. Below:
  no change in #34942; the tests are #32471's and #32473's to adapt.

Files: `data/sfd-topup3/` holds the scripts (`instrument_stale.py`, the
Replay and SITL logging; `stale_probe.py`, per-disarm rest checks;
`why_disagree.py`, `vd_disarmed.py`, `probe_test.py`, `bisect_srcset.sh`,
`cmp_34942_stages.sh`) and `stale_probe.out`. They name scratch paths from
the session that ran them.

## The static yaw reference (2026-10-31), the CI failure fixed

MAV_CMD_SET_EKF_SOURCE_SET, failing in sitltest-copter-tests1e at
`3da7a8cf2e`, reproduces on the PR head in a scratch build of master's base.
Fixed by `dc76e048a6` "AP_NavEKF3: take the static yaw reference before it is
first fused", on branch `fix/34942-static-yaw` (worktree
`../tfix-ab-34942p`), pushed 2026-10-31 as a fast-forward of the PR
(`3da7a8cf2e` -> `dc76e048a6`); on SFD refresh12 as `3429fc6dfd`, locked in
`1ff61d2db5`.

The mechanism:

- With no yaw source and the vehicle still, `SelectMagFusion()` fuses
  `yawAngDataStatic` (`fuseEulerYaw(STATIC)`, R = `sq(yawAngErr)`). The
  reference is stored only while the vehicle is not still, and nothing
  initialises it.
- On master the first `updateMovementCheck()` sample is differenced against
  a zero `accel_prev`: `prevOnGround` starts true, so the reseed branch does
  not run. That holds the check off for about 0.24 s at boot (4.45-4.69 s
  in SITL), which takes the reference: yaw 0, before the initial alignment
  at 5.89 s, with R = 0.5^2.
- Commit 5's cap limits that sample to 4x the limit, so a vehicle that boots
  still reads still from its first sample and never takes it. R is then 0
  and the yaw 0.
- In the test, 0.2 s on set 2 (no yaw source) while still fuses yaw 0
  against 272 deg with zero noise. On the ground a failed yaw innovation
  test still fuses (`MagFusion.cpp:1224-1230`). XKF1.GZ goes from -0.18 to
  -28.6 deg/s on both cores within 0.3 s, the yaw spins about 22 deg/s, and
  "Check mag field" and "Need Position Estimate" never clear.

The fix stores the reference also while it has never been stored
(`yawAngDataStatic.time_ms == 0`), which restores master's boot state.

- SITL: MAV_CMD_SET_EKF_SOURCE_SET fails without the fix and passes with it;
  GZ stays at -0.18 deg/s and the yaw at 270 deg through 50 s. Also pass:
  EK3HardLandingRearm, AHRSSwitchBackendYawReset, EK3_EXT_NAV_vel_without_vert,
  EKF3SRCPerCore, EKFSource, FlowAidingRestartsWithoutYawFusion,
  FlowGyroZBiasNoYawReference, the four GPSForYaw tests, GPSViconSwitching,
  GSF, GSF_reset, LoiterNoCompassYaw and LoiterNoCompassYawGPS, and the
  whole tests1e shard except MountSiyiZT30. That one fails on a local
  pymavlink without `camera_device_id`, which is environmental.
- The Q25 is affected: no compass (`COMPASS_ENABLE 0`) and `EK3_SRCn_YAW 0`
  on every set, so it runs the static path on every still boot.
- Replay, topup3 against topup3 with the fix, 15 logs and 65 arms:
  - 13 logs are bit-identical in replayed core 0: all eight SFD-O4,
    q25-0cb4-run, q25-308a-run, q25-5b70, q25v1-op-0e2c and q25-0cb4.
  - q25-308a differs from 7.21 s, at boot, and the fix tracks the flight:
    rms yaw against flown 0.73 deg, against 19.84 without it.
  - q25-0cb4-ft3 differs from 8.72 s. With the fix it matches the
    pre-#34942 replay and the flight sample for sample from 8 to 24 s.
    Without it, XKF1.GZ froze at 0.02 deg/s with the yaw pinned at 0, where
    the flight learned 0.55.
- Verdicts: one arm changes, ft3 126.12 s (2.1 s after a disarm, VD -0.04),
  from refused to allowed. On the rework's own base (refresh12 `2e2936166d`
  plus `stages-v2.py`, scored with `arm_table.py`), ft3 goes from the
  rework's four refusals to three; 355.92 stays refused. The PR's Q25 row
  becomes 9 refused, 7 of them re-arms.
- ft3 at 26 s: both #34942 builds snap the yaw to about 3 deg. That is the
  "EKF3 IMUn forced reset" (master's `099d6aa72e`, filter status 0 for 5 s
  while disarmed), after the height error made the handled vehicle
  unhealthy at about 21 s. With no yaw source a new core starts at yaw 0: an
  arbitrary heading re-zeroed, not a navigation error.

#### Superseded 2026-10-31: 355.92 is not refused

"355.92 stays refused" above is on the replay that leaves the flight at
138.62 s. With the pilot's resets repeated it is allowed and 499.82
refused, so the PR's rows become 3 of the 6 big-error arms refused, and
10 other Q25 arms refused, 8 of them re-arms. See
"Flight test 3 with the pilot's resets repeated".

Quick review of `dc76e048a6`: COMMENT. Mechanical gate clean apart from
`dal.snprintf` read as `printf` at `Outputs.cpp:98` (a false positive, the
same pattern as line 91). Codex's cold read raised one must-fix: the
reference taken at the start is the pre-alignment yaw, and a yaw reset does
not refresh it while the vehicle stays still. True, and master does the
same. A 60 s probe still on set 2 (`run_set2_probe.sh`) gives identical
results on master and on the fix: yaw pulled from 272 to 9.6 deg, and Z gyro
bias from -0.10 to -1.15 deg/s, still -1.13 back on set 1. That is a latent
master bug, not this PR's. A fix would refresh the reference on a yaw reset;
it is a separate upstream PR. It does not reach the Q25, which never aligns
a yaw.

The other stack failures, re-examined:

- AccelBiasMovingPlatform, Copter.Replay's accel bias inhibit leg (both
  `SIM_PLAT_ACC_Z -1`) and VibrationRectificationBiasLearning's bit-2 leg:
  nothing to change in #34942. The EKF is really wrong on the ground in each
  (VD -2.4 to -6 m/s; 1.7 m/s) without the PR too, and the tests assume
  arming. They are #32471's and #32473's to adapt, and the bit-2 VD is a
  #32471 question.
- EK3_ZeroVelFusionNotUsedWithGPS: intermittent, passes alone.

PR body edits drafted (`pr-body-dc76.md` in scratch): the Q25 row as above,
and the boot effect, the fix and the master residual in the stillness
paragraph.

Files: `data/static-yaw/` holds the probe and Replay scripts
(`srcset_timeline.py`, `still_onset.py`, `gz_peak.py`, `gz_at.py`,
`cmp_replays.py`, `yaw_timeline.py`, `arm_verdicts.py`, `replay_pair.sh`,
`cmp_pair.sh`, `rework_base_ft3.sh`, `insert_set2_probe.py`,
`run_set2_probe.sh`), the fix as `static-yaw-fix.diff`, and
`arm_verdicts_fix.out`.

## The reset at rest waits while a measurement is fused (2026-10-31)

Pushed as `2a52c965e2`, a fast-forward of `dc76e048a6`; on SFD refresh12 as
`467782a96c` and `f93bd10a6f`.

The failure: EK3_ZeroVelFusionNotUsedWithGPS (SFD's) failed identically in
two full SFD runs and passed alone, so it was not chance.
- On the ship, SITL logged "SIM Hit ground at 1.06 m/s", which started a new
  rest. GPS velD was fused but 0.5 m/s off while the EKF learned the injected
  0.7 m/s/s bias.
- The reset fired on core 1, and AZ settled at 0.65.
- Run alone, no reset fired, and the test passed.

The change: the check waits while a measured vertical velocity is being fused,
`measuredVertVelFused()`. That is navigation velD fused in the last 2 s with
`velTestRatio < 1`, or body velocity fused in the last 2 s with all three
`bodyVelTestRatio` under 1. Once nothing is being fused it decides once, as
before.

Review history:
- First version, `c4ed65e00f`: the reset skipped when one was fused in the
  last 0.5 s, latched once per rest. Codex raised three findings:
  - the latch made one recent fusion suppress the reset for the whole rest;
  - 0.5 s missed a passing sample from 2 Hz sources;
  - `prevBodyVelFuseTime_ms` is set when any one axis passes.
- Second version, `329335f9f2`: waits instead of latching, with the
  latest-test-ratio term and a 1 s window. The audit closed 1 and 3 and left
  2 partial for 1 Hz sources.
- Final: a 2 s window. A rejected sample ends the wait at once through its
  test ratio, so the window only matters for a source that stops arriving.
  The audit closed both remaining findings. Quick review APPROVE.

Measured:
- EK3HardLandingRearm on the PR's own base passes three times on the final
  version; the GPS leg resets on both cores and rises 0.05 to 0.08 m.
  - A fourth run, under a six-target build's load, failed the
    falling-re-arm leg ("armed only once on the ground"). The arm went
    through, but the harness read the range finder too late. That leg is
    flow-only, where no measured vertical velocity is ever fused.
- Replay cannot change: SFD-O4 logs 54-65 had 40 rest checks and no resets,
  and the Q25 fuses no measured vertical velocity (GPS1_TYPE 0, no body
  odometry).
- The full SFD set on the final code: 124 of 124. The ship test passes at the
  place in the set where it had failed twice; the deck bump still happens, and
  no reset follows.

Open:
- The PR body passages on the reset are not yet updated; a draft is with Andy.
- On the SFD beta from refresh12 topup3, promoted 2026-10-31; unflown.

## Flown on SFD-O4 (2026-10-31)

SFD refresh12 topup3, firmware `ea8cef60` (the flight card commit, same code as `f93bd10a`), which carries `2a52c965e2`'s EKF3, logs 66-71. 8 arms, with no
"height error" refusal and no reset at rest after any of six landings; VD
at arm read 0.00-0.01 m/s. Replay matches every log on both cores to 1e-7,
except log67 after an arm-pending bootstrap reset at 29.87 s. That reset is
not a DAL event, and unrelated to this PR.

Every flight ended in a power cycle, so the re-arm after a landing was not
flown: that is the case Replay refused in 0 of 20 arms on logs 54-65. The
Q25 was not flown either.

## Squash audit (2026-10-31)

On logs 66-71: commit 5 (`bf1ea90b4e`) has flown. Reverting it changes the
EKF on all six logs: core 1's yaw moves 0.14-0.29 deg from EKF start at every
boot, log66 core 0's yaw 0.57 deg at 61.4 s, and core 1's yaw 3.1 deg around
264-313 s. Its message gives the SFD-O4 effect as three landings only; it
needs the boot yaw added. The static yaw fix `dc76e048a6` stays on top: six
logs replay identically without it, as SFD-O4 has a compass. The rest-fused
fix `2a52c965e2` may fold into G (`21a8e3a683`): neither ran (identical
without it, and G never reset), giving 9 commits with the same tree
(`squash-audit-2026-10-31/A.md`).

## Flight test 3 with the pilot's resets repeated (2026-10-31)

Replay records nothing for an EKF bootstrap reset
(`AP_AHRS::reset_configured_backend()`, from aux 187 or arm-pending), so
every earlier replay of q25-0cb4-ft3 left the flight at the pilot's first
reset, 138.62 s, and scored the later arms on a state the flight never
had. `data/ft3-resets/inject_reset.py` (scratch only) makes Replay call
`NavEKF3::InitialiseFilterBootstrap()` before the first EKF3 update frame
that starts after each logged "EKF bootstrap reset performed" (TimeUS
138625046 and 334324738). The RC loop runs after the fast loop's AHRS
update, so that is the first frame the flown EKF ran after its reset.

Checked on the flown code, refresh12 `2e2936166d` (EKF, DAL and Replay as
`0cb49e7dfb`), core 0 against the flown XKF1 sample by sample
(`cmp-flown-2026-10-31.txt`, `diff-bins-2026-10-31.txt`):

- Without the injection it differs from 138.62 s to the end (VD up to
  1.67 m/s, yaw 180 deg).
- With it, VD and PD match to 1e-5 over 139-169 s and from 334.7 s to the
  end (517.6 s): the drop at 354.12 s and 8 of the 13 arms.
- 171-334 s still differs (VD up to 0.25 m/s, yaw up to 12 deg). The
  pilot's rng_hgt_hold.lua switched range finder height on and off from
  170.93 to 279.05 s ("RngHgt: on", "RngHgt: off") with no PARM record,
  and the flown EKF reset its terrain offset from the range at 170.96 s
  where the replay did not. The second reset brings them back together.
- The first sample after each reset differs only because the flown EKF
  logs after the RC loop.

Then the SFD beta at refresh12 topup4 `c46a09ec56`, whose EKF3 is
topup3's `f93bd10a6f` and whose #34942 changes are line for line those of
the PR head `3c73e8b64b`, with the injection and `instrument_latest.py`,
scored with `arm_score.py` (`arms-2026-10-31.txt`; filter as a magnitude):

| arm (s) | after a disarm | no injection | injected | VD replay / flown (m/s) | filter (m) |
|---|---|---|---|---|---|
| 33.02 | first arm | refused | refused | 0.00 / 0.00 | 1.75 |
| 296.62 | 2.0 s | refused | refused, in 171-334 s | 0.00 / 0.00 | 1.81 |
| 355.92 | 1.8 s, a drop | refused | allowed | 0.35 / 1.05 | 0.95 |
| 499.82 | 1.2 s, a drop | allowed | refused | 0.07 / 0.07 | 1.08 |

The no-injection verdicts are the static yaw section's three. The other
nine arms are allowed both ways, with the injection at 0.05 m/s or less
except 447.22 (-0.18, flown -0.17). With the injection no reset at rest
fires; without it one does, in the diverged part. The forced reset at
about 25.5 s is in both.

355.92, from the drop to the arm (`timeline-2026-10-31.txt`):

- The vehicle never reads still (`onGroundNotMoving` 0 throughout), so no
  rest check runs. At 0.35 m/s it would be under the reset's 0.5 m/s
  anyway.
- `velDotNEDfilt.z` peaks at 3.6 m/s/s in the fall, under the 0.5 g skip,
  which never applies.
- The filter grows from 0 at the disarm to 0.95 m at the arm, about 0.02 m
  per 0.1 s at the end; on that trend it would have crossed 1 m about
  0.3 s later (extrapolated, not measured).
- The 0.35 m/s against the flown 1.05 is not the series acting at the arm.
  The beta with #34942's EKF3 reversed (`git diff e78e5ccda2^ c46a09ec56
  -- libraries/AP_NavEKF3`) matches the flight to 5e-5 from 334.5 s to the
  end. With it, the replay departs from about 335.5 s (4e-3 m/s), widely
  from 338.5 s, and reaches the drop with VD 0.50 against the flown 1.02
  at 353.92 s. Which commit moves it was not measured. (Both betas also
  differ from the flight from 23.4 s, from other changes on the beta,
  until the second reset re-syncs them.)
- No threshold on the filter separates it: allowed re-arms with no
  velocity error read 0.94 m (126.12) and 0.85 m (462.12).

499.82: disarmed at about 1 m (range 1.01 to 0.14 m in 0.2 s). After the
touchdown the baro reads up to 3 m below its value before the disarm,
while VD stays under 0.1 m/s. A refusal of a clean arm; on optical flow
the five-second unhealthy reset should clear it (mechanism only; the
vehicle took off).

33.02: handled at boot (IMU accel norm 4 to 14 m/s/s). The flown and
replayed EKF both read VD -1 to -3.5 m/s from 26 to 31 s, and the replay
sits 1.3 to 2.6 m off the baro; the refusal is right.

The pilot re-arms within 2 s of a disarm five times in this log (344.82,
355.92, 420.02, 447.22, 499.82 s), three of them after a drop from 1.0 to
1.6 m (354.12, 445.52, 498.62 s).

Conclusion: the series does not refuse Flight test 3's re-arm. It is the
limit the PR states, a re-arm before the vehicle reads still, and the
guidance (on the ground and still for at least a second) is what covers
it. The PR body was corrected 2026-10-31 at 23:12 UTC: of the 6 big-error
arms 3 refused and this one up at 0.35 m/s; 10 other Q25 arms refused, 8
of them re-arms; the limit and Replay passages rewritten.

Owed: q25-0cb4's arm-pending bootstrap reset at 14.68 s (TimeUS
14683608) has not been repeated; its arms are still scored on the
diverged state.

## File map

With the pilot's resets repeated (2026-10-31), in `data/ft3-resets/`:

- `inject_reset.py` - Replay repeats logged EKF3 bootstrap resets (`REPLAY_EKF3_RESET_US`)
- `instrument_latest.py` - height check and rest reset logging (XKFM layout, C 150) on the beta
- `run_one.sh`, `arm_score.py`, `timeline.py` - running one log, per-arm verdicts, a window's state
- `cmp_flown.py`, `diff_bins.py` - replayed core against flown, overall and per bin
- `events.py`, `parm_changes.py` - a log's MSG/ARM events and runtime parameter changes, raw TimeUS
- `cmp-flown-2026-10-31.txt`, `diff-bins-2026-10-31.txt`, `arms-2026-10-31.txt`,
  `timeline-2026-10-31.txt` - the outputs

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
# the private analysis repo, one path per line, into loglist.txt
<archive>/34942/data/replay/run_replay.sh build/sitl/tool/Replay loglist.txt out
python3 <archive>/34942/data/replay/score.py loglist.txt out
```

The scorer names logs by file name; the archived output renames them to
their index ids.

Flight test 3 with the pilot's resets repeated, from a beta checkout:

```sh
git worktree add --detach ../wt-ft3 c46a09ec56 && cd ../wt-ft3
git submodule update --init --recursive
python3 <archive>/34942/data/ft3-resets/inject_reset.py .
python3 <archive>/34942/data/ft3-resets/instrument_latest.py .
./waf configure --board sitl && ./waf replay
# resolve q25-0cb4-ft3 to a path with find_log.py and the private analysis repo
R=<archive>/34942/data/ft3-resets
$R/run_one.sh build/sitl/tool/Replay <log> out 138625046,334324738
python3 $R/arm_score.py out/logs/00000001.BIN "0-169,334.7-520"
python3 $R/timeline.py out/logs/00000001.BIN 353.9 357.0
```

The flown-code check is the same at `2e2936166d` with `inject_reset.py`
only, then `python3 $R/cmp_flown.py out/logs/00000001.BIN 0 138.6 169
334.3 354.0 358.0`.

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

## 2026-10-31: squashed after the flight audit

Pushed `2a52c965e2` -> `3c73e8b64b` (force, 10 commits to 9, same tree; backup `pre-squash/34942-1031`). What folded and what stays on top, and why: `squash-audit-2026-10-31/squash_A.md`.

## 2026-11-02 (later): the reset at rest waits for the fusion horizon; the clip floor

AP-Review round 1 (COMMENT at `3c73e8b64b`): one should-fix, one minor.
Fixed on refresh12 (`r1102b/34942-r12c`: `07a7f7805e`, `a270c53823`,
`16f39fb057`) and ported to `sq/34942-1102c` (`7d966e6838`, `d964c88b6a`,
`b39c0e9485`, head `b39c0e9485`), not pushed. A cold read of the first
version (fresh Claude reviewer, Codex out) found nothing blocking and five
wording/test points, all taken in this version (the `-r12b`/`-1102b` and
earlier branches are superseded).

Should-fix: stillness comes from the latest IMU sample (`updateMovementCheck()`
reads `ins.get_gyro()`/`get_accel()`), while the reset acts at the fusion
horizon, so buffered samples rebuild the velocity and the latch blocks a
second reset. Reproduced in SITL (EK3HardLandingRearm on the PR head), at the
landing that ends the flow quick re-arm leg rather than the 25 m drop: in
three of four baseline runs the first reset came 25-45 ms after the disarm
(stillness is declared 2 ms after a disarm, as the movement check's
rate-of-change terms restart at their limits, under the 0.7 x SF hysteresis),
VD rebuilt to 0.70-0.79 m/s, and a second reset 0.3 s later came only because
stillness dropped out; the fourth run needed none. The 25 m drop reset once in
every run, leaving 0.10-0.16 m/s (the bot saw 1.4-1.8 there). Fix:
`restStartTime_ms` records the IMU time stillness began, and the one-shot
check waits until `imuDataDelayed.time_ms` reaches it, a cost of one horizon:
60 ms with baro height (EK3_HGT_DELAY; flow is 10 ms), up to 250 ms with GPS.
After: no reset needed at that landing in every run, |VD| under 0.03 m/s.

Why only the reset waits (checked in the source): zero-velocity fusion
(PosVelFusion `onGroundNotFlying`, both paths) and the accel bias
observability test (core.cpp `is_bias_observable`) act every cycle; the
static yaw reference (MagFusion `yawAngDataStatic`) is captured on the last
cycle before the flag rises, one horizon before the rest, but the flag needs
the gyro under about 4.2 deg/s (3 deg/s x OGNM_TEST_SF 2 x 0.7) and, except
right after a disarm, the rate-of-change metric settled (about 0.26 s at
400 Hz), so it is off by about a degree at most, inside its 0.05 rad noise.

Minor: the clip on rejected ground height samples. On master Sub's
`EK3_ALT_M_NSE` defaults to 0.01 (not on 4.7, where Sub uses 2.0); ExtNav
height noise is floored at 0.1 m: both give a gate under 1 m by default.
Probe (Copter, disarmed, no GPS, sustained baro step, prearm text): with
ALT_M_NSE 0.01 or 0.1 a 3 m or 10 m step was reported only after 3.8-4.0 s
(the gate widens while samples are rejected; the 5 s height timeout then
resets), so "never" did not hold; a 1.5 m step is fused, reported by neither;
with the floor, 2.8 s. The EKF-unhealthy flag (what the new test leg times):
3.6-3.8 s without the floor, 1.6 s with it. The clip is now
`MAX(gate, 2 * GND_HGT_ERR_LIMIT)`, the 1 m threshold one constant shared with
`onGroundHgtError()`. Over the threshold `healthy()` is false: ESTIMATOR_ATTITUDE
drops and the 10 s the primary must stay healthy before lane selection
(AP_NavEKF3.cpp `lastUnhealthyTime_us`) restarts.

Tests: the `fly_and_land()` check (two landings; the GPS leg's reset count is
always 0, so only its velocity check applies) and a new no-aiding leg
(EK3_ALT_M_NSE 0.01, 3 m step, unhealthy within 2.5 s: fails without the
floor, 1.6 s with it). On the PR: EK3HardLandingRearm (passes twice; fails
without the clip commit), EK3_ZeroVelFusionNotUsedWithGPS, Sub DiveManual,
AltitudeHold, ModeChanges, DiveMission. MatekF405 (float EKF) builds without
EKF warnings. `pr_review.py checks` flags `dal.snprintf` at
AP_NavEKF3_Outputs.cpp:115 as printf, a false positive in an earlier commit.

Replay: refresh12 Replay with and without both changes (first version; the
constant refactor is numerically the same) on SFD-O4 logs 66-71: XKF1/XKF2
on both replayed cores identical (binaries differ). A LOG_REPLAY 1 SITL log
from the fixed PR build replays exactly at matched timestamps across the
25 m drop's reset (VD -10.96 -> 0.03); `check_replay.py` reports FAILED on it
only from a ~100 ms startup offset, as it pairs records in sequence.

Seen, not in scope: at the 25 m drop's reset PD jumps from about -6 m to
36-38 m in every run, before and after the fix (ResetHeight to hgtMea after
the test's 20 m baro glitch leg).

Pushed 2026-11-02 (afternoon) to andyp1per with a lease: `3c73e8b64b` -> `b39c0e9485` (refresh12 `df341758a7` locks it). Reply: https://github.com/ArduPilot/ardupilot/pull/34942#issuecomment-6580089744.

## 2026-11-02: Q25 indoor loiter logs on c46a09ec (refresh12 topup4)

`Q25 - MicoAir743v2 - 4.7.2 - c46a09e - Indoor Loiter 1 of 2.bin` and `2 of 2`
(tester A's Q25). Flow only, baro height
(EK3_SRC1_POSZ 1, EK3_RNG_USE_HGT -1), no yaw source. Three flights: log 1 one,
log 2 two in one boot. INS_ACC_VRFB_Z was still 0.0417 (the card asked for 0),
so with ACC_ZBIAS_LEARN 10 v3 applied the old total as the change since arming.

- Every landing came down with the EKF 1.5-2.2 m above the baro: in flight the
  baro read 1.5 m above the range finder (log 2 at 88 s: RF 1.14 m, baro
  2.64 m, EKF 3.32 m), prop wash indoors, and at touchdown ground effect
  took it to -1.5 m.
- Log 2, first landing (disarm 92.16 s): the height innovation sat at -2 m,
  XKF4.SS went to 0 at 94.2 s (healthy() false on the ground height check),
  and 5 s later upstream's disarmed "EKF3 IMU0 forced reset" fired (98.57 s):
  a full InitialiseFilterBootstrap, PD to 0 and yaw from 332.4 to 359.7 deg (no
  yaw source). Re-arm at 106.16 s went fine. This is a new interaction: #34942
  putting the height error into healthy() makes filterStatus all zero, which is
  the forced reset's trigger, so a slow height convergence on the ground now
  reinitialises the whole filter rather than only refusing arming.
- Log 1 (disarm 120.36 s) and log 2's second landing (185.26 s): the EKF pulled
  its height down to the baro through VD (0.16 m/s for 10 s; 0.79 m/s at 5 s),
  one SS=0 sample in log 2. No "vertical velocity reset at rest": VD was
  0.06-0.07 m/s when rest began, and the reset is a one-shot at that moment by
  design; the later VD came from the height correction, not a drop.
- No "height error" refusal seen: the only re-arm came after the forced reset.
- Boot (T1): log 2, still from power-on, yaw 0.00-0.03 deg and GZ 0.00-0.01 to
  arming. Log 1 was turned during boot; once still, yaw wandered +-1.3 deg over
  8 s while GZ learned -0.29 deg/s against a raw gyro near 0.
- T2 (#34941, acro over 45 deg) and T3 (CPU load, BRD_IDLE_STATS 0) not flown.

## 2026-11-02 (evening): a height error no longer forces a reset

`AP_NavEKF3: do not force a reset for a height error on the ground`:
refresh12 `88dfc049b7` (branch `r1102c/34942-r12`, on `df341758a7`), PR port
`2826fdfc10` (`sq/34942-1102d`, on `b39c0e9485`). healthy() is split into
healthyApartFromGndHgt() and the ground height check; updateFilterStatus()
sets gndHgtErrorHoldsStatus when the status is zero only because of that
check (otherwise healthy, aligned, quaternion valid, so the attitude flag
would be set), and the forced reset's timer keeps running while it holds.
healthy(), filterStatus and all their readers (NavEKF3 lane selection and
primary health, the pre-arm check, the status flags/ESTIMATOR_STATUS, AHRS)
are unchanged. A core unhealthy for another reason as well still resets.

Replay A/B through refresh12's Replay (before = `df341758a7`, after =
`88dfc049b7`):
- gl2 (Q25 log 2): before, the forced reset at 98.6 s as flown (yaw 332.4 ->
  354.4 deg); after, no reset, PD converges from -2.27 m and the status turns
  non-zero at 100.46 s (before: 99.66 s after the reinit), i.e. a re-arm
  would pass 8.3 s after the disarm; yaw holds 332.3-332.5 deg at rest.
- gl1 and SFD-O4 logs 66-71: identical on every core (max XKF1 difference 0).

What the flown forced reset cost: after it the EKF learned a Z gyro bias of
2.9-3.7 deg/s (XKF1.GZ; raw IMU GyrZ at rest -0.01 deg/s), its yaw slid 354
-> 322 deg at rest, and in the second flight, yaw stick at 1500 throughout,
the raw gyro shows the vehicle turning at +2.33 deg/s (110-150 s) and +2.81
deg/s (160-184 s): Loiter held a heading built on a bias that did not exist.
The no-reset replay keeps GZ at 0.00 and its yaw follows that turn.

Root of the wrong bias (fixed below): yawAngDataStatic (#34942's static
yaw reference) is not cleared by InitialiseVariables(), and onGroundNotMoving
survives the reinit, so after any bootstrap reset at rest the pre-reset yaw
(332.4) is fused against the reinitialised one and the difference goes into
the gyro bias. A forced reset for another cause, or #32401's arm-pending
bootstrap reset, would do the same; clearing yawAngDataStatic.time_ms in
InitialiseVariables() would re-take it.

Tests: EK3HardLandingRearm and EK3_ZeroVelFusionNotUsedWithGPS pass on the
port and on refresh12; MatekF405 builds with no warnings. No SITL leg: the
reset needs every status flag zero (no GPS), and a SITL flow landing does not
hold a >1 m height disagreement for 5 s reliably. Not pushed.

Update, same evening: the static yaw carry-over fixed too, as its own commit
ahead of the forced-reset one (it is a bug in the static-yaw commit
`3c73e8b64b`; the forced-reset change is a separate behaviour). The earlier
`88dfc049b7`/`2826fdfc10` branches are superseded:
- refresh12 `r1102c/34942-r12b` (on `df341758a7`): `082192f019` retake the
  static yaw reference after a reset at rest, `2d4b680994` the forced reset.
- PR `sq/34942-1102e` (on `b39c0e9485`): `fbe93d4ece`, `48d602d374`; hunks
  identical to refresh12's.

Mechanism confirmed in the source: InitialiseVariables(), run only from
InitialiseFilterBootstrap(), sets onGround/prevOnGround true and clears
restStartTime_ms but leaves onGroundNotMoving and yawAngDataStatic, and
updateMovementCheck() only clears onGroundNotMoving when prevOnGround is
false, so a still vehicle stays still through the reset and the reference
(time_ms != 0) is never retaken. Paths that bootstrap a still core: the
disarmed forced reset, and NavEKF3::InitialiseFilterBootstrap() (on
refresh12 #32401's arm-pending reset through AHRS reset_configured_backend());
AHRS reset() at startup only, with the reference still zero. Lane switches
do not reinitialise a core. The fix clears yawAngDataStatic.time_ms in
InitialiseVariables(), so SelectMagFusion() retakes it from the new yaw
(prevTnb is recomputed from the new quaternion before it runs).

Replay A/B of gl2 with the forced reset still happening (Replay of
`df341758a7` vs `082192f019` alone):
- XKF1.GZ after 98.6 s: 2.93-3.70 deg/s before, 0.00-0.08 deg/s with the fix.
- Yaw at rest 100-108 s: 354 -> 322 deg before; 360.0/0.0 deg held with it.
- Second flight, yaw stick at 1500: before, yaw held about 355 deg (the
  vehicle turning under it); with the fix the yaw follows the real turn,
  39.3 -> 91.6 deg in 20 s (2.6 deg/s) against the raw gyro's 2.3-2.8 deg/s.
- gl1 and logs 66-71: identical with the fix alone and with both fixes;
  with both, gl2 is identical to the forced-reset change alone (no reset, so
  the static fix never acts). log67's arm-pending reset is not a DAL event,
  so no replay exercises that path.

Tests: EK3HardLandingRearm, EK3_ZeroVelFusionNotUsedWithGPS and
FlowAidingRestartsWithoutYawFusion pass on the port and on refresh12;
MatekF405 builds with no warnings; branch conventions pass (the mechanical
gate's only must-fix is the earlier dal.snprintf false positive). Not pushed.

Update after the cold read of `fbe93d4ece`/`48d602d374` (nothing blocking):
rebuilt as five commits, refactors first (ARCH-19). Superseded:
`r1102c/34942-r12`/`-r12b`, `sq/34942-1102d`/`-1102e`.

| | refresh12 `r1102c/34942-r12c` (on `df341758a7`) | PR `sq/34942-1102g` (on `b39c0e9485`) |
|---|---|---|
| store the static yaw reference through one function (no behaviour) | `13730ea212` | `98285fe3dd` |
| split the ground height check out of healthy() (no behaviour) | `c072f9f301` | `759034f128` |
| retake the static yaw reference after any yaw reset | `d4eb8e1b58` | `7e4a0bbcfe` |
| autotest: static yaw retaken after an EKF reset at rest | `ef670a8cc5` | `d33585757e` |
| wait longer to force a reset over a ground height error | `7697270b17` | `37f52d6d15` |

- Static yaw: also stored from resetQuatStateYawOnly(), which every yaw
  reset goes through (compass alignment setYawFromMag(), GPS/external yaw
  alignYawAngle(), realignYawGPS(), the EKF-GSF reset), so a still vehicle
  with a compass no longer keeps a pre-alignment reference; none of those is
  made by the static fusion, so no loop. Stored at once, not just cleared,
  because a static fusion can follow a yaw reset in the same update.
- Forced reset: no new member. last_filter_ok_ms is still set only by a
  non-zero status (a core never healthy is never reset). A core whose
  status is zero only because of the ground height check (otherwise
  healthy, aligned, finite quaternion), evaluated only when the status is
  zero, waits GND_HGT_ERR_RESET_MS = 30 s instead of 5 s, about four times
  the Q25's 6.8 s; the cap bounds a height held off by a wrong accel bias,
  which ResetHeight() does not correct and the height timeout (rejected
  samples only) never reaches. The commit says it changes "fix on-ground
  height innovation filter never updating"'s five-second reset.
- Test EKFBootstrapResetStaticYaw: lands at heading 90 with a compass,
  switches to a GPS set with no yaw, resets from the EKF_RESET aux switch
  while still, checks the yaw moved (92.5 deg) and |XKF1.GZ| < 0.5 deg/s.
  Old EKF code fails 3 of 3 (refresh12 2, port 1; GZ 6.30-6.36 deg/s);
  fixed passes 5 of 5 (refresh12 3, port 2; GZ 0.06-0.11 deg/s). The
  forced reset stays replay-only.
- Replay through refresh12 builds: the refactors identical to before on all
  eight logs; the static fix alone changes only gl2 after 98.66 s (max
  |GZ| 0.08 deg/s against 3.74, yaw holding then following the real turn);
  all five commits change only gl2, identical to the no-reset run (status
  recovers 8.3 s after the disarm).
- Tests on both branches: EKFBootstrapReset, EK3HardLandingRearm,
  EK3_ZeroVelFusionNotUsedWithGPS, FlowAidingRestartsWithoutYawFusion pass;
  MatekF405 0 warnings; branch conventions pass (gate: the old dal.snprintf
  false positive only).

Final, after a third cold read (Andy's decision): the forced-reset hold is
dropped. The 5 s reset was written (tridge, EKF2 `8ea7df3efe`, 2018) for an
idle filter whose healthy() carried this same hgtInnovFiltState test;
master's EKF3 height test has not tripped since 4.1, so the hold would in
effect add a 30 s reset; and with the static-yaw fix alone the Q25 replay
recovers 7.50 s after the disarm (sooner than 8.3 s with the hold) with no
false bias. The healthy() split went with it (only the hold used it,
ARCH-14). All the hold branches above are superseded.

| | refresh12 `r1102c/34942-r12d` (on `df341758a7`) | PR `sq/34942-1102i` (on `b39c0e9485`) |
|---|---|---|
| store the static yaw reference through one function (no behaviour) | `3d9c8a1417` | `a1ae2f1bc5` |
| retake the static yaw reference after any yaw reset | `b041cb53a7` | `d0274705ff` |
| autotest: static yaw retaken after an EKF reset at rest (every core) | `61a0cabc56` | `ae295465bc` |
| autotest: static yaw reference keeps the compass alignment | `7f4b8e79f0` | `f52182b114` |

- New test StaticYawKeepsCompassYaw: boot at 90 deg with a compass, never
  move, switch to a GPS source set with no yaw. Without the
  resetQuatStateYawOnly() store the reference stays at the 0 deg taken
  before the compass aligned, and core 0's yaw is pulled 21.6-22.1 deg in
  15 s (fails 3 of 3, threshold 15 deg); with it, 6.9-7.0 deg (passes 6 of
  6), the residual being what compass fusion moved the yaw after the
  alignment store while still. The Z gyro bias does not separate them here
  (0.18-0.20 deg/s both). EKFBootstrapResetStaticYaw now checks every core
  through a shared helper: pre-fix code 6.36 deg/s on core 0 (fails), fixed
  0.06 deg/s on both cores.
- Replay through refresh12 (`df341758a7` vs r12d): gl1 and logs 66-71
  identical; gl2 differs only after the forced reset at 98.66 s, which still
  fires: status recovers 7.50 s after the disarm either way; max |GZ| after
  it 0.08 deg/s against 3.74; yaw holds 360.0/0.0 deg at rest (before:
  356.7 -> 321.1) and in the second flight follows the real turn, 67.3 ->
  147.4 deg from 120 to 150 s (2.7 deg/s, raw gyro 2.3-2.8).
- Tests on both branches: EKFBootstrapResetStaticYaw,
  StaticYawKeepsCompassYaw, EKFBootstrapReset, EK3HardLandingRearm,
  EK3_ZeroVelFusionNotUsedWithGPS, FlowAidingRestartsWithoutYawFusion pass;
  MatekF405 0 warnings; branch conventions pass (gate: the old
  dal.snprintf false positive only).

Update after the cold read of the two tests (late 2026-11-02): the test
fixes are folded into the test commits; the EKF commits are unchanged.
Superseded: `r1102c/34942-r12d`, `sq/34942-1102i`.

| | refresh12 `r1102c/34942-r12e` (on `df341758a7`) | PR `sq/34942-1102k` (on `b39c0e9485`) |
|---|---|---|
| store the static yaw reference through one function (no behaviour) | `27d80427f9` | `b1edba2b5a` |
| retake the static yaw reference after any yaw reset | `757b8963df` | `d23bbcc841` |
| autotest: static yaw retaken after an EKF reset at rest | `92ba59b269` | `537676d074` |
| autotest: static yaw reference keeps the compass alignment | `994fbc6263` | `a29dd0dcda` |

- Comments corrected: source set 2 carries no GPS settings over; with
  only EK3_SRC2_YAW set to 0 (the rest default to none) a still disarmed
  vehicle drops to AID_NONE and holds its yaw by fusing the static
  reference. Both tests share static_yaw_test_setup(), which sets the
  parameters and restarts SITL at heading 90 through
  customise_SITL_commandline(); the separate reboot is gone.
- The 7 deg residual in StaticYawKeepsCompassYaw, traced in the log: the
  compass alignment at 5.88 s used COMPASS_DEC 0 and put the yaw at 77.2
  deg, which the fixed code stores as the reference; the declination
  arrived later with no yaw reset, and compass fusion at rest moved the
  yaw to about 94 deg by "origin set" (20 s) and 92.6 deg at the switch
  (43.85 s); the static fusion then pulled it back toward 77.2. The test
  now holds the declination (COMPASS_AUTODEC 0, COMPASS_DEC 0,
  EK3_MAG_EF_LIM 0): residual 0.1 deg, bound tightened from 15 to 5 deg.
  Without the resetQuatStateYawOnly() store the reference stays at the 0
  deg taken before the compass aligned: 25.0-25.2 deg, fails 2 of 2.
- The residual is a property master already has: the reference is
  refreshed only while moving (`if (!onGroundNotMoving)`), so a yaw
  source that moves the yaw at rest leaves it stale until the vehicle
  moves. Not changed here; a possible follow-up.
- The bias check is dropped from StaticYawKeepsCompassYaw: it did not
  separate the fixed and unfixed code (0.18-0.20 deg/s both).
- Pre-fix EKF (`b39c0e9485`) with the new tests: StaticYawKeepsCompassYaw
  25.0 deg (fails), EKFBootstrapResetStaticYaw GZ 6.24 deg/s (fails).
  Fixed: 0.1 deg and 92.5 deg moved with GZ 0.06 deg/s.
- The port's `import struct` is placed in sorted order (between socket
  and subprocess); refresh12 already imports it.
- Tests on both branches, at these heads: EKFBootstrapResetStaticYaw and
  StaticYawKeepsCompassYaw pass 3 of 3 each (port 4 of 4 counting a
  re-run on the final head: yaw moved 92.5-92.6 deg, GZ 0.06 deg/s, and
  0.1 deg on both cores); EKFBootstrapReset, EK3HardLandingRearm,
  EK3_ZeroVelFusionNotUsedWithGPS, FlowAidingRestartsWithoutYawFusion
  pass. MatekF405 builds with 0 warnings (874808 B flash, 108220 B free);
  branch conventions pass; flake8 clean; the mechanical gate's only
  must-fix is the old dal.snprintf false positive. Replay unchanged from
  r12d (same EKF hunks). Not pushed.

## 2026-11-02 (evening): squash

The Q25 logs flew 3c73e8b64b ("take the static yaw reference before it is
first fused"): log 2, still from power-on, held yaw within 0.03 deg to the
arm, and replay with it reverted differs by up to 101 deg. Folded into
"keep a shock from holding off the on-ground stillness check" on
`sq/34942-1102l` (head `d986e313d8`, 16 commits, tree identical to the
worker's `sq/34942-1102k`; backup `pre-squash/34942-1102` at
`b39c0e9485`). The four static-yaw commits stay on top, unflown. Not pushed.

## 2026-11-02 (late): two more Q25 logs on c46a09ec, after tester A's VRFB learning

`Inside house brown floor.bin` and `Inside to outside bad althold.bin`. Both
fly ACC_ZBIAS_LEARN 10 with INS_ACC_VRFB_Z 0.0131 (from tester A's learning flight,
which is not among these logs; was 0.0417), "Hover Z-bias IMU0: 0.013" at
boot. Both arm in VALT (mode 29) and fly Loiter; each ends with a switch to
LAND by a script (ModeReason 32 SCRIPTING; the vehicle runs patrios.lua,
flow_quality_osd and added_flight_mod).

- Brown floor: the disarmed forced reset fired again, 6.3 s after the
  disarm (97.36 -> 103.67 s), the path the static-yaw fix covers; no re-arm
  followed, so no flight carried a false bias.
- Bad althold: Loiter holds the EKF height to within about 0.1 m of target
  throughout; the EKF height is the baro (EK3_SRC1_POSZ 1, EK3_RNG_USE_HGT
  -1) and surface tracking is off (SURFTRAK_MODE 0), so it holds a baro
  height, not height above ground. With BARO1_THST_SCALE -150 the baro still
  reads 1.62 m high in the inside hover against the range finder (IQR
  1.53-1.75 m, ThO 0.38), and moves with the indoor/outdoor pressure; over
  the flight the height above ground ran 0.23-2.9 m at a held altitude
  (2.7-2.9 m at 84-86 s, around going outside). baro_thst_cal.py suggests
  -235, but from a free hover, which it warns is not a valid fit; the range
  finder residual points to about -200 to -220. Same mechanism as the
  indoor landings' 1.5-2.2 m EKF offset.

## 2026-11-03: keep the learned gyro bias across a bootstrap reset

Users reported yaw jitter without a compass and poor VALT on the new
betas. Andy's point: #33498 holds the Z gyro bias in flight at the value
learned at rest, and a bootstrap reset zeroed it (`ZERO_FARRAY(statesArray)`
in InitialiseVariables(), then gyro_bias.zero() and the inactive biases),
so the forced reset this PR makes fire after landings, the EKF_RESET aux
function and #32401's arm-pending reset all send a quick re-arm off with
what had been relearned from zero. Seeding from INS_GYROFFS was weighed
and rejected: the INS takes the stored offsets off every sample
(AP_InertialSensor_Backend.cpp:166), so the state is the residual and zero
already means "trust the stored offsets". Q25: INS_GYR_CAL 0, TCAL on,
residual -0.68 deg/s on 10-30 (b0cb4), -0.4..-0.5 on 10-29, -0.14..-0.25
on 11-02 flight 1.

SITL A/B (throwaway harness GyroBiasResetAB, scratch r1103/gbab): 0.6 deg/s
SIM_GYR1-3_BIAS_Z, INS_GYR_CAL 0, offsets 0, flow only, no yaw source; 60
s at rest, EKF_RESET, wait N, arm, 60 s Loiter hover; GZ in deg/s, drift
is SIM yaw minus EKF yaw over the hover. Bias before the reset 0.63.

| Armed after the reset | refresh12 df9604a31f: GZ at arm, drift | fix: GZ at arm, drift |
|---|---|---|
| 6.8 s (N 2) | 0.44, 15.1 deg | 0.65, 2.8 deg |
| 15 s (N 10) | 0.64, 3.8 deg | 0.66, 2.4 deg |
| 35 s (N 30) | 0.67, 3.1 deg | 0.67, 3.0 deg |

The bias relearns from zero in about 10 s at rest, so only a re-arm
inside that costs the flight. The first attempt changed nothing (0.43,
15.7 deg): it stopped the later gyro_bias.zero() but InitialiseVariables()
had already zeroed the state vector; the fix saves the bias before it, as
refresh12 already saves the origin.

Commits: refresh12 `dfd8194b85` (EKF), `80cbb8106b`
(EKFBootstrapResetKeepsGyroBias); port `sq/34942-1103a` `2c8c1575d8`,
`d1d731fa1b` on `d986e313d8`. The test fails on the old code (core 0
0.61 -> 0.00 deg/s) and passes with the fix (0.61 held); on both branches
it passes with EKFBootstrapReset, EKFBootstrapResetStaticYaw,
StaticYawKeepsCompassYaw, EK3HardLandingRearm, FlowGyroZBiasNoYawReference
and FlowAidingRestartsWithoutYawFusion. Unflown. Not pushed.

Andy's decision (same day), option 2 of three: the EKF's own reset keeps
the gyro biases, the EKF_RESET switch zeroes them (a full reset of a
filter that may be wrong; the cold read's point that keeping any finite
bias would carry a phantom like 566576e804's 2.9-3.7 deg/s through an
EKF_RESET). NavEKF3::InitialiseFilterBootstrap(), the commanded entry,
calls the new core zeroGyroBiases() first. Master's comment on it said
"the filter always resets with the existing gyro biases", which the core
never did; reworded. On SFD #32401's arm-pending reset uses the same
entry, so it zeroes too; Andy called implicit resets keep, so moving it
to keep is a #32401 follow-up if wanted. Not taken: keeping only within
the initial bias uncertainty (2.5 deg/s default), which drops 3.7 but
only just 2.9.

Test EKFResetGyroBias (replaces EKFBootstrapResetKeepsGyroBias): learn
0.6 deg/s at rest, EKF_RESET must zero it, relearn, then a 15 m baro step
(rejected by the height gate; a 3 m step is fused away in 2.5 s with the
innovation overshooting to -0.85 m and never resets) brings the forced
reset 5.2 s later and the bias must hold within 0.15 deg/s. Beta EKF code
fails the forced-reset half (0.65 -> 0.00), keep-everywhere fails the
EKF_RESET half (0.61 kept), the split passes (0.61 -> 0.00, then 0.64 ->
0.64-0.67). The EKF_RESET switch sequence is shared with
EKFBootstrapResetStaticYaw (ekf_reset_by_switch()). Cold-read nits taken:
both directions checked, the two SITL IMUs only, one-line comments, the
accel bias reason in the message.

Commits: refresh12 `19e5ca3831`, `76a16f3278` on top of `dfd8194b85`,
`80cbb8106b`; the PR gets them as two, `sq/34942-1103b` `c83b148144`
(EKF), `713ca4946f` (test) on `d986e313d8` (supersedes `-1103a`). Both
pass with the six neighbouring tests. Description addition drafted
(scratch r1103/34942_desc_new.md). Unflown. Pushed 2026-11-03 at `713ca4946f` (a fast-forward of `d986e313d8`); refresh12 locks it in `9ebc2d45ef`.

## 2026-11-03 (later): bot round 3 minor, the static yaw reference with a fused yaw

AP-Review round 3 (COMMENT at `d986e313d8`, before the gyro bias push):
one new minor, the two disclosed trade-offs (disarmed DCM fallback on a
baro step, late-fall re-arm refusal under 0.5 g) unchanged. The minor: a
declination that arrives after the compass alignment (default
COMPASS_AUTODEC) turns the yaw with no reset, so a still vehicle
switched to a source set with no yaw source is pulled back to the stale
reference; it suggested `|| use_compass()`.

Taken first as suggested (refresh12 `e84029d45f`/`c21a862f8a`); the
cold read found it wrong for GPS yaw with compass fallback: use_compass()
is true while a still vehicle waits for GPS yaw, when the compass is not
fused and the STATIC fusion is the only heading observation, so
retaking the reference made it learn nothing while P[12][12] still
collapsed. New test StaticYawLearnsBiasAwaitingGPSYaw (copter-gps-for-yaw,
SRC1_YAW 3, SIM_GPS2_ENABLE 0, 0.6 deg/s bias, 40 s still):

| store rule | waiting for GPS yaw, GZ | StaticYawKeepsCompassYaw, default dec |
|---|---|---|
| none (`713ca4946f`) | 0.63, pass | 7.0-7.1 deg, fail |
| `use_compass()` | 0.00, fail | 2.2-2.3 deg, pass |
| `recentYawFusion()` (5 s, #33498's) | 0.62-0.63, pass | 2.8 deg, pass |

Kept recentYawFusion() (ARCH-2: a fused yaw, not a usable compass;
ARCH-8 reuse). The 2.8 deg residual is a phantom Z gyro bias from the
compass alignment and declination with a bias-free simulated gyro: XKF1.GZ
-1.81 deg/s 30 s before the switch, -0.18 at it, and the yaw then turns
at about that rate (92.63 -> 95.44 deg); pre-existing, not the
reference. Left: the resetQuatStateYawOnly() store (566576e804) no
longer has a test that fails without it, as a fused yaw follows every
alignment while still; it still covers a reset with no fusion after it.

Port `sq/34942-1103d`: `746779f445` (EKF), `facdfb7b81` (test) on
`713ca4946f`, a fast-forward. Refresh12 `e95d72c3a9`, `56d71821f3` on top
of `e84029d45f`/`c21a862f8a`. All 12 related tests pass on both
(StaticYaw x2, EKFBootstrapResetStaticYaw, EKFResetGyroBias,
EKFBootstrapReset, EK3HardLandingRearm, the two flow tests, GPSForYaw,
GPSForYawCompassLearn, GSF, GSF_reset). Unflown. Not pushed.

Second cold read of the recentYawFusion() commits: no bug; two minors
taken. (1) recentYawFusion() looks back 5 s, so the reference follows the
yaw for up to 5 s after the last fusion: in the compass test the yaw went
92.63 -> 93.68 deg in those 5 s and froze there, so about 1 deg of the
2.8 is the window and the rest the phantom bias; comments and messages
now say so. (2) StaticYawLearnsBiasAwaitingGPSYaw never checked that no
GPS yaw arrived; it now fails on any "yaw align" message (with
SIM_GPS2_ENABLE 1 it fails on "EKF3 IMU1 yaw aligned"). Refresh12
`5a328d4364` (comments), `bcaaa11cfd` (premise check). Port supersedes
-1103d: `sq/34942-1103e` `4b4e0fe806` (EKF), `d742c388ee` (test) on
`713ca4946f`, a fast-forward; EKF and test diffs identical to refresh12's
net change; the 12 tests pass. Pushed 2026-11-03 at `d742c388ee` (fast-forward of `713ca4946f`). The description draft also replaces the
stale "as on master, the reference is the yaw from before the initial
alignment" sentence (wrong since 566576e804).

Description updated 2026-11-03 (after the `d742c388ee` push): the forced
reset keeps the learned gyro biases, EKF_RESET zeroes them, the static
yaw reference is stored within 5 s of a yaw fusion, and the stale "as on
master, the reference is the yaw from before the initial alignment"
sentence is replaced. 2151 words.

## 2026-11-03 (afternoon): bot round 4, the EKF step average across a reset

AP-Review round 4 (COMMENT at `713ca4946f`): the kept gyro bias states
are delta angles per EKF step and InitialiseVariables() restarts
dtEkfAvg at EKF_TARGET_DT (12 ms), so where the EKF does not step at
12 ms the kept bias acts at the wrong rate for about 3 s. Confirmed:
EKFResetGyroBias at SCHED_LOOP_RATE 50 read 0.64 -> 0.64-1.04 deg/s
after the forced reset (fails); copter's default 400 Hz steps at about
12.5 ms, so the earlier A/B could not see it. The Q25 runs
SCHED_LOOP_RATE 200, where the EKF steps at 10 ms (0.83x).

Scaling the kept states by dtEkfAvg after/before was tried and rejected:
right at the reset, then 0.41 deg/s as the average climbed back. Kept
dtEkfAvg across the reset instead: 0.64-0.65 at 50 and 400 Hz. Cold
read: keeping it unconditionally changes the first boot, as during the
1 s start-up window readIMUData(false) pushes a frame per 24+ ms
accumulated and drifts the average (magnitude not measured: the
onboard log starts after the EKF initialises); now kept only for a core
that has run (ekfStartTime_ms != 0, set only by InitialiseVariables()),
so a first boot takes the old path. Its other points taken: the stale
test comment, the context note, the message naming 100-300 Hz too.

Refresh12 `77c33e88d4`, `46e47b0956`, `dd4191b19d`, `1a1c0cd734` (after
the topup6 promotion `f9fb97e8eb`). Port `sq/34942-1103g` `a74daa3f37`
(EKF), `2804706ae0` (test) on `d742c388ee`, a fast-forward, identical
to refresh12's net change. Port tests: EKFResetGyroBias (400, 50), the
three other reset/static yaw tests, StaticYawLearnsBiasAwaitingGPSYaw,
EK3HardLandingRearm, the two flow tests, Plane.Replay; refresh12 also
the Heli, Plane, QuadPlane and Sub SFD tests. Unflown. Pushed 2026-11-03 at `2804706ae0` (fast-forward of `d742c388ee`).

## 2026-11-03 (afternoon): tester B's 4-inch logs on 2dc4a918 and 71054882

Correction: the June logs compared below (tester B's June 4-inch log64-67, 4.7.0-beta6)
are a different vehicle (Andy). The June settings, IMU and roll-trim
comparisons are withdrawn, and so is the conclusion that the setup
changed EK3_RNG_USE_HGT; good 4.7.0 logs of this vehicle are to come.
The findings from log 62 alone stand.

`62 12-31-1979 7-00-00 PM.bin` (tester B's 4-inch, SFD 4.7.2 logs),
SkySakuraH743, QUAD/X_REV, firmware "SmallFastDrone V4.7.2 (2dc4a918)",
which is not in our refs. Reports: yaw deviation, small but early and
often; poor centre-stick VALT, "sucked into the floor"; more roll
deviation, not holding the accel-cal level. Log starts at arming (LOG_
DISARMED 0): ACRO takeoff 31.9 s, VALT 63.9-177.1 s. No yaw source
(EK3_SRC1_YAW 0, compass logged), flow, EK3_IMU_MASK 2 (one core on IMU2),
SCHED_LOOP_RATE 200, ACC_ZBIAS_LEARN 6 with INS_ACC2_VRFB_Z -0.050.

- Floor (82-99 s): descending to about 0.3 m the EKF height (baro, as
  EK3_RNG_USE_HGT -1) climbs while the range finder falls, VALT backs off
  and the vehicle sits on the floor from 88 s (RF 0.02-0.13 m). On the floor
  the baro swings -2.94 to +2.09 m in the prop wash; the pilot holds climb
  stick (C3 1550-1588) and the EKF believes it climbs to 2.2 m, so throttle
  stays 0.12-0.13 until 99 s. EK3_RNG_USE_HGT -1, BARO1_THST_SCALE -255,
  SURFTRAK_MODE 1, VALT_POS_EXPO 5 (EK3_RNG_USE_HGT is index 42 in every
  build). CTUN.DSAlt is not logged in VALT, so surface tracking does not
  act there.
- Roll: tracking is fine (DesRoll = Roll); from 100 s the pilot holds about
  +2.3-2.8 deg of roll stick to stay in place. The EKF's lateral accel bias
  (XKF2.AY) sat at -0.09 through the floor contact and stepped at 99.4 s,
  as the vehicle lifted off, to -0.26 then +0.29 by 102 s; flow recovery
  had been deferred ("range stale") from 88.3 s. Hypothesis, not shown from
  the innovations: flow fusion resuming after 11 s of dead reckoning put
  part of the correction into lateral accel bias, and the EKF's level is
  off by that since. In steady hover both IMUs read near zero lateral
  specific force (IMU1 0.03 deg, IMU0 0.37 deg), so the accel cannot show
  the tilt there.
- Yaw: XKF1.GZ -0.34 to -0.41 deg/s all flight. Against a tilt-compensated
  heading from the logged compasses, EKF yaw drifts under 0.1 deg/s in the
  steady hover 110-134 s (231-235 and 355-360 deg), so the bias is right;
  the compass is unusable elsewhere (swings with heading). Yaw tracking is
  close (RATE.Y vs YDes); 12 excursions over 10 deg/s with the yaw stick
  centred, 3 within 0.5 s of a flow vel reset, 6 in the last 8 s. No
  estimation cause found.
- 25 "flow vel reset (axis lockout)" in 145 s of flight.

Log 63 (firmware 71054882, also not in
our refs; same settings, LOG_REPLAY 1 on both): ACRO 32-92 s, VALT
92-160 s. XKF1.GZ is 0.00 at takeoff (log 62: -0.39, learned on the
ground) and runs to -0.82 deg/s by 70 s in ACRO, then -0.41 to -0.78 in
VALT. With no yaw source #33498 should hold it in flight; FuseOptFlow does
mask state 12 without a recent yaw fusion, so another fusion path (or
cross-covariance) is learning the Z bias in flight. Next: replay log 63
and find which fusion moves state 12.

Tester B's 4-inch on 4.7.0 (logs 47 and 48, firmware
57be0525), the same vehicle and settings but for: AHRS_TRIM_X +0.0180
(4.7.2: -0.0122, a 1.73 deg roll change from a new accel cal at 38 C
against 32 C), compass off (4.7.2: on, not used for yaw), MOT_HOVER_LEARN
2 (0), INS_ACC2_VRFB_Z 0.0027 (-0.050), GND_EFFECT_COMP 1 (folded into
GNDEFF_ALT, which carries it), EK3_FLOW_MIN_H 0.1 (now FLOW_HGT_MIN 0, not
migrated), FLOW_HF_RATEF 1 (dropped).

- Not like for like: VALT flown at 1.25-2.25 m on 4.7.0 (range finder,
  never under 0.5 m), at 0.25-0.75 m on 4.7.2 (rarely over 1.25 m). The
  4.7.0 logs touch the floor only at takeoff and landing; the 4.7.2 logs
  10 and 15 times in flight, with climb stick held and the EKF believing
  0.6-1.8 m. 4.7.0 has the same lockout recovery and message and logs no
  lockout reset at 2 m; 4.7.2 logs 22-23, all low. So the floor symptoms
  are in a band the 4.7.0 logs never entered.
- The code difference in that band: below 0.1 m in flight 4.7.0
  (EK3_FLOW_MIN_H, default 0.1) fused zero flow and held zero velocity;
  4.7.2's FLOW_HGT_MIN defaults to 0 and discards the flow below it, so
  tester B's 4.7.2 fuses unfocused flow down to the ground clearance check.
- Yaw: XKF1.GZ wanders more on 4.7.0 (-1.28..+0.59 deg/s, no #33498); yaw
  rate tracking in VALT 4.6-5.2 deg/s rms on both. No regression seen.
- Roll: median desired roll in VALT +0.01/+0.05 (4.7.0) against +0.34/+0.32
  (4.7.2), upper quartile 1.8-2.4 on both. No difference shown.
- Wanted: a 4.7.0 low hover at 0.3-0.7 m, or a 4.7.2 flight at 2 m.

Sources (Andy asked whether tester B uses flow and the range finder): yes, on all
four logs. EK3_SRC1_VELXY 5, FLOW_TYPE 6 (DroneCAN), RNGFND1_TYPE 24
(DroneCAN, down, 0.08-45 m), flow innovations in every XKF5; height is
baro only (EK3_RNG_USE_HGT -1, SRC1_POSZ 1); GPS fitted, no fix.

Range finder near the floor on 4.7.2: about 600 in-flight samples under
0.15 m, mostly status 2 (out of range low), 150 status 4 (good) at
0.10-0.20 m, with "CAN[125] challenging surface detected" twice. I first
took them for dropouts (XKF5.HAGL 0.65 m, baro 0.6-0.8 m, OF.Qual about
100), then withdrew that: HAGL is the baro height less a terrain state and
the baro is the sensor in question; the good samples track a climb
smoothly (log 63 125.5-126.5 s: 0.16, 0.28, 0.43 m) and the AGL KF
(XKFA.HAgl 0.13-0.15 m) agrees. So the vehicle was most likely within about
0.2 m of the floor while the EKF height (baro) read 1.2-1.8 m, as first
read. The AGL KF never fused its velocity into the EKF (XKFA.VFuse 0 in
both logs), so no range finder path reaches the EKF height.

Replay of log 63 on refresh12 `f085ae566f` (scratch r1103/replay63/base):
two replayed cores (100, 101) where the flight ran one; core 100 follows
the flown yaw (14/9, 109/105, 185/191, 278/280 deg) and height shape, but
its Z gyro bias stays -0.08 to -0.25 deg/s until the landing where the
flown one ran to -0.82. Fidelity is limited (log starts at arming, up to
2.2 m and 40 deg apart), but the in-flight bias learning is the flown
build's, not this code's. 71054882 and 2dc4a918 are in neither our refs
nor fossuav/smallfastdrone on GitHub; SkySakuraH743 is in our tree.

Tester B's account of the VALT mechanism, checked against the code (2026-11-03):
- 57be0525's update_ground_effect_detector() re-latches takeoff_expected
  while airborne below TKOFF_GNDEFF_ALT, on the AGL KF height when there is
  one ("re-enable ground effect compensation when descending back below
  threshold"); the 5 s cap clears it and the re-latch sets it in the same
  call. Current AP_GroundEffect::update() has no re-latch: takeoff_expected
  only while landed, cleared at 5 s or above GNDEFF_ALT after the hold;
  touchdown_expected needs a commanded descent under -0.05 m/s. So in a
  centre-stick low hover neither flag is set after 5 s. Confirmed.
- VALT's 0.1 m/s correction clamp (mode_valt.cpp:59) keys off those
  flags, so it does not engage there. Confirmed.
- "EKF immune to the wash": overstated. With a flag set the baro variance
  is x4 (gndEffectBaroScaler) and the innovation is floored at -0.5 m on
  one side only (against the baro pulling the height down). A baro reading
  high, as tester B's did (EKF 1.2-1.8 m at about 0.15 m), is still fused at
  reduced weight; 4.7.0 damped it rather than removed it.
- Not new: 32472/README.md records dropping the re-latch deliberately and
  predicts this ("a low hover being pulled down at mid-stick is not
  covered", BF_X log210 pulled onto the floor), with the follow-up
  deferred. The reason it was dropped (log41: an SFD-only zero-velocity
  fusion gated on takeoff_expected) no longer applies: that fusion is now
  gated on onGroundNotMoving only (the comment still names
  takeoff_expected).
- Re-latching takeoff_expected also changes it for its other readers: the
  AGL KF velD step hold (off while set), the terrain re-open on each
  clear, hover Z-bias learning (paused while set). Alternatives: set
  touchdown_expected rather than takeoff_expected for a low hover when an
  AGL height exists (keeps takeoff_expected's meaning; note its 60 s cap),
  or rangefinder height near the ground (EK3_RNG_USE_HGT 3 is 1.35 m of
  RNGFND1_MAX 45 m; tester B's range finder drops out at the floor itself).

The low hover pull-down, reproduced in SITL and A/B'd on 4.7.0, 4.7.2 and
both alternatives above (2026-11-03): ../32472/README.md, "the low hover
pulled into the floor, on 4.7.2". Restoring the clamp alone or setting
touchdown_expected in a low hover gives back 4.7.0's result, about half
the hold on the floor with a baro reading 1.5 m high at it, and does
worse than 4.7.2 with a noisy one. Neither is the fix.

Later the same day: the 4.7.0 logs 66 and 67, flown low on the same board,
hit the floor from near-centre stick 2.0 times a minute below 0.6 m
against 4.7.2's 9.3. That advantage comes from the range finder switching
4.7.0's re-latch; baro-only in SITL the builds do not differ. EK3_OPTIONS
26 steadies the hover and usually holds it in SITL, and is not a reliable
fix (seeded runs). It also wants EK3_AGL_ABIAS_P 0.3. ALT_HOLD with
surface tracking holds where VALT does not. All in
the private analysis repo and `../32472/README.md`.

## 2026-11-03 (evening): the EKF's own reset zeroes X and Y, keeps Z

Prompted by tester B's 4-inch log 69, which armed with a 0.38 deg/s roll gyro bias
after the vehicle was carried powered. Since `dfd8194b85` the EKF's own
forced reset keeps all three gyro biases, so biases learned while the
vehicle is carried survive it. Change (refresh12 `f297033f6e`, not yet on
this PR's branch): `InitialiseFilterBootstrap()` keeps Z, which with no yaw
reference is learned only at rest, and starts X and Y from zero, which are
learned again from gravity within a second at rest. The inactive IMUs'
biases are treated the same way. A commanded reset still zeroes all three
(`zeroGyroBiases()`).

Replay of the Q25's 11 replayable 4.7.2 logs, base refresh12 `f085ae566f`
against base plus this change alone:

- Boots 36, 43, 45, 49, 59, 60, 69, 70: no attitude gap over 1 deg.
- Boot 52, the replayed reset at 29.7 s: X/Y -0.53/-1.93 deg/s are zeroed
  where base keeps them. Both relearn to about +0.1/-0.6 within 3 s.
  Afterwards they differ by 1-2 deg for 11 s of flight, neither better.
- Boot 55: 0.7 s on the ground and 5 s of flight differ, base slightly
  closer to DCM.
- Boot 165: the replayed EKF reset at 31.0 s while the vehicle was held at
  30-60 deg of tilt. The change started X/Y from zero, and after the vehicle
  was set down at 44 s it sat within 1 deg of DCM. Base drifted 3-6 deg and
  to VE -37 m/s disarmed, and needed a second forced reset. Over 47 s
  disarmed the mean error was 5.7 deg on base and 1.1 deg with the change;
  over 26 s on the ground, 1.1 and 0.7. The flown EKF (0e2c977) was 11-14
  deg off at the same time, with -0.75/-1.34 deg/s X/Y biases.

The kept Z can be wrong too: boot 52's -2.3 deg/s Z was learned during a
divergence before arming. Z is kept by the user's choice (2026-11-03),
since dropping it gives back the yaw drift `dfd8194b85` fixed.

Test (`fb0e459bba`, then `902d52b738` after a cold review): EKFResetGyroBias
also simulates 0.6 deg/s X and Y gyro biases. At 400 and 50 Hz the EKF's
own reset drops X and Y from 0.65 to 0.00, they are back at 0.65 within 2
s (checked 1.5 s after), and Z stays at 0.64-0.65. EKF_RESET zeroes all
three. Without `f297033f6e` it fails: X kept at 0.64. EKFBootstrapReset,
EKFBootstrapResetStaticYaw, StaticYawKeepsCompassYaw,
StaticYawLearnsBiasAwaitingGPSYaw and EK3HardLandingRearm pass. On the PR
branch: `4ac4f4b1f8` and `3879fc6a6e`, pushed 2026-11-03. Then rebased onto
master `802db19de1` (the bot's should-fix): master's `7de72dbde0` moved the
body odometry members into `bodyOdm`, renamed in the two commits that use
them, and a comment conflict on `yawAngDataStatic` was taken onto master's
struct layout. PR head `94f24cdd9c`, mergeable; the PR's six EKF reset and
re-arm tests pass on it. The pre-rebase branch is kept as `sq/34942-1103j`.
Promoted to the beta as refresh12 topup8 (`722d77b5de`), the full SFD set
121 of 121.

The PR branch's own Replay (master-based) cannot replay these 4.7.2 logs:
its output carries only the flown XKF1 records, so the A/B above stands on
refresh12's Replay.

Open from the cold review: keeping body Z assumes a vehicle at rest near
level. On a tailsitter resting on its tail body X is vertical, so the
reset would drop the bias learned about the vertical and keep one gravity
relearns anyway (as master drops all three). Keeping the component along
the vertical from the bootstrap's accelerometer tilt would cover it.

## 2026-11-04 (night): Q25 touchdown snaps the height to a prop-washed baro, carried into a quick re-arm

Boot 142 ("08 VALT after EK3 OPTIONS 92", a8487f0), flight 2: at 0.11 m on the landing the flow lane stopped aiding (112.29 s) and the EKF height stepped from +0.28 to +1.55 m with the range finder at 0.05 m. Entering AID_NONE sets position.z from the delayed baro (master Control.cpp:434, "reset the vertical position state to faster recover from baro errors experienced during touchdown"; the beta subtracts baroHgtOffset), and the baro was in touchdown prop wash (+1.06 m at 112.0, -1.00 m at 113.0). Re-armed 2.4 s after the disarm: the arm-time EKF_ALT_RESET event fired but the EKF still read +1.59 m on the ground, no height-error refusal (below the threshold) and no forced reset (too soon), so flights 3 and 4 flew with the EKF +1.18 and +1.06 m above the range finder, and in flight 3 VALT held the EKF at 2.83 m while the vehicle climbed 0.6 m on the range finder, AGL KF and baro over 14 s. Why the arm reset left the 1.55 m is not yet traced (derived from the log timing and the source; not replayed).

### 2026-11-04 (night): the touchdown snap traced and a gate prototyped

Tonight's eight Q25 logs: seven landings entered AID_NONE near the ground with touchdown_expected set, and the snap stepped the height by 1.3-7 m each time (log 01: -6.3 to -7.95; 02: -6.96; 05: -5.14, -3.22; 06: -2.40; 08: +1.32). A forced reset or an arm-pending bootstrap reset before the next arm cleared it (05, 06); a re-arm before either carried it (08). Snaps without the flags can help: in log 01 one pulled a 6.6 m in-flight error (baro thrust scale 0) back to the ground baro. Prototype r1104/rearm-datum `89170afd20` (local) skips the snap while takeoff or touchdown is expected, as bb615f0f93 does for a source switch. Replay, EKF minus range finder 5-10 s after each takeoff, base -> gate: log 08 flights 3/4 +1.27/+1.10 -> +0.23/+0.04; log 05 flights 4/5 -2.79/-5.40 -> +0.30/+0.49; log 06 flight 2 +0.00 -> +0.98 (the snap's error had tripped the forced reset that cleaned the estimate; without it the pre-touchdown -0.8 m error carried); log 01 mixed (baro misconfigured). Tier 1b, estimator only; no SITL test written. Not a clear win on its own: the wider gap is that nothing re-zeroes the height on the ground before a quick re-arm without GPS (../32768/README.md, same date).

### 2026-11-04 (night): option A made final, the touchdown height reset gated on ground effect

Andy chose option A (gate alone; the range finder is not a reliable on-ground signal). Local branch r1104/touchdown-snap-v2 on a8487f02aa (worktree r1104-rearm-datum): `68cfa26202` AP_NavEKF3: skip the AID_NONE height reset in ground effect (the prototype 89170afd20 unchanged in code, message final), `2f9c02d822` autotest EK3TouchdownHeightNotSnapped. Not pushed, not flown.

Flag claims checked against the source: AP_GroundEffect latches takeoff_expected while armed with land_complete (AP_GroundEffect.cpp:90-94; Copter passes throttle_up only for manual-throttle modes, so in ALT_HOLD/VALT the takeoff anchor refreshes on the ground and the flag holds until the release after takeoff); touchdown_expected needs a slow (<1 m/s) descent demand with the D controller active, slow horizontal and height under GNDEFF_ALT, inside the touchdown window. Caveats: GNDEFF_ALT < 0 clears both flags, so the gate is off; a fast or manual-throttle (STABILIZE) descent is outside touchdown_expected until land_complete latches takeoff_expected; disarmed both are false, so the reset runs. The extra test is the same !assume_zero_sideslip() as bb615f0f93, so planes in forward flight keep the reset. The snap writes stateStruct.position.z only (no posResetD, output observer left to converge); skipping it leaves meaHgtAtTakeOff set (its only other use is the low-pass), and flowFocusRngPosD and lastKnownPositionD consistent.

SITL A/B (tier 2), EK3TouchdownHeightNotSnapped, one core, flow and range finder, no GPS, recorded origin, flow timeout ends aiding with a baro glitch for prop wash: landed and armed, -3 m glitch (floored as ground effect): base -3.18 m at the ground, gate -0.32/-0.28 m (two runs); next flight re-armed 1 s after the disarm hovers -0.30/-0.42 m off on the gate and -0.46 m on base, as the clean SITL baro pulls the height back (on the Q25 it persisted). Disarmed (-20 m glitch, rejected): -21.0 base, -21.3 gate, so the reset still runs; in flight at 4 m after the takeoff window: -21.25 on the gate. Two early harness errors corrected on the way: LOCAL_POSITION_NED is not sent without aiding (heights now read from XKF1/RFND in the log), and a disarm before clearing the glitch let the un-floored baro in after the disarm (the glitch is now cleared as the motors stop). Related tests pass on the gate (17): EKFBootstrapReset, EKFBootstrapResetStaticYaw, EK3HardLandingRearm, BaroGroundEffectAtTakeoff, BaroGroundEffectResetSuppression, BaroGroundEffectRangefinderSwitch, HeightDatumKeptOnArmWhileMoving, HeightDatumKeptOnMidairRearm, BaroDriftClearedAtArm, BaroDriftClearedAfterMidairDisarm, EK3_TerrainStateFollowsHeightReset, EK3_TerrainStateFollowsDatumReset, EK3_TerrainStateHeldOnDriftReset, EKF3RangeFinderOnGround, FlowAidingRestartsWithoutYawFusion, OpticalFlow, Replay. Copter and plane build; gate: the 13 pre-existing E131s only.

Upstream: master has the identical reset (AP_NavEKF3_Control.cpp:432-434) and the same baroInGndEffect test, so it applies with a three-line hand port (master has no baroHgtOffset subtraction or flowFocusRngPosD line); the test helpers and AHRS recorded origin all exist on master. Suggested as its own PR: a three-line change with one failure, independent of #34942 (on-ground height check, forced reset) and #32768 (arm-time datum reset), though both are where its consequences showed; cross-reference both. Log 06 is the open cost: its height was already about 1 m off at the landing, and the reset's larger error is what tripped the forced reset that cleaned it.

### 2026-11-05: the touchdown snap on master, A/B before an upstream PR

Ported to master `1348fd162b` as `r1105/ekf3-touchdown-snap` (local, not pushed): `8ca1873254` AP_NavEKF3 (the gate, three lines, no baroHgtOffset or flowFocusRngPosD on master), `0497299028` autotest (EK3TouchdownHeightNotSnapped, comments rid of #34942 and #32768 mechanisms). Mechanical gate clean, check_branch_conventions passes.

SITL A/B on master (tier 2), fix reverted against fix, binaries md5-checked. The test as committed, a -3 m glitch (reads low, as ground effect does): landed, the height moves -3.21 m on master and -0.28/-0.29 m with the fix; the next flight re-armed 1 s after the disarm hovers 0.11-0.16 m off on master and 0.03-0.05 m with it. Unlike the beta, master has no arm-time datum reset with home set (AP_Arming_Copter.cpp:723-733 moves home instead), so the clean baro pulls the error back while disarmed and the next flight does not carry it. The next-flight check therefore does not fail on master; the ground check does.

Throwaway probes (the test edited, not committed):

| case | master | fix |
|---|---|---|
| +3 m glitch (reads high, as the Q25's), height when aiding stops | +3.30/+3.32 m | +1.36/+1.50 m, rising |
| +3 m, next flight after a 1.6 s disarm | -0.15/-0.23 m | -0.18/-0.19 m |
| -3 m, no disarm, height 7 s after aiding stops | -3.07 m | -1.76 m (dead zone floor creep) |
| -3 m, no disarm, takeoff overshoot (error peak / range peak) | +0.63 m / 2.87 m | +0.21 m / 2.44 m |
| +3 m, no disarm, error at liftoff (8 s on the ground) | +3.13 m | +4.17 m |

Reading high, the ground effect dead zone does not hold the baro out, so with the reset skipped ordinary fusion takes the height to the baro anyway and overshoots (the Z accel bias learns the step), ending further off after 8 s armed on the ground than the reset left it. The beta's Replay gains (log 08, log 05) came through #32768's arm-time reset, which master lacks: #32768's head adds reset_height_datum() where home is already set (AP_Arming_Copter.cpp:756-757), master resets the datum at arm only when home is not set. Not opened upstream.

Corrected the same day: an earlier line here said the Q25's baro read high, from log 08 alone. Replayed, the snaps on the four correctly configured landings went both ways (below), mostly low. The master commit message's "the ground effect dead zone that keeps a baro reading low out of the height" is also wrong: the dead zone clamps each baro innovation to -0.5 m, which slows the pull to a creep but does not stop it (below).

### 2026-11-05: replay of the armed sits, and a long sit on the beta build

Held from the topup10 push for this. Replay (beta Replay with and without the gate, replayed core C=100), EKF height minus range finder from each AID_NONE entry near the ground with touchdown expected to the end of the armed sit:

| log | entry | armed after | base at disarm | gate at disarm |
|---|---|---|---|---|
| 08 | 112.4 s | 0.7 s | +1.47 m | +0.21 m |
| 05 | 131.2 s | 0.6 s | -4.88 m | -0.09 m |
| 05 | 162.5 s | 0.2 s | -4.78 m | +0.06 m |
| 06 | 87.0 s | 1.1 s | -3.24 m | -0.81 m |
| 01 (no baro thrust compensation) | 179.4, 242.6, 374.7, 443.5 s | 0.3-2.2 s | +10.47, +9.87, +0.41, +0.85 m | +15.15, +6.30, +7.06, +11.55 m |

Every Q25 landing disarmed within 2.2 s of aiding stopping, so the logs hold no long armed sit. On log 01 the EKF height was already 6-15 m off in flight and the snap resynced it; the gate keeps that error (3 of 4 worse).

SITL on the beta build (topup9 + gate, the binaries the Replay A/B used), the landed subtest edited to sit armed 10 s after aiding stops, then take off without a disarm (tier 2, constant glitch):

| glitch | base, 2 / 8 / 14 s | gate, 2 / 8 / 14 s | range peak after takeoff, base / gate |
|---|---|---|---|
| +3 m (reads high) | +3.34 / +3.25 / +3.11 m | +1.98 / +3.86 / +4.58 m | 2.95 / 3.48 m |
| -3 m (reads low) | -3.20 / -3.06 / -3.02 m | -0.50 / -2.27 / -3.65 m | 3.07 / 3.04 m |

With a sustained error ordinary fusion takes the height to the baro within about 10 s either way, past it for a high reading (the Z accel bias learns the step); the dead zone only slows a low reading to about 0.3 m/s. No #34942 on-ground check or forced reset fired while armed. So the gate protects the seconds after aiding stops, which covers every Q25 landing on record, and not a long armed sit with the baro still wrong; at idle on the ground the prop wash error is likely smaller than SITL's constant glitch, which is unmeasured. The test comments that the dead zone "keeps it out of the height" hold only over the second they measure.

Placement: the next-flight cost needs #32768's arm-time reset with home set, and #32768 already changes this AID_NONE line (the baroHgtOffset frame fix), so the gate fits #32768 better than a standalone PR. #32768 is frozen under maintainer review; adding to it is the author's decision. Decided the same day: added to #32972 instead, beside its ResetHeight suppression (../32972/README.md, 2026-11-05); the master branch `r1105/ekf3-touchdown-snap` is not used.

Topup10 (the gate without #32972's later armed term, and its test) pushed to the SFD beta 2026-11-05 after the replay above, `a8487f02aa..1bb9af74de`; the next refresh takes #32972's version.

## 2026-11-06: the reset at rest flown, SFD-O4 log78

SFD-O4 log78 (flown 2026-11-05 indoors), beta topup11 `52ec3c77`: four hops
in ALT_HOLD, each a full-rate descent to the floor (1.1-1.9 m/s, 6.5-7.7 g),
disarm, re-arm 2.4-3.1 s later. The first flights of the reset at rest:
after hops 2 and 4 the main filters still carried 0.99-1.01 and 0.50-0.52
m/s of descent on the floor, and "EKF3 IMUn vertical velocity reset at
rest" took `XKF1.VD` to 0.00 about 0.1 s after the disarm, on both cores
after hop 2 and on core 0 after hop 4 (core 1 read 0.36 m/s there, under the
0.5 m/s threshold, and was left). No "height error" refusal on any re-arm.
Beta copies: `992bb00935` + `467782a96c` (the PR's `3888b0f7d9`),
`4795b33bc8` (`85855176cd`), `742952b71f` (`1237f11460`).

Replay with `4795b33bc8` (the wait for the fusion horizon) reverted,
against the as-flown Replay, tier 1b:

| | as flown | without the wait |
|---|---|---|
| resets at rest | the same three | the same three |
| VD zeroed by the 10 Hz XKF1 sample at | 64.27 s / 93.87 s | 64.17 s / 93.77 s |
| baro around the reset, hop 2 / hop 4 (inferred from the timing) | settled (-0.27 / -0.19 to +0.12 m) | touchdown spike (-0.58 to -1.23 / -0.68 m) |
| core 0 height at the next arm, hop 2 | PD +0.72 m | +0.81 m |
| core 0 height 2 s after hop 4's reset | PD +1.74 m | +2.13 m |
| max abs(VD) in the 2 s after each reset | 0.02-0.07 m/s | 0.02-0.06 m/s |

So the wait has flown and acted, in a different way from the one its
commit message describes: without it the velocity did not rebuild (no
second reset was needed either way), but, judging by the baro timing,
ResetHeight() took a sample still depressed by the touchdown, and the
height on the ground ended 0.1 m
(hop 2) and 0.4 m (hop 4) further from the floor. (Both builds read 0.7-2.2
m off the floor on the ground there: the range finder was out of range low
and the baro drifted.)

Not run: the clip (`1237f11460`), as no height sample was rejected
(`XKF4.SH` at most 0.33 armed and 0.08 disarmed on log78, 0.17 on log73);
the gyro bias, step average and EKF-own-reset commits, as there was no
forced EKF reset. The static yaw commits were not checked by Replay: the O4
fuses its compass at rest, so they are probably idle there.

Squash decision: `squash-audit-2026-10-31/O4-2026-11-05.md`.

## 2026-11-07: three arms outdoors at the head, SFD-O4 logs 84-86 (tier 1)

The SFD beta (refresh13 topup1, build reporting `ea9c6ab5`) carries this
PR at the head `94f24cdd9c`. Three flights outdoors on GPS, one arm each:
log84 (3408138/693) armed 3.3 min after power-on, log85 (695) after 5.8
min, log86 (697) after 33 s. XKF1.VD just before each arm read 0.00-0.01
m/s on both cores. No "height error" refusal, and no "vertical velocity
reset at rest" or forced reset after any of the three landings (land
complete to disarm 0.9-2.0 s). None re-armed after a landing without a
reboot, so these flights do not cover the re-arm; log78 above is the
last flight that did.

Logs 87-88 (2026-11-07, same build, SFD-O4 3408138/699 and /701): XKF1.VD
-0.01 to 0.00 m/s at each arm, no refusal, no reset at rest after either
landing. No re-arm after a landing.
