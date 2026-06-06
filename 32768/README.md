# PR #32768 - Clear baro temperature drift on arming (ArduCopter / EKF3)

Analysis archive for [ArduPilot/ardupilot#32768](https://github.com/ArduPilot/ardupilot/pull/32768).
Everything here is from SITL (no real-flight data).

## Status (one line)

Shipped design is **reset the EKF height datum once, at arm**. The reviewer
suggestion to *also* reset periodically while disarmed (like Plane) was
implemented, tested, found to cause regressions, and removed. A height-only
variant of the periodic idea is preserved as a separate experiment, PR
[#33338](https://github.com/ArduPilot/ardupilot/pull/33338) (see `../33338/`).

## The problem

The barometer drifts with temperature while a copter sits disarmed, so the
reported height wanders off - metres by takeoff. The PR re-zeroes the height
reference at arm, just before flight, so the altitude is correct when it starts
being used.

## The conclusion and why

Arm-only is the right scope for Copter. `resetHeightDatum` is only valid on the
ground, with baro/GPS height, at a moment you are about to use the estimate -
arm satisfies all three. Running it repeatedly while disarmed fires it in states
it was never designed for, and that is where every problem came from.

The periodic reset, in the forms tried, caused:

1. **Height corruption with a non-baro height source** (GPSViconSwitching). The
   reset had no guard for ExternalNav/vicon; firing it there snapped reported
   height to the takeoff altitude on the ground. Plot B.
2. **Degraded GPS-denied takeoff estimate** (BaroDriftClearedAtArm, GPS-denied).
   The reset zeroes `velocity.z`, which on the ground is how the EKF learns its
   Z accel bias (zero-velocity fusion); repeatedly erasing it leaves a worse
   bias at arm that integrates into a post-arm altitude climb. Plots C and D.
3. **Disarmed replay-logging stress** (Replay) - CI-only evidence.
4. It only avoided slowing from-boot bias learning via a convergence gate +
   non-Plane interval, i.e. load-bearing complexity arm-only does not need.

Plane needs no change: it clears drift at arm (works baro-only) and gates its
periodic reset on a GPS fix, which confines it to the regime where it is
harmless. Details in `analysis.md`.

## Key finding: it is the velocity reset, not the datum

Paul Riseborough's review point - a datum reset should redefine the zero-point
without touching vertical velocity - is the crux. A one-variable A/B (Plot D)
confirms it: with the periodic reset firing during GPS-denied bias learning,
zeroing `velocity.z` plateaus the learned bias at ~0.56, while re-datuming
height only reaches the true 0.70. The height/baro re-datum is innocent;
`resetHeightDatum` does not touch the covariance.

That motivated #33338 (a `reset_velocity` flag: periodic = height-only, arm =
full). It fixes findings 1 and 2 and drops the gate - but `RudderDisarmMidair`
still fails on the periodic reset regardless of velocity handling (arm-only
3/3 pass; both periodic variants 3/3 fail), so arm-only remains the
recommendation. See `../33338/`.

## Plots

| | |
|---|---|
| ![A](plots/A_arm_reset.png) | **A** - arm-time reset clears ~9 m drift in one sample; removes the phantom -0.3 m/s, no kick |
| ![B](plots/B_gpsvicon.png) | **B** - periodic reset corrupts height (jumps to ~9.5 m) with vicon as the height source; arm-only stays at 0 |
| ![C](plots/C_gps_denied_postarm.png) | **C** - GPS-denied: periodic post-arm altitude climbs; arm-only stays flat |
| ![D](plots/D_velocity_vs_bias.png) | **D** - zeroing velocity.z (red) interrupts bias learning; height-only (green) reaches the true bias |

## What is here

```
32768/
  README.md          <- this file
  analysis.md        <- full write-up (posted as the PR #32768 analysis comment)
  design-notes.md    <- earlier design notes on the reset mechanics
  plots/             <- A/B/C/D PNGs + make_plots.py (regenerates them from data/)
  data/
    arm-only/        <- SITL BINs from the arm-only build (this PR's design)
      barodrift_arm.BIN     (Plots A, C)
      gpsvicon_clean.BIN    (Plot B, clean trace)
    periodic/        <- SITL BINs from the periodic-reset build(s)
      gpsvicon_FAIL.BIN     (Plot B, corrupted trace)
      guard_barodrift.BIN   (Plot C, periodic+guard GPS-denied)
      fullreset_bias.BIN    (Plot D, zero velocity.z)
      heightonly_bias.BIN   (Plot D, leave velocity.z)
```

All BINs are SITL (ArduCopter V4.8.0-dev, CMAC default home; each carries
hundreds of `SIM_*` parameters).

## Reproduce

Plots, from this directory:

```
python3 plots/make_plots.py
```

The SITL behaviours, in an ardupilot checkout:

```
# arm-only branch (this PR) - these pass:
git checkout pr-baro-drift-minimum
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.BaroDriftClearedAtArm
Tools/autotest/autotest.py --no-configure test.Copter.GPSViconSwitching

# periodic-reset branch - reproduces the problems (run GPSViconSwitching a few times):
git checkout pr-baro-drift-minimum-periodic-reset
./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.RudderDisarmMidair   # fails on periodic
```

## Branches and people

- `pr-baro-drift-minimum` - the PR #32768 branch (arm-only, shipped).
- `pr-baro-drift-minimum-periodic-reset` - PR #33338 (height-only periodic experiment).
- Reviewers: @tridge (suggested mimicking Plane's periodic reset), @rmackay9,
  Paul Riseborough (EKF author; "less is more", datum reset should not touch
  velocity/covariance - which the velocity-reset finding confirms).
