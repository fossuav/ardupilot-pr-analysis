# PR #34583 - Throttle-gain boost and throttle mix with the fast rate thread

Analysis archive for [ArduPilot/ardupilot#34583](https://github.com/ArduPilot/ardupilot/pull/34583).
Branch `pr-rate-thread-gboost` (andyp1per fork), base `master`, head
`653221ac65` (2026-10-02, rebased onto `cafe674577`). Everything here is SITL
or inspection; the only real-flight numbers are an operator's, cited inline.

## Status (one line)

Opened 2026-10-02. Three commits: apply the throttle-gain boost once per main
loop (and restore the angle P half, dead since 4.7.0), an autotest that fails
on master, and slew the throttle mix with the rate controller's dt.
Self-reviewed with /pr-review (5 Claude + 5 Codex, then a re-review of what
moved), no must-fix outstanding. Not flown. Follow-up #34584 is stacked on it.

## Origin

Forum report by RobinIJ (ArduPilot Discourse, 2026-09-20 and 2026-10-01), 7"
quad, `ATC_THR_G_BOOST=0.4`. Max `ATSC.PDScX` per log was an exact power of 1.4
(tier 1, the operator's logs, not held here):

| Fast rate / loop rate | max ATSC.PDScX |
|---|---|
| off / 400 Hz | 1.4 |
| off / 800 Hz | 1.4 |
| 1 kHz / 400 Hz | 2.744 (1.4^3) |
| 2 kHz / 400 Hz | 14.76 (1.4^8) |
| 2 kHz / 200 Hz | 40.50 (1.4^11) |
| 4 kHz / 200 Hz | 8820 (1.4^27) |
| 4 kHz / 200 Hz | 17287 (1.4^29) |

The two largest are the flights where the problem showed. Robin reported three
issues; the user's first read was that only the boost mattered. That is right
for the gain explosion and wrong for the throttle mix (fast rate alone).

## The three defects

1. **PD boost compounds.** `update_throttle_gain_boost()` ran inside
   `rate_controller_run_dt()` and multiplied `_pd_scale` and `_angle_P_scale`
   by the boost on every call. They are reset once per main loop, so with the
   rate thread the scale reached `boost^n`, n = rate thread runs since the
   reset. The only multiplier written from the rate path; landed gain
   reduction and the acro I scale are main-loop writes and cannot compound.
2. **Angle P boost dead since 4.7.0.** `c683d8c16` (Copter-4.7.0, 4.7.1) moved
   the angle P reset into `rate_controller_target_reset()`, which Copter calls
   after `rate_controller_run()` and before `update_flight_mode()`. The boost
   was applied and wiped before the angle controller read it, with or without
   the rate thread, while ATSC (copied in the rate run) still logged it.
   `ATC_THR_G_BOOST` exists since 2022 (`53b7f96a5d`) and worked through 4.6.
3. **Throttle mix ramps too fast.** `update_throttle_rpy_mix()` stepped by
   `_dt_s`, the main loop time (the rate thread only sets `motors->set_dt_s`),
   while running at the rate thread rate.

## The fix

- PD: `get_throttle_pd_boost()` returns the multiplier; the rate controller
  applies it to a local copy of `_pd_scale` and logs that copy as
  `_pd_scale_used`.
- Angle P: a Multi override of `rate_controller_target_reset()` (made virtual
  again) multiplies in `sq(pd_boost)` after the base reset, so the angle
  controller later in the same loop sees it. Equal to the old
  `constrain((g+1)^2,1,4)` over the documented 0..1 range; differs only below
  g = -2.
- Mix: `update_throttle_rpy_mix(dt)` with the rate controller's own dt;
  `rate_controller_run()` passes `_dt_s`, so the non-thread path is identical.

## Measurements (SITL, tier 2)

Built on `877c45cd6f` unless stated. SITL gyro is 1 kHz, so runs per loop are
raised by lowering `SCHED_LOOP_RATE`.

| What | master | this PR |
|---|---|---|
| ThrottleGainBoostRateThread, max PD / angle P scale (1 kHz / 200 Hz, boost 0.4) | 10.54 / 111.1 | 1.400 / 1.960 |
| Angle P the angle controller read, no rate thread (temporary probe) | never above 1.0 | 1.96 |
| Same, rate thread | (compounding) | 1.96 |
| Throttle mix rise, 1 kHz / 200 Hz (`data/thr-mix-ab`) | 10.9/s | 1.86/s (2.0/s intended) |

- The angle P probe was a rate-limited `GCS_SEND_TEXT` of the max
  `_angle_P_scale.x` seen inside `update_ang_vel_target_from_att_error()`; it
  printed nothing on master without the rate thread and "PROBE angP 1.9600"
  with the fix in both modes. Not kept as a log.
- **ATSC cannot show defect 2.** Without the rate thread master's ATSC logged
  AngPScX 1.96 while the controller used 1.0. An ATSC assertion on the non-thread
  test passes on master; that review suggestion is refuted, do not add it.
- The rise numbers time 0.11 to 0.49 (`rise_time.py`), so they are rates, not
  "0.035 s instead of 0.2 s" as a first commit message said. The `master.BIN`
  and `fixed.BIN` are 877c45cd6f with the throttle mix fix reverted / applied
  plus a temporary `TMIX` log of `_throttle_rpy_mix` on every rate run
  (`AP::logger().Write`, not `WriteStreaming`, which rate-limits to ~50 Hz and
  cannot resolve the ramp).
- On landing the mix dropped 0.5 -> 0.1 in one step in both builds: the
  "reset immediately" clamp, so the ramp-down change mostly shows where that
  clamp does not apply. The land-detector timing effect is stated in the
  commit message but not measured.

## The autotest

`ThrottleGainBoostRateThread`: `FSTRATE_ENABLE=3`, `FSTRATE_DIV=1`,
`SCHED_LOOP_RATE=200` (about 5 rate runs per loop), five STABILIZE throttle
punches, then asserts max ATSC PD = 1.4 and angle P = 1.96 to 0.001. Exact
equality fails both ways (compounding above, no boost below). It also requires
RTDT samples with mean dt under half a main loop: with `FSTRATE_ENABLE=0` the
scales come out at exactly 1.4 / 1.96, so without that check the test passes
when the thread never runs (shown 2026-10-02; Codex cold-read finding).

Not covered by any permanent test: the non-thread angle P fix (needs the
in-controller probe), and the throttle mix (not logged anywhere).

## Review record (2026-10-02)

- Must-fix: none. Should-fix fixed by squash: commit messages (name
  `c683d8c16` / 4.7.0, the user-visible return of up to 4x angle P on punches
  and the acro I scale, narrowed QuadPlane claim, mix as rates), the stale
  comment in `get_throttle_pd_boost()`, float literals, RTDT check, redundant
  mode change in the test.
- Left open: the test takes the max over roll and pitch together, so a boost
  missing on one axis would pass. Cheap to split if asked.
- QuadPlane: `setup_rp_fw_angle_gains()` (`quadplane.cpp:4899`) *sets* the
  angle P scale above low airspeed, replacing the boost, as before 4.7. Not
  changed; would be an ArduPlane commit.
- Design question a maintainer may raise: PD decided per rate run, angle P per
  loop. Alternative is both in the reset override (one loop extra latency on
  PD); only clean on top of #34584. Answered in the PR detail section.
- A review agent claimed the stack "guarantees a textual conflict" with
  #34208; a trial merge against `a618208324` was clean. Refuted.

## Relation to other PRs

- #34584 (stacked): the rate thread can still run between the per-loop reset
  of the PD/I scales and sysid and `update_flight_mode()` rebuilding them.
- #34208: merges cleanly; independent (target vs. modifiers).

## Files

- `data/thr-mix-ab/master.BIN`, `fixed.BIN` - SITL, `TMIX` probe, 1 kHz / 200 Hz,
  takeoff then LAND.
- `data/thr-mix-ab/rise_time.py` - time from mix 0.11 to 0.49 while rising.
