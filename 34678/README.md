# PR #34678 - Copter: avoid an internal error when righting a flipped copter in Stabilize

[ArduPilot/ardupilot#34678](https://github.com/ArduPilot/ardupilot/pull/34678),
branch `andyp1per/pr-land-detector-takeoff`, opened 2026-10-07 at
`5d1f4be729` on master `3b52469e50`. Two commits: `8c2c964953` (Copter,
`ArduCopter/land_detector.cpp`) and `5d1f4be729` (autotest,
`StabilizeInvertedLanded`).

## Origin

Operator report, 2026-10-07: a pilot flipped a copter, tried to right it
while inverted without turtle mode, and from then on had an internal error
at line 66 until reboot. The vehicle runs the rate thread
(`FSTRATE_ENABLE=1`). No log has been received, so the flight mode at the
time is not known; that decides which of the two paths below it was.
Found on the SmallFastDrone 4.7 branch, but the code involved is identical
on master.

## What it does

Line 66 is `INTERNAL_ERROR(flow_of_control)` in the land detector's landed
branch: throttle output above half hover, full spool, `land_complete` still
set, and the mode not taking off. Internal errors latch in a bitmask nothing
clears, so the pre-arm check fails until reboot.

Path 1, Stabilize or Drift, inverted (reproduced in SITL, below). Angle
boost multiplies the throttle by `inverted_factor`, which is 0 past 90
degrees of tilt, so the mixer sees zero collective and sets
`limit.throttle_lower`. Stabilize and Drift clear `land_complete` only when
`!limit.throttle_lower`, so they never do. `set_throttle_avg_max()` is fed
the un-boosted pilot throttle, and with the attitude controller saturated
trying to roll 180 degrees the mixer raises `throttle_out` to
`throttle_thrust_best_rpy`, up to that average maximum. Once that passes
hover/2 the land detector fires. Acro is immune: it calls
`set_throttle_out(..., false, ...)`, so its throttle reaches the mixer.
The AltHold family, Auto and Guided take-off are covered by
`is_taking_off()`, Guided attitude control and Throw clear the flag
themselves, Turtle bypasses the mixer, and System ID cannot be entered
landed. Derived from the source, not measured, for every mode except
Stabilize.

Path 2, rate thread (derived from the source, not measured). With
`FSTRATE_ENABLE` the motors are output from the rate thread, so an output
can land between `update_flight_mode` and
`update_land_and_crash_detectors`. In airmode a copter sits at full spool
on the ground with zero stick; a throttle step from exactly zero to above
about half hover in one RC frame lets the detector see the new
`throttle_out` before the mode has seen the cleared `throttle_lower`. Any
manual mode, upright or inverted.

The fix: the land detector ignores throttle output while
`limit.throttle_lower` is set (the take-off test Stabilize, Acro and Drift
already use), and only acts on a missed take-off that is still there on the
next main loop (`takeoff_missed_count`, reset in `set_land_complete()`).

## Evidence

All SITL, master `3b52469e50` against the branch, 2026-10-07. The test
turns the copter over in the air (Acro roll, force disarm, force re-arm in
Stabilize) because SITL's ground model levels a landed copter
(`SIM_Aircraft.cpp` GROUND_BEHAVIOR_NO_MOVEMENT). Any disarm leaves Copter
believing it has landed.

| Run | Test at | Firmware | Roll when throttle rises | Result |
|---|---|---|---|---|
| v1 | `31fca549a3` | master | -130 deg | FAIL: `Internal Errors 0x100000`, SYS_STATUS errors_count2=16, errors_count4=1 |
| v1 | `31fca549a3` | `edc7708020` | -123 deg | PASS, errors_count4=0 |
| v2 | `5d1f4be729` | master | 168.26 deg | FAIL: `Internal Errors 0x100000`, errors_count2=16, errors_count4=1 |
| v2 | `5d1f4be729` | `8c2c964953` | 168.28 deg | PASS, errors_count4=0, IN_AIR reached |

0x100000 is the `flow_of_control` bit; errors_count2 is the upper 16 bits
of the mask and errors_count4 the count. In both failing runs the error
fires the moment the motors reach full spool, while the copter is still
inverted, and the copter then rights itself.

v1 rolled at the default 360 deg/s and overshot to 230 to 237 deg (-130
to -123) after the stick was centred, about 35 deg short of the copter no
longer being inverted. v2 sets `ACRO_RP_RATE=90` and asserts
`wait_roll(180, 45)` just before the throttle rises; it now stops 8 deg
past the point the stick is centred (160.6 to 168.3). The v1 rows are a
different test, not a correction of v2.

Path 2 probe (`data/race-probe-2026-10-07/`): firmware `edc7708020` with
the one-loop grace removed (`takeoff_missed_count > 0`),
`FSTRATE_ENABLE=1`, `ACRO_OPTIONS=1` (airmode), 40 throttle steps from
1000 to 1900 us on the ground in Acro. The rate thread ran at 500 to
1000 Hz (2402 RTDT records, "Rate CPU" messages). 34 of the 40 steps took
the copter out of the landed state through Acro's own test (34
NOT_LANDED events). Zero internal errors. SITL does not interleave the two
threads the way a single-core ChibiOS board can, so this neither shows the
race nor rules it out. The grace counter is unmeasured.

