# #30841 Control ESC Logging

### 2026-11-06: AP-Review blockers fixed, squashed as `9816840ba6` on `26c7363f64` (`r1106/30841-squash`, not pushed)

AP-Review (2026-09-30, head `ad6e3bdcfd`) blocked on Rover, Sub, Blimp and
Tracker logging no ESC, and on Copter's Motors-bit gate, which dropped ESC
at LOG_BITMASK 65535 and broke DynamicRpmNotches; both notch tests
reproduced failing at the head (ZeroDivisionError, no ESC records).

Fixed with peterbarker's design: AP_ESC_Telem's 100 Hz update() logs ESC,
ESCX and EDT2 at a new ESC_TLM_LOG_RATE (index 2, Hz, 0 off, default 100,
the rate logged today), the vehicle calls are gone, loop-rate ESC logging
with the fast-notch bits is dropped, and there is no new log bit, since a
new bit would stop ESC logging for every stored mask without it. The net
change against master is AP_ESC_Telem alone, +37/-2. At a 25 Hz default
DataFlashErase failed (763 KB against its 1000 KB floor), so 25 would change
users' logs. The rate limiter steps by the interval and stays at most one
behind: 100.0 Hz under scheduling jitter, where resyncing to now gave 94.
Rates 100/25/10/0 logged 100.0/24.0/9.9/0 Hz.

At the branch DynamicRpmNotches, DynamicRpmNotchesRateThread and
DataFlashErase pass; Copter at LOG_BITMASK 65535 logs 3497 ESC/ESCX where
the head logged 36 (after disarm); Rover 387 where the head logged none.
Codex cold read of the net diff and audit: no findings. The PR description
still describes vehicle control and a 25 Hz default.

Developed as six commits on the PR head (`r1106/30841-fix`,
`3f1a0b7bd2..1eb45c8eb5`); since they undid the PR's Copter and Plane
commits, the PR is squashed to the one AP_ESC_Telem commit, its tree
identical to that branch's.

Pushed 2026-11-06: `pr-esc-logging` `ad6e3bdcfd...9816840ba6` (forced, squashed). Description updated. Reply posted: https://github.com/ArduPilot/ardupilot/pull/30841#issuecomment-6690426215

### 2026-11-07: AP-Review minors fixed (`r1107/30841-fix2`, `9816840ba6..5e6288c3b1`, not pushed)

AP-Review (2026-11-06, head `9816840ba6`) raised two minors.

The first was that the parameter text claimed a 100 Hz check rate. AP_Vehicle schedules update() at 100 Hz, but the scheduler runs it every SCHED_LOOP_RATE/100 loops (integer division, at least every loop). It therefore gets at least 100 Hz on loops of 100 Hz or more (150 Hz at a 150 Hz loop, 125 Hz at 250) and every loop below that, which means 50 Hz on the fixed-wing Plane, Rover, Tracker and Blimp default. On Copter, a rate of 100 logged 50.0 Hz at SCHED_LOOP_RATE 50 and 100.1 Hz at 150 and 250. A rate of 30 logged 30.0 Hz at 150 and 250, so a task faster than the set rate still logs at the set rate. `365b5d6cd4` rewords the description and the header comment to "checked at least 100 times a second, or every main loop when SCHED_LOOP_RATE is lower than 100, in which case the most it can log is SCHED_LOOP_RATE". A first wording, "up to 100Hz", failed a cold read on the 150/125 Hz cases.

The second was that no test set the parameter. `5e6288c3b1` adds Copter ESCTelemLogRate in tests2b. It waits for SITL's ESC telemetry, which starts 6 s after boot, clears the harness's LOG_*_RATEMAX, and counts ESC per instance between the PARM records at 10/50/0 Hz. It reads 10.0/50.1/0.0 Hz and passes at speedup 100 and 2. Three mutants each fail it:
- removing the limiter (99.9 Hz at 10)
- making 0 log at full rate (100 Hz at 0)
- resyncing the limiter to now (33.4 Hz at 50)

Mechanical gate clean. The PR description's "runs at 100 Hz on every vehicle" needs the same correction.

Pushed 2026-11-07: `pr-esc-logging` `9816840ba6..5e6288c3b1`. Description updated (the rate sentence, and ESCTelemLogRate under testing). Reply posted: https://github.com/ArduPilot/ardupilot/pull/30841#issuecomment-6706615668

## 2026-11-07: flown on the SFD beta, SFD-O4 log84 (tier 1)

The SFD beta (refresh13 topup1, build reporting `ea9c6ab5`) carries this
PR at `9816840ba6`; the head `5e6288c3b1` changes only the parameter text
and adds the test. On SFD-O4 log84 (3408138/693), with `ESC_TLM_LOG_RATE`
25 from the SFD board defaults and `LOG_DISARMED` 2, ESC logged at 25.0 Hz
per motor over 245 s armed (6125 records each) and at 24.9 Hz over the
whole 468 s log, disarmed included, with the main loop at 1972-2007 Hz.

## 2026-11-07: the doc fix squashed, pushed

`365b5d6cd4` (ESC_TLM_LOG_RATE is capped by the loop rate) is comments
and parameter text only, and its target flew at 25 Hz on SFD-O4 logs
84-88. Pushed `5e6288c3b1` -> `af27953c1b` (force, 3 commits to 2, same
tree; backup `pre-squash/30841-1107`): the doc fix is folded into the
logging commit, now `8e1560997c`, whose message gains the loop-rate
paragraph and the flight rate. The ESCTelemLogRate test is `af27953c1b`.

## 2026-11-07 (evening): AP-Review at `af27953c1b`, rebased onto master, pushed

AP-Review (COMMENT) repeated two points first raised at `5e6288c3b1`,
never answered. The rebase: master's new Copter test lists conflicted
with the registration, so GitHub skipped CI. Rebased onto master
`b7c08d4dbc`; master's RateThreadPostFilterGyroLog and ESCTelemLogRate
had landed in the same place and are both kept, and ESCTelemLogRate is
registered in tests1a beside the RPM notch tests. The diff is otherwise
the same line for line. SITL copter builds clean and ESCTelemLogRate
passes (10.0, 50.0 and 0.0 Hz per ESC).

Still open, not a documentation change: the log buffer can drop ESC rows
and read a rate low. The bot suggests LOG_FILE_BUFSIZE 32767 with a
reboot, a longer drain and assert_log_has_no_dropped_blocks() (on master)
before the rate check.

Pushed 2026-11-07: `pr-esc-logging` `af27953c1b...c15a37c45d` (force,
rebase). GitHub reads it as mergeable.
