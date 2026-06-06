# PR #33338 - Periodic height-only datum reset (prototype)

Draft/prototype: [ArduPilot/ardupilot#33338](https://github.com/ArduPilot/ardupilot/pull/33338).
Branch `pr-baro-drift-minimum-periodic-reset`.

This is the explored alternative to [#32768](https://github.com/ArduPilot/ardupilot/pull/32768).
The full analysis, plots and SITL data live in [`../32768/`](../32768/) - this is
the same investigation; read that first.

## What it is

#32768 ships an arm-only height-datum reset. This branch keeps a *periodic*
disarmed reset (continuous drift clearing) but makes it safe with a
`reset_velocity` flag on `resetHeightDatum`:

- periodic disarmed reset passes `reset_velocity=false` - re-datum height only,
  leave `velocity.z`, so the on-ground zero-velocity bias-learning signal is
  preserved;
- arm-time reset passes `reset_velocity=true` - full reset, clean takeoff.

It retains the ExternalNav source guard, logs `reset_velocity` in the RHGT
replay block (and applies it in Replay), and removes the convergence gate the
earlier periodic version needed.

## Outcome

The `reset_velocity` split works for what it targets - it preserves bias
learning (`../32768/plots/D_velocity_vs_bias.png`) and fixes the ExternalNav
corruption. But it does **not** make the periodic reset clean:

| build | RudderDisarmMidair |
|---|---|
| arm-only (#32768) | pass 3/3 |
| periodic, full reset | fail 3/3 |
| periodic, height-only (this PR) | fail 3/3 |

The periodic reset breaks `RudderDisarmMidair` (mid-air disarm/re-arm with a
displaced home) regardless of velocity handling: at the final touchdown the EKF
reports ~2.5 m altitude and the periodic reset only re-datums it ~1 s after the
landing disarm, too late for the RTL completion check. Arm-only never fires
those disarmed resets, so its datum stays consistent.

Conclusion: kept as a documented experiment. It shows the velocity/datum split
is sound for bias and vicon, but the periodic reset still has cross-subsystem
edge cases, so #32768 (arm-only) is the recommended approach.
