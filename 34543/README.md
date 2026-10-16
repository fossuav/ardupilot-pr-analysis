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
