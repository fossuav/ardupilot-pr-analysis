# PR #33568 - Fall back to relative aiding when optical flow replaces lost GPS (EKF3)

Analysis archive for [ArduPilot/ardupilot#33568](https://github.com/ArduPilot/ardupilot/pull/33568).
Branch `pr-flow-aiding`, head `4bb2ef3583`, base master (23 Jun 2026, four
months stale but it still merges cleanly).

## Status (one line)

Adds the missing AID_ABSOLUTE -> AID_RELATIVE edge so a GPS-booted vehicle that
later flies on flow gets the flow control limits. The 2026-09-12 automated
review's headline BUG - that the new edge teleports the NE position to the EKF
origin - **did not reproduce when measured**.

## The claimed BUG, and what the measurement says (2026-09-12)

The review's chain is real as source:

- the new edge sets `PV_AidingMode = AID_RELATIVE` (`Control.cpp:406-408`)
  without writing `lastKnownPositionNE`
- the mode-change block always calls `ResetPosition()` (`Control.cpp:510-511`)
- `ResetPosition()` with `PV_AidingMode != AID_ABSOLUTE` assigns
  `stateStruct.position.xy = lastKnownPositionNE` (`PosVelFusion.cpp:122-125`)
- `lastKnownPositionNE` is written in exactly one place, on entry to AID_NONE
  (`Control.cpp:429-430`), and zeroed at `core.cpp:243`

All four verified by reading. The predicted consequence is that a vehicle far
from the origin snaps to it at the fallback.

**It does not happen.** The PR's own test scenario, with the vehicle first flown
89 m from the origin and then switched to the flow source set:

| | |
|---|---|
| AID 0 -> 2 | t = 88.04 s |
| vehicle position at the transition | PN -0.3, **PE -89.3 m** |
| logged position reset delta (`XKF4.OFN/OFE`) | **+0.13 / -0.05 m** |
| largest \|OFN\| over the whole flight | **0.17 m** |
| position after the transition (t = 93.84) | PN -0.2, PE -89.4 m |

The position does not move. A teleport to the origin would have shown as an
~89 m reset delta and an ~89 m step in `XKF1.PN/PE`; neither is present.

### What is not yet established

Which of the two possibilities holds: the reset is not taken on this edge, or it
is taken and `lastKnownPositionNE` already holds the current position (an
AID_NONE entry shorter than the 10 Hz `XKF4` logging interval would hide the
write). Distinguishing them needs one more instrumented run, and the
instrumentation has to be `::fprintf(stderr, ...)` rather than `GCS_SEND_TEXT` -
see the traps below.

Either way the review's stated consequence is refuted for this scenario, and the
suggested fix (write `lastKnownPositionNE` before setting AID_RELATIVE) should
not be applied on the strength of the review alone.

## Traps this cost, worth not repeating

- **`GCS_SEND_TEXT` from EKF probe code is lossy.** Three runs' worth of probe
  output was missing or misleading because statustexts were dropped around the
  source switch. `::fprintf(stderr, ...)` survives and lands in the autotest log.
  The dataflash (`XKF1.PN/PE`, `XKF4.OFN/OFE`, `XKF4.AID`) is better still.
- **`self.reboot_sitl()` means two SITL instances per run**, so early stderr
  lines can belong to the pre-reboot instance and read as if the transition
  happened at the origin. Correlate against the dataflash, not the console.
- **`fly_guided_move_local(100, 0, 8)` silently did not move the vehicle** in
  one run - "Reach distance (0.51)" with `endpos == startpos`. RC translation is
  cruder but cannot no-op silently.
- **Print both components.** A probe printing `stateStruct.position.x` alone
  read as "at the origin" while the vehicle was 89 m east.

## The other review findings, untested

Not examined here, and none of them depend on the BUG above:

- the PR silently enables `getHeightControlLimit()` on GPS loss, which AC_Avoid
  will use to command a vehicle down to ~20 m AGL with a 30 m rangefinder
- `!readyToUseGPS()` is a per-cycle flag, so under a sustained GPS rejection the
  edge fires and blocks the in-place glitch recovery
- the bit-identical velocity claim in the description cannot hold if
  `ResetVelocity()` zeroes the horizontal velocity on the transition
- the added test hovers at home, where the position question is invisible; the
  fly-out above is the fix for that regardless of the outcome
