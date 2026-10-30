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

## 2026-10-16: rebuilt on the current bases, the quality floor added

Pushed `749bf16701` -> `b081354744` (forced). The stack is rebuilt on
#33484 at `edb0cc387e` (the D gate and the latch store ordering) and
#34543 at `023c651ac8` (squashed, plus the AHRS semaphore and the RSSI
style flow signal strength): the ten #34543 commits cherry-picked, then
seven of this PR's eight. Resolutions:

- "AP_NavEKF3: report the status of each lane": #33484's
  `flowFuseTimeAxis_ms` block kept as #33484 has it, #34543's
  `flowPassTimeAxis_ms` added beside it.
- `25a994f29f`: the reset-axis stamp added under #33484's
  `otherAxisPassed` gate; the lane status reads `flowPassTimeAxis_ms`.
- `1527cf8116`: #34543's parameter text, with "going out once when a
  velocity reset recovers it" added.
- `6eeb42eb08` (the timer rename) skipped: the first resolution already
  makes that split.
- `89955625d3`, `749bf16701` not carried: #34543's squash holds them.

Checked against the old head: AP_NavEKF3 differs only by #33484's own
changes since `669172801f`; AP_AHRS, AP_NavEKF and AP_OSD only by
master's and the two new #34543 commits.

New here, unflown: `0fea569c8b` (AP_NavEKF) and `935a53cde6`
(AP_NavEKF3) put `EK3_FLOW_QMIN` in the lane status; `8fafff1900`
(AP_OSD) shows it as 50 on the signal strength, flashing below it, 0-99
over 0-255 with no floor; `b081354744` an `OSDEKFLanes` subtest. Why 50:
on TD25 indoors `OF.Qual` sat at median 58 against QMIN 60, which a
scale from QMIN to 255 would show as 0-3.

`OSDEKFLanes` passes (QMIN 51 a steady `50`, 102 `25` flashing, 0 back
to `20`, SITL quality 51); `EK3_FlowAxisLockoutRecovery` passes, all ten
subtests including the quiet option and "Both axes wrong". Title now
"AP_NavEKF3: show flow resets and the quality floor on the OSD, make
reset messages optional"; description updated.

## 2026-10-30: the quiet option and the reset flag flown; rebuilt on #33484's squash

Three lockout resets counted in `XKF7.FVC` with `EK3_OPTIONS` bit 6 set and
no "(axis lockout)" message: SFD-O4 log57 core 1 at 941.4 s (`6d754361`) and
the T25 runaway at 122.4 and 124.0 s (`308a7e73`). Both vehicles fly an MSP
DisplayPort OSD (`OSD_TYPE` 5) with the lane items on (`OSD1_EKF0_EN`, and
`OSD1_EKF1_EN` on SFD-O4), and the T25 sets `EK3_FLOW_QMIN` 60, so the lane
reset flag, the flash and the quality floor all ran; what the OSD drew is
not in the log, so the display is still unconfirmed. Nothing to squash: none
of this PR's own commits had flown, so none is a fix on a flown commit.

Rebuilt on #33484's squash: `b081354744` -> `d402ac272a`, the 21 commits
after `edb0cc387e` cherry-picked onto `e0e4a38f57`, empty diff against the
old head. #34543 has since been rebased onto newer master (`17f017fb8c`);
the copies here are left as they were. The mechanical gate reports three
older commits whose bodies carry squashed subjects (`e5ac04130f`,
`a488b89db8`, `60b8bd1d79`), unchanged by this rebuild.

## 2026-10-30: lockouts counted in flight, SFD-O4 log65

log65 (3408138/646), beta `52b1d36f`, `EK3_OPTIONS 94` (bit 6 set): three
lockout resets on core 1 (`XKF7.FVC` 0 -> 3 at 63.6, 83.2 and 132.5 s,
FVU never set) and no reset statustext, as bit 6 intends. Each reset is in
`../33484/` (2026-10-30). The OSD (`OSD_TYPE 5`, `OSD1_EKF0/1_EN`) drew
every frame; what it showed is not in the log and no pilot report was
taken.

A limit seen on log61 (3408138/639): core 1 was 13 m/s and 300 m wrong
while its status said healthy (`XKF4.SS` unchanged, SV and SP 0), so a lane
item had nothing to flag. Lane status reports what is being fused, not
whether the result is right.

## 2026-10-30: the quality floor shown only with the AGL KF option

AP-Review at `d402ac272a`, should-fix: `getLaneStatus` reported
`EK3_FLOW_QMIN` whenever the lane was configured for flow, so with
`EK3_OPTIONS` bit 3 clear the OSD rescaled the signal strength to read 50
at a floor that did nothing. Verified: the only code that acts on the floor
is the lockout block in `FuseOptFlow`, under `EK3_FEATURE_OPTFLOW_AGL_KF`
and `option_is_enabled(AglKfForOptflow)`. It is the only writer of
`flowVelResetUnhealthy`; the release run in `writeOptFlowMeas` and the two
readers in Control.cpp act only on that latch. `OSDEKFLanes` set QMIN with
`EK3_OPTIONS` 0 and passed.

