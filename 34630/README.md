# EKF3/OSD: show flow lockout resets on the OSD, make their messages optional

**Open as [#34630](https://github.com/ArduPilot/ardupilot/pull/34630)**,
opened 2026-10-05 from `andyp1per/pr-osd-ekf-lanes-flow-reset` at
`b993d77c7a`. Head `749bf16701` (pushed 2026-10-05 21:05). Record written
2026-10-05.

Head history the same day: `b993d77c7a` -> `6ed939c51b` (12:59, the
option moved from bit 4 to bit 6 in code, docs, commit message and test,
and the test subject shortened; the four commits from the option onwards
renumbered `2b49d7b3af`, `948e72ad06`, `ca6c02dfa3`, `6ed939c51b`) ->
`749bf16701` (21:05, fast-forward: #34543's second round of display
changes carried across as `89955625d3` + `749bf16701`). Commit hashes in
the sections below are as of `b993d77c7a` unless named otherwise; the
code they describe is unchanged apart from the bit number.

## Stacking

GitHub shows the PR based on master, but it is stacked on two open PRs and
carries their commits (24 in all; only the last eight are its own):

| base PR | branch | head stacked on | record |
|---|---|---|---|
| #33484 single-axis flow lockout recovery | `pr-vel-flow-axis-gate` | `669172801f` | [33484](../33484/) |
| #34543 OSD item per EKF3 lane | `pr-osd-ekf-lanes` | `7c149439c1` | [34543](../34543/) |

Built by checking out `origin/pr-vel-flow-axis-gate` and cherry-picking the
#34543 commits on top, then the eight commits of this PR. Use origin's
#33484 branch, not a local one: on 2026-10-05 the local
`pr-vel-flow-axis-gate` was the unsquashed 15-commit series at `853f3f2177`
while the PR head was the squashed 7 commits plus one.

Two conflicts come up every time the stack is rebuilt, both from the two
PRs each adding a per-axis flow timer:

- #34543's cherry-pick of "AP_NavEKF3: report the status of each lane"
  conflicts with #33484 over `flowFuseTimeAxis_ms`.
- Since `7c149439c1` #34543 calls its own timer `flowPassTimeAxis_ms`.
  Resolve by keeping #33484's `flowFuseTimeAxis_ms` exactly as #33484 has
  it (under `EK3_FEATURE_OPTFLOW_AGL_KF`, also stamped at relative-aiding
  entry and after a reset) and adding `flowPassTimeAxis_ms` beside it,
  written only where an axis passes its innovation check. Check with
  `git diff origin/pr-vel-flow-axis-gate -- libraries/AP_NavEKF3`: only
  lane-status additions should differ.

When either base PR merges, rebase onto master and drop its commits.

## What it does

At `b993d77c7a`, eight commits:

- `108698fe4c` AP_NavEKF, `25a994f29f` AP_NavEKF3: the lane status gains
  `flow_x_reset` / `flow_y_reset`, set after a velocity reset that
  recovered that axis from a lone lockout. The axis is the more stale of the
  two at the reset (`axisLockout` guarantees one stale, one fresh).
- `1527cf8116` AP_OSD: that axis's arrow is not drawn while the flag is set.
- `6eeb42eb08` AP_NavEKF3: the rename above.
- `2b49d7b3af` AP_NavEKF3: `EK3_OPTIONS` bit 6 (`QuietFlowVelResets`)
  stops the per-reset "flow vel reset N (axis lockout)" statustext. Default
  off, so the messages stay on. The pause, deferral and low-quality messages
  are not affected.
- `fb4c8fbfee` AP_NavEKF, `2aecc0febb` AP_NavEKF3: the reset flag is held
  for 250 ms, not 500 ms.
- `b993d77c7a` autotest: a subtest of `EK3_FlowAxisLockoutRecovery`.

## Decisions and why

### The reset statustext is optional, not removed

The operator asked on 2026-10-05 for the messages to be muted, as the OSD
now shows each reset. A mute was written (`9b33a81fc8`, with an autotest
moved to `XKF7.FVC`), reviewed and dropped before the PR opened, because it
contradicts a tier-1 finding: [33484](../33484/README.md) "Proposed fix 2"
made the message per-reset after flight log7, where `XKF7.FVC` reached 3
but only two messages appeared and the missing one was the reset that
mattered. The mute also lost the `MSG` log record, every GCS without the
OSD item (off by default), and the Replay sweep's count, which reads
statustexts because XKF7's format record is lost to a reader desync in the
33484 logs. The operator then chose an option bit instead.

Consequence for the Replay sweep: with bit 6 set, its `'flow vel reset'`
needle matches only "flow vel resets paused", one per burst. Replay with
bit 6 clear.

### 250 ms, not 500 ms

An axis still failing after a reset locks out again 500 ms later
(`FLOW_AXIS_LOCKOUT_MS`) and is reset about one flow sample after that.
With a 500 ms flag the arrow stayed dark through a whole run of resets
(up to five, about 2.5 s, before the pause). 250 ms leaves it lit between
resets. *Derived from the source, not measured on an OSD.* The OSD redraws
at 10 Hz, so 250 ms is two or three frames dark.

## Evidence

SITL only (tier 2), at the heads named:

- `EK3_FlowAxisLockoutRecovery` and `OSDEKFLanes` pass at `c24fa3e925`,
  the pre-squash tip with the same tree as `b993d77c7a`.
- The new subtest sets `EK3_OPTIONS` 8|64, provokes a lockout with
  `SIM_FLOW_OFS_X`, waits for core 0's `XKF7.FVC` to count a reset, and
  checks no "(axis lockout)" statustext arrived. It **fails** with the
  option check replaced by `if (true)`: "flow vel reset announced with the
  quiet option set".
- Built with `EK3_FEATURE_OPTFLOW_AGL_KF=0` and with
  `EK3_FEATURE_OPTFLOW_FUSION=0` (binary checked for the AGL-KF-only
  "flow recovery deferred" string: absent).
- Repeated-lockout reset times at `29e8456bf5`: 35.2 39.0 43.2 47.1 51.2
  56.2 59.2 63.0 67.1 71.1 83.1 87.1 91.0 95.0 99.6 s (5 s then 12 s
  pauses, against minimums of 5 and 10).

Not flown. The OSD display changes from 2026-10-05 (arrow marker, `---`,
alternating tilt arrows) were flown on #34543; the reset flash and the
option have not been.

## Review findings (2026-10-05, /pr-review: four Claude readers, Codex)

Fixed before opening:

- Mute contradicts the 33484 record - reverted, option bit instead.
- Both axes shown fused for 500 ms on relative-aiding entry and after a
  reset, with nothing fusing (Claude whole-diff and Codex, independently).
  Caused by the first stack resolution sharing #33484's timer. Fixed by the
  rename. Also removed the duplicate-member build break whichever base PR
  merged second.
- Back-to-back resets read as one long blackout - 250 ms.
- Codex on the fix round: the quiet check matched "flow vel resets paused",
  which the option deliberately keeps - now matches "(axis lockout)".

Dropped with the mute: the gate-off check made vacuous (XKF7 is only
written with `AglKfForOptflow` set), and the reset waits not filtering
XKF7 by core.

Accepted as open:

- No test reads the flash off the OSD. `OSDEKFLanes` runs on the ground
  and a reset needs `takeOffDetected` and AID_RELATIVE.
- `flowPassTimeAxis_ms` comment "written nowhere else" ignores its init;
  wording only.

## Replay

No estimator change: the lane status is output-only and the option gates
a statustext. Nothing to replay; recorded in [REPLAY_LOGS.md](../REPLAY_LOGS.md).
