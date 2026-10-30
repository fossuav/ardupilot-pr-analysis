# AP_OSD: show the status of each EKF3 core

**Open as [#34543](https://github.com/ArduPilot/ardupilot/pull/34543)**
from `andyp1per/pr-osd-ekf-lanes`. Head `be2961c02b`, pushed 2026-10-05
21:05.
Record started 2026-10-05; nothing was kept here before that.

`OSDn_EKF0` to `EKF2` show one EKF3 core each: `C<n>`, a marker if it is
the core flying the vehicle, its horizontal position type, and for a core
using optical flow a forward and a sideways arrow for the flow axes it
fused in the last 500 ms, or the reason neither is fusing.

#34630 is stacked on this PR and on #33484; see
[34630](../34630/README.md) for how the stack is built.

## Flown 2026-10-05

Operator report (tier 1, no log named): "pretty good but some changes
required". The changes, pushed as `c01690e19d` + `b0ab43489e`:

| flown | now | why |
|---|---|---|
| `NON` | `---`, line flashing | the flash already says there is no fix |
| `/` past the flow tilt limit | up and down pitch arrows alternating every 500 ms | |
| `>` on the flying core | `SYM_ARROW_RIGHT` | |
| sideways flow arrow `SYM_ARROW_RIGHT` | `SYM_ROLLR` | the plain arrow did not match the `SYM_PTCHUP` beside it; `SYM_ROLLR` is its pair in the ArduPilot and INAV fonts |

In the Betaflight symbol table `SYM_ROLLR` and `SYM_ARROW_RIGHT` are both
0x64, so the last change does nothing there, and the marker and the
sideways arrow are the same glyph (different columns).

Second operator report the same day: liked the changes, then asked for the
marker to be the same right arrow as the sideways flow arrow, and for tilt
to step left, up, right with a 1 s cycle. Done in `88f8672b48` +
`9f44a7b3be` (marker `SYM_ROLLR`, test expects 0xEA) and an `amend!` taking
the step from 500 to 333 ms, autosquashed and pushed as `d69703eeb5` +
`be2961c02b`. The `>`
and up/down rows in the table above are superseded by these.

The PR description still describes the flown display and needs updating.

## The timer rename (`7c149439c1`)

#33484 adds a per-axis flow timer with the same name this PR used,
`flowFuseTimeAxis_ms`, and also stamps it when relative aiding starts and
after a velocity reset, as its lockout baseline. Sharing it makes the lane
report both axes fused for 500 ms with nothing fusing (about every 5 s
while flow is rejected), and whichever PR merged second would fail to build
on a duplicate member. This PR's timer is now `flowPassTimeAxis_ms`,
written only where an axis passes its innovation check. `OSDEKFLanes`
passes at `7c149439c1`.

## Open review findings (2026-10-05)

From the whole-diff read of the #34630 stack; this PR's, not #34630's.
Inspection only (tier 3), none measured:

- Plane and Rover: `get_ekf_lane_status()` returns false unless the
  active EKF type is EKF3, and for FIXED_WING and GROUND vehicles AHRS
  falls back to DCM in AID_NONE or when GPS has a fix the EKF is not using.
  The items vanish at the moment a lane fails. Copter is not affected
  (`always_use_EKF`). Suggested: gate on the configured EKF type and
  `ekf3.started`.
- `draw_ekf_lane()` reads per-core EKF state from the OSD thread without
  `ahrs.get_semaphore()`, which the other estimator items take. No crash
  path found; torn reads only.
- `REJ` is shown for any recent upright sample that did not fuse, not only
  innovation failures: a sample still waiting for the fusion horizon, one
  over `EK3_FLOW_MAX`, a badly conditioned innovation variance (Codex).
- With `EK3_FEATURE_OPTFLOW_FUSION=0`, `flow_configured` is false even
  when the source set asks for flow (Codex).
- The #33484 low-quality latch has no reason of its own on the OSD.

## 2026-10-08: squashed after flight test

Head be2961c02b -> 3d3a382b3f, 12 -> 7 commits on the same base, content identical
(empty diff against the pre-squash head); every commit builds on its own. Follow-ups folded into their AHRS, NavEKF3 and OSD commits; tests folded.

- e3a4eca0e9 AP_AHRS: report the primary core index with the estimates
- 467deaeef4 AP_NavEKF: add a per-lane status structure
- 8f2e289008 AP_NavEKF3: report the status of each lane
- ba75cc42b3 AP_AHRS: pass out the status of each EKF3 lane
- a7c2c673b6 AP_OSD: map the symbols after SYM_LQ for MSP DisplayPort
- 3dfe60f0bb AP_OSD: show the status of each EKF lane
- 3d3a382b3f autotest: check the OSD EKF lane items

## 2026-10-16: Peter's AHRS objection, the flow signal strength

peterbarker on #34630 (2026-10-06, on the `EKF0_EN` parameter text, so
about this PR's items): "Our abstraction is AHRS. Just looking through
that abstraction layer into the EKF isn't really appropriate." An
AHRS-only rework (one item from `get_filter_status_for_configured_backend()`
and a flow quality item from AP_OpticalFlow, no AHRS or EKF changes,
+264 bytes on MatekF405) was built and tested on local branch
`osd-postype-ahrs` and set aside: the user wants the per-core data when
running one source set per core (`EK3_SRC_OPTIONS` bit 3), which the
active estimate cannot give. Replied on #34630
(https://github.com/ArduPilot/ardupilot/pull/34630#discussion_r4299809682)
with that case and the precedent of `set_posvelyaw_source_set()` /
`get_posvelyaw_source_set()`, which already pass straight to EKF3,
offering to put the interface in source-set terms. The user's position
went into aap RULES_PROPOSED as ARCH-3a.

Pushed `3d3a382b3f` -> `023c651ac8` (fast-forward, unflown):

- `1a6a4aa58e` the lane items take the AHRS semaphore (open finding from
  2026-10-05).
- `c9fa328041` a flow core shows the flow sensor's signal strength after
  `SYM_RSSI`, 0-99 from quality 0-255, before the axis arrows, `--`
  flashing with no flow data. The user chose RSSI style over a battery
  glyph gauge, ASCII bars or new glyphs: no font (analog, HD WS/WTFOS,
  and by their codepoint map SneakyFPV's) has graded signal bars, and
  the 256-glyph map has no room for a series.
- `023c651ac8` `OSDEKFLanes` checks the gauge, `--` and the shifted
  arrows. Passes; the log shows `C1 REL\x0120` then the arrows (SITL
  flow quality 51).

Description rewritten to the flown display plus the gauge, with the
per-core source set case. Scaling from `EK3_FLOW_QMIN` (QMIN at 50,
flashing below) needs #33484 and belongs on #34630.

## 2026-10-30: the lanes no longer blank on a DCM fallback

The AP-Review bot (head `17f017fb8c`, COMMENT) still had one should-fix
open: the DCM fallback found in the 2026-10-05 whole-diff read.
`get_ekf_lane_status()` answered only while EKF3 was the active estimator.
For FIXED_WING and GROUND vehicles, AHRS drops to DCM when the EKF stops
fusing GPS while the GPS still has a 3D fix, and on Rover that only happens
with `AHRS_OPTIONS` changed from 3. That is exactly when a GPS lane reads
CST, and every lane item went blank instead. Copter cannot reach it
(`always_use_EKF`). Confirmed on the PR head before the fix (below).

Local, unpushed, on `r1030/34543` (worktree `r1030-34543`):

- `a2f1de5edd` AP_AHRS: keep the EKF3 lane status while DCM is active.
  The gate is now `configured_ekf_type() == EKFType::THREE &&
  ekf3.started`, inside AHRS, so the OSD still goes through AHRS (ARCH-3).
  The cores keep running under DCM (AP_AHRS::update() updates every
  backend). DCM's estimates carry `primary_core_index = -1`, so no lane is
  marked while it flies the vehicle. `draw_ekf_lane()` is the only reader.
- `003ef442a9` autotest: `test.Rover.OSDEKFLanesDCMFallback`, plus the
  MSP DisplayPort helpers moved from arducopter.py to
  vehicle_test_suite.py. It arms a Rover with `AHRS_OPTIONS` 0, sets
  `SIM_GPS1_GLTCH_X` 0.001 (about 111 m), waits for "AHRS: DCM active",
  then needs lane 0 to read `C0 CST`, flashing and unmarked, before any
  "AHRS: EKF3 active".

A/B, sim time from the .BIN, with the glitch at 46.3 s. DCM goes active at
50.26 s, which is the 4 s `using_gps` timeout. With the glitch left on,
EKF3 takes over again at 56.48 s, once the lanes reset to the glitched fix
(`posRetryTimeUseVel_ms`, 10 s), so the window is 6.2 s. On the PR head
(ardurover md5 b4bf8835) the row is blank all through it and then reads
`C0>ABS`: FAIL 2/2 ("OSD row 9 never showed C0 CST"), one run with an
earlier two-lane draft of the test. With the fix (d9f959a1) the row reads
`C0 CST`, flashing, at 52.66 s, 2.4 s into the window: PASS 3/3, and once
more at the committed head. test.Copter.OSDEKFLanes passes with the fix
and the moved helpers. SITL copter, plane and rover build.
`pr_review.py checks` raises only the squashed-subject bodies, and the
branch checker passes all 12 commits.

The bot's commit-message point was not applied. Corrected messages for
d9e4277412, 92767a6d63 and cbda421ea8 (the gate flags cbda421ea8 too), and
for 09f2c62741's last sentence once the fix folds in, are drafted for the
next squash. The compile-time option, the 766-character `EKFn_EN`
descriptions and the QUAL/TILT/REJ/DRK test gaps are left open.

Quick-review follow-up, `af50a66828` autotest: have the OSD lane flash
check see the text come back. The cold read cleared `a2f1de5edd` but
found the flash check weak: with `flashing=True`, `wait_osd_ekf_lane()`
took any 2 s sample holding one screen with the text and one without, so
the ABS screens before CST counted as the flash-off. It now counts only
the screens from the first match on, carries them across samples, and
needs the text to go and come back. On synthetic screens the old helper
passes "ABS then steady CST" and "CST then gone for good"; the new one
fails both and still passes a real flash. OSDEKFLanes passes with it;
the Rover test passes 3/3 on the fix (CST seen flashing 3.3 s into the
6.2 s DCM window) and fails on the PR head ("never showed C0 CST
flashing").

Pushed 2026-10-30 to andyp1per with a lease on the old head: `17f017fb8c`
-> `af50a66828`.
