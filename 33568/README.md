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

## The height control limit does not command a descent either (2026-09-12)

The review's third finding: because `getHeightControlLimit()` gates on the same
`AID_RELATIVE`, the fallback silently switches on the EKF height limit, and
"a copter that loses GPS at 100 m will now be commanded down to ~20 m AGL".

Measured. LOITER at 39.4 m, `SIM_TERRAIN 0` so `terrain_srtm_alt_valid` cannot
suppress the limit, analog range finder at its 40 m default, so the limit would
be `40*0.7 - 1 = 27 m` - twelve metres below the vehicle. Switch to the flow
source set and watch for 30 s:

    altitude before 39.4 m
    t+05s 39.5   t+10s 39.5   t+15s 39.5
    t+20s 39.5   t+25s 39.5   t+30s 39.5
    net change +0.1 m

**No descent.** The mode change to AID_RELATIVE is confirmed in the same run.

The descent path itself is real: Copter calls the four-argument
`adjust_velocity_z()` (`ArduCopter/mode.cpp:993`), and that overload does fold a
non-zero `backup_speed_cms` into the climb rate
(`AC_Avoid.cpp:396-405`). So something upstream is not publishing the limit.

The most likely gate is `flowDataValid` in `getHeightControlLimit()`
(`AP_NavEKF3_Outputs.cpp:94`): at 39.5 m with a 40 m range finder the flow
measurements are at or past the edge of validity, and that is the same regime
the review's own "loses GPS at 100 m" scenario assumes. If so the finding is
partly self-cancelling - the limit only engages where flow is still valid, which
is where the vehicle is low enough not to be driven down far. **Not confirmed**,
and confirming it needs the limit itself in the dataflash rather than a console
probe.

## Instrumentation: console probes are not trustworthy here

Recorded because it cost several runs and produced two wrong intermediate
conclusions.

`GCS_SEND_TEXT` is dropped under load. Switching to `::fprintf(stderr, ...)`
fixed the loss but not the ordering: SITL's stderr and the harness's stdout are
separate streams merged into one capture, and the test reboots SITL partway, so
a line printed by the pre-reboot instance can appear *after* a harness line from
the post-reboot one. That made a transition that the dataflash places at
PE = -89.3 m read as happening at the origin.

Anything that has to be correlated with vehicle state belongs in the dataflash.
`XKF1.PN/PE`, `XKF4.OFN/OFE` and `XKF4.AID` were right every time and disagreed
with the console every time.

So the open question from the section above - whether the reset is skipped on
this edge, or taken with `lastKnownPositionNE` already current - is still open,
and the way to settle it is a temporary log field, not another print.

## Both questions answered with a dataflash probe (2026-09-12)

A temporary `PRBE` message written from `Log_Write()` carrying, per core:
`lastKnownPositionNE`, `stateStruct.position`, `PV_AidingMode`, `flowDataValid`,
`useVelXYSource(OPTFLOW)`, `terrain_srtm_alt_valid`, and the return and value of
`getHeightControlLimit()`. That settled in two runs what four console-probe runs
could not.

### The teleport is impossible, not merely absent

`moveEKFOrigin()` (`AP_NavEKF3_core.cpp:2273`) moves `EKF_origin` onto the
vehicle **at 1 Hz** whenever there is a valid origin and GPS is in use, and
subtracts the delta from `stateStruct.position`, `outputDataNew`,
`outputDataDelayed` and every entry of `storedOutput`. The comment says it
plainly: "move the EKF origin to the current position at 1Hz. The public_origin
doesn't move."

So `stateStruct.position` is held near zero by construction while on GPS. The
absolute position is carried by `public_origin.get_distance_NE(EKF_origin)`,
which `getPosNE()` adds back (`AP_NavEKF3_Outputs.cpp:263`) - which is why
`XKF1.PN/PE` reads -90.6 m while the state itself reads -0.0.

Measured, vehicle 90.5 m from the origin at the fallback:

| t | XKF1 PN,PE | stateStruct PN,PE |
|---|---|---|
| 70.0 | -0.1, -47.6 | -0.0, -0.1 |
| 80.0 | -0.2, -90.6 | -0.0, -0.0 |
| 90.0 | -0.1, -90.6 |  0.0,  0.0 |

`ResetPosition()` assigning `stateStruct.position = lastKnownPositionNE` is
therefore a move between two near-zero numbers. The review's "a vehicle 1 km
downrange jumps 1 km to the EKF origin" requires the state to hold the full
kilometre; it cannot, because the precondition for this edge is that the vehicle
*was* navigating on GPS, which is exactly when the origin is being re-based.
**The finding is refuted at the root and no fix is needed.**

### The height limit finding is real, and worse than stated

The EKF publishes the limit exactly as the review says. At 39.4 m with a 40 m
range finder: `AID=2 FDV=1 VXY=1 SRTM=0 HOK=1 HCL=27.0`. My earlier guess that
`flowDataValid` was gating it was **wrong** - `FDV=1`.

The reason a hovering vehicle is not driven down is `AC_Avoid.cpp:418-421`:

    // do not adjust climb_rate if level
    if (is_zero(climb_rate_cms)) {
        return;
    }

`adjust_velocity_z()` exits before it looks at the limit when the climb demand
is zero. So the consequence needs a pilot input - and then it is severe:

| | altitude |
|---|---|
| on GPS, full-up throttle 8 s | 39.5 -> **50.5 m (+11.0)** |
| on flow, limit 27 m, **same** full-up throttle | 50.5 -> **32.3 m (-18.1)** |

The vehicle descends 18 m while the pilot holds full climb. Not "it will be
commanded down to ~20 m" but "the next climb input becomes a descent", which is
a worse failure to meet in the air and is not mentioned in the PR description.

This is the finding on this PR that needs addressing.