Builds: SITL copter and heli clean (heli carries the counter in
`set_land_complete()` only, no warning); flake8 clean.

Replay cannot settle this: it is a vehicle-code fix, and the DAL re-feeds
the flags the flight recorded.

## Behaviour changes

Derived from the source, not measured.

- A copter being righted in Stabilize or Drift now stays landed until it is
  upright. `crash_check()` returns early when landed, so it no longer
  disarms a copter still on its back after 2 s of throttle. On master that
  happened only because the internal error path cleared `land_complete`.
  Acro never runs the crash check.
- `should_disarm_on_failsafe()` disarms a landed Stabilize copter, so a
  radio or battery failsafe during the flip now disarms instead of starting
  RTL or Land.
- `landed_gain_reduction()` stays on during the flip; no effect unless
  `ATC_LAND_*_MULT` is below 1. Throttle mix stays at minimum, but the mixer
  ceiling still follows the pilot's raw throttle.
- Every mode's missed-take-off backstop clear now happens one main loop
  (2.5 ms at 400 Hz) later.

## Alternatives not taken

Derived from the source, not measured.

| Alternative | Argument for | Why not |
|---|---|---|
| Compare throttle demand, as before `4b20a2d5f1` | Demand is zero when inverted, so it also avoids the error | Changes what the check measures in every mode; the `throttle_lower` term changes it only when demand is zero |
| Clear `land_complete` in Stabilize on raw pilot throttle | Fixes it at the mode level the error message blames | Marks a copter on its back as flying and raises the throttle mix during the flip |
| Do the mixer's "add lower limit flag" todo (`AP_MotorsMatrix.cpp`) | The headroom throttle is the mixer's doing | Inverted demand already sets `throttle_lower`; changes the altitude controller's anti-windup in every flight |
| Drop the one-loop grace (pre-submission review) | It has no test and SITL cannot show the race | Kept by decision 2026-10-07, disclosed in the PR as derived from the source |

## Review findings answered

Pre-submission `/pr-review` 2026-10-07 at `31fca549a3`: three Claude
reviewers (per commit, whole diff) and three Codex cold reads. Verdict
COMMENT. Fixes autosquashed into `8c2c964953` and `5d1f4be729`.

- Test never checked the copter was inverted when the throttle rose (Claude
  autotest, Claude whole-diff, Codex cold) - taken, v2 above.
- Commit message omitted the crash-check change, said "as the modes do"
  where only the manual modes use that test, and called the grace a delay
  of the report when it also delays the clear (Claude) - taken.
- Comment conflated demand with output; `throttle_high` renamed
  `takeoff_missed` (Claude) - taken.
- Grace counter unexercised (Claude whole-diff) - probe run, kept, see
  Evidence.
- A count of 1 survives a disarm and skips the grace on the next arm
  (Claude whole-diff) - rejected: after arming the spool passes through
  SHUT_DOWN, GROUND_IDLE and SPOOLING_UP, where the condition is false and
  the ternary resets the count (derived from the source). Same reason the
  optional reset in the `!motors->armed()` branch was not added.
- Heli build warning for the unread counter (Claude) - `./waf heli` clean.
- Noted, not changed: the bicopter tailsitter mixer sets `throttle_lower`
  at positive collective when roll saturates, so the backstop waits for
  roll to desaturate there, as Stabilize already does; a Lua script holding
  the external `throttle_lower` limit masks the check; debug SITL builds
  panic on the internal error rather than failing the SYS_STATUS check.
- Codex cold reads of the Copter commit and the whole diff: no findings.

## Owed

- The pilot's log: Stabilize or Drift means path 1, Acro means path 2.
- Hardware test of the fix; any hardware evidence for path 2.
- Drift is covered by the same code but not tested.

## Reproduce

On the PR branch (test passes):

    ./waf configure --board sitl && ./waf copter
    Tools/autotest/autotest.py test.Copter.StabilizeInvertedLanded

Against master (test fails with errors_count4=1): build `3b52469e50` in a
scratch worktree, copy its `build/sitl/bin/arducopter` over the branch's,
and run the same command from the branch checkout. The recipe is
"Before/after A/B runs" in the ArduPilot `Tools/autotest/CLAUDE.md`.

Path 2 probe: see `data/race-probe-2026-10-07/harness.py`.

## Files

- `data/ab-2026-10-07/v1-master.txt`, `v1-fix.txt`, `v2-master.txt`,
  `v2-fix.txt` - autotest transcripts for the table above, with local
  paths rewritten to relative ones.
- `data/race-probe-2026-10-07/harness.py` - the throwaway probe method.
- `data/race-probe-2026-10-07/transcript.txt` - its run.

## 2026-10-08: in the SFD 4.7 build (topup11)

Added to the SFD beta on top of 4.7.2-beta1. `StabilizeInvertedLanded` passes
there with the fix, and with `8c2c964953` reverted it fails with "Internal
Errors 0x100000" and `errors_count4` 1, the same as on master. The 4.7 test
harness has no `context_set_speedup()`, so the SFD copy sets `self.speedup`
and `SIM_SPEEDUP` by hand (SFD commit `5fa489a2a5`). It is on the SFD flight
card as an optional ground check: arm on its back in Stabilize and roll
upright, with no internal error and a re-arm without a reboot.