Seven commits on `d402ac272a`, unflown; the first three:

- `17ead03a5e` AP_NavEKF3: the floor is copied into the lane status only
  inside the AGL KF block and with the option set; otherwise 0, which the
  OSD already treats as no floor (0-99 over 0-255, no flash), as for
  QMIN 0.
- `a7ac51780b` AP_OSD: the three `OSDn_EKFm_EN` descriptions say the
  floor needs bit 3. Documentation only.
- `057ca0f7d8` autotest: `OSDEKFLanes` first checks QMIN 51 with bit 3
  clear reads 20 on every screen for 2 s, then sets `EK3_OPTIONS` 8 for
  the existing 50 / 25-flashing / 20 checks.

A/B: head binary `d326dc50` fails the new check, 21 of 25 screens reading
`\x0150` after QMIN 51 (the first four still 20); fixed binary `767152bd`
passes, the trace reading 20, then 50 with bit 3, 25 flashing at 102 and
20 at 0. The CST and Betaflight subtests after it pass with bit 3 left
set. Built: copter, replay and `tool/AP_DAL_Standalone` as CI configures
them, and copter with `EK3_FEATURE_OPTFLOW_AGL_KF=0` and with
`EK3_FEATURE_OPTFLOW_FUSION=0`. Output-only: nothing logged or replayed
changes.

Follow-up from the quick review's cold read of `17ead03a5e`, verified:
`EK3_OPTIONS` can change in flight, and only the setting of
`flowVelResetUnhealthy` tests the option. Its release (against
`_flowQualMin`), its disarm clear and both places it blocks flow aiding do
not, so with bit 3 cleared after a latch the floor stayed in force while
the lane reported 0. `7e63c513bf` (AP_NavEKF3) also reports the floor
while the latch is set; the latch itself is untouched. `191ad8c36b`
(autotest) adds an `OSDEKFLanes` leg: take off in ALT_HOLD with QMIN 40,
quality 10 and `SIM_FLOW_OFS_X` 1, wait for lane 1's "flow quality 10 too
low", clear bit 3, raise the quality to 20 (below the floor and the 44
release) and wait for `\x0125` flashing. The quality step is a marker:
MSP is not read through the flight, so 23 s of earlier screens are queued
ahead (a first version read only those, 232 screens of 12 flashing, and
passed on both binaries). A/B: option-only binary `bc578353` fails, lane 1
reading "C1 ---" with a steady 7 for 60 s; fixed `db4019ef` passes, "C1
---" with 25 flashing, twice, and again at the committed head
(`3de3eec4`). Copter, replay and `tool/AP_DAL_Standalone` build.

Round 2 of the cold reads. `wait_osd_ekf_lane(flashing=True)` passed on
one screen with the text and one without in a 2 s sample, so the queued
pre-change screens would have let a steady 25 pass. `9a64b9bc5f` applies
#34543's `af50a66828` logic to this PR's copy in arducopter.py (screens
from the first match on, the text must go and come back); offline, the
old predicate passes queued-then-steady and the new one does not.
OSDEKFLanes passes at head (`93ef49e8`), all four flashing waits
included, and the option-only binary `bc578353` still fails the latch
leg, "never showed b'\x0125' flashing" with lane 1 a steady 7.
`6b84dcfeb9` (AP_OSD) words the descriptions for the latched case.
Not changed, noted: the latch releases at QMIN + 10%
(Measurements.cpp:185), so with quality between QMIN and that the
strength reads above 50, unflashing, while the lane stays latched. That
was so with bit 3 on before this round, and the lane reads "C1 ---"
while latched.

No change on the flown vehicles: the T25 sets QMIN 60 and logged lockout
resets, which run only with bit 3, so its display is as before. Derived
from the source, not from its parameter dump.

The minor on `ResetVelocityToFlow`'s covariance is left: the function is
#33484's (`020cdcdced`), not this PR's. Doing it properly means a 2x24
Jacobian of the solved N/E velocity in the quaternion and vel-D states,
setting `P[4..5][k] = J P[:,k]` and `P[4..5][4..5] = J P J^T + R`, then a
SITL A/B and a replay; at least the yaw term would add `vE^2`, `vN^2` and
`-vN vE` times the yaw variance.

The PR description is stale on the floor, the commit count and the
`OSDEKFLanes` sentence; a draft update is in the scratch dir.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `d402ac272a`
-> `9a64b9bc5f`.
