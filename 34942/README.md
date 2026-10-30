# PR #34942 - EKF3: fix the on-ground height check and apply it without a vertical velocity

Analysis archive for [ArduPilot/ardupilot#34942](https://github.com/ArduPilot/ardupilot/pull/34942).
Branch `pr-ekf3-gnd-hgt-check` (andyp1per fork), base `master` at
`278a68a57a`, PR head `a1fbfbcdc7` (opened 2026-10-30, five commits). The
flight evidence is from the T25 airframe on the SFD 4.7.2 beta; numbers are
cited inline and no flight logs are committed.

> **Read this before changing the code.** "Measured and rejected" below
> lists the versions of this change that look right and measured worse,
> each with the number that settled it. Several of them were the first
> design.

## Status (one line)

Opened 2026-10-30 after four /pr-review rounds (verdict COMMENT). Replay and
SITL validated; unflown; only Copter exercised; on by default, which the PR
argues as a bug fix and a maintainer may want discussed first.

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

- The MicoAir false refusals: 9 of 27 ordinary arms, all quick re-arms
  after the EKF settles 1 to 3.5 m off the baro on landing. The 1 m
  threshold is the existing one; a 2 m threshold would, from the table,
  keep 100.58 and 62.90 s and drop most of them (not measured).
- No Plane, Rover or Sub SITL run; nothing has flown; not on the SFD beta.
- On by default (ARCH-19): a dev-call or Discourse thread may be wanted.
- Flash cost not measured.
- EKF2 is unchanged; whether its AID_NONE-only rule should follow is open.

## File map

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
