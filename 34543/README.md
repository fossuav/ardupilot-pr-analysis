# AP_OSD: show the status of each EKF3 core

**Open as [#34543](https://github.com/ArduPilot/ardupilot/pull/34543)**
from `andyp1per/pr-osd-ekf-lanes`. Head `7c149439c1`, pushed 2026-10-05.
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
