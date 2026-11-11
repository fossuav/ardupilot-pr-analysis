# PR #35119 - an in-flight SmartRTL return point reset for Lua scripts

Analysis archive for [ArduPilot/ardupilot#35119](https://github.com/ArduPilot/ardupilot/pull/35119).

Opened 2026-11-11 at `42f34760d1`, 13 commits on master `aea9a1b5d4`,
branch `pr-smartrtl-reset`. On the SFD beta as refresh14 topup5 the same
day, with one 4.7 fixup (`Tools/SFD/REFRESH_NOTES.md`).

## What it does

`AP_SmartRTL::reset_home()` clears the SmartRTL path and makes the
current position the new return point, in flight. Lua reaches it as
`smart_rtl:reset_home()`; the applet `smartrtl-reset.lua` calls it from an
RC switch or `MAV_CMD_DO_AUX_FUNCTION`. RTL and home are unchanged. The
reset is refused unless the vehicle is saving its path from a good
position, which update() is told every cycle and
request_thorough_cleanup() stops at once when a return starts.

`set_home()` now goes through the same request, which the background
cleanup thread performs under the path semaphore. Before, it reset the
path and the simplify and prune state on the calling thread while that
thread could be running (a Copter re-arm with SmartRTL still active,
Rover, DO_SET_HOME with the current location in flight).

## Review before opening (2026-11-11)

The first three commits came in as one multi-subsystem commit written
against 4.7, split one subsystem per commit. `/pr-review`, three rounds:
three Claude reviewers (one per subsystem and one on the whole diff) and
Codex cold reads, verification and an audit of every earlier finding.

| round | verdict | what it found |
|---|---|---|
| 1 | REQUEST CHANGES, 2 must-fix | a reset was accepted during a SmartRTL return, since the guard only covered the path cleanup wait (Copter then landed where it was); parameter table key 86 was already `copter-deadreckon-home.lua`'s |
| 2 | REQUEST CHANGES | the guard was still open for up to about 330 ms at the start of a return, as update() runs at 3 Hz; set_home() waited on the path semaphore on the main loop; the shared request slot could drop a home reset |
| 3 | COMMENT | the request flag was read without its semaphore; the applet counted an unseen RC switch as low, so one already high at the receiver's first frame triggered a reset |

Measured and rejected, or left as notes:

- The applet probe's back-to-back retries cannot be refused as busy at
  the head: reset_home() no longer takes the path semaphore.
- A Copter SmartRTL mode entered within about 1 ms of arming would find
  SmartRTL not yet active after set_home() moved to the background
  thread; no caller enters that soon.
- An RC aux function in the vehicle would cover the switch case only;
  the library call also lets a script choose when to reset.
- Pre-existing, unchanged: Rover never cancels a thorough cleanup when
  SmartRTL is left during the cleanup wait; init() frees `_path` without
  clearing it on an allocation failure.
- With the reset compiled out, one intermediate commit does not build:
  the binding's `depends` cannot precede the define under
  `-Werror=undef`. The default configuration builds at every commit.

## SITL (tier 2), at the opened head

| test | result |
|---|---|
| `SmartRTLResetHome` (new) | reset from the applet's switch 40 m out; SmartRTL lands 0.59-0.65 m from the reset point; a script's reset during the return is refused |
| the same with the original guard put back | fails: the probe's reset is accepted mid-return |
| `SMART_RTL`, `SMART_RTL_EnterLeave`, `GCSFailsafe`, Rover `SmartRTL` | pass |
| `SMART_RTL_Repeat` | fails, as it does on master, where it is disabled for loop detection |

Built for Copter, Rover and Plane SITL, every commit for Copter, and
Copter and Rover with `AP_SMARTRTL_RESET_ENABLED 0`. Flash at the opened
head: MatekH743 copter +736, rover +720; MatekF405 copter +688, rover
+272 (no scripting there, so only the set_home() change and the
singleton).

## Open

- Unflown. No flight log applies: the path reset is vehicle-side state
  Replay does not re-run.
- AP-Review's first round.
