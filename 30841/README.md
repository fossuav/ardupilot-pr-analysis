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
