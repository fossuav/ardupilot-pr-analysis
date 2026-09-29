# PR #30980 - Copter: fix compassmot so that it works with the rate thread

Analysis archive for [ArduPilot/ardupilot#30980](https://github.com/ArduPilot/ardupilot/pull/30980).
Branch `pr-compassmot-fastrate` (andyp1per fork), base `master`, head
`eb73dccad2` (2026-09-29), two commits. All numbers below are SITL; the one
hardware case is rmackay9's report on the PR, no logs committed.

## Status (one line)

Open. CompassMot, the new CompassMotFastRate and MotorTest pass at
`eb73dccad2`; copter and heli build at each commit. The earlier head's
rate-thread-off regression, found by AP-Review and matching rmackay9's
hardware report, is fixed. No reported problem is left open.

## The problem

With `FSTRATE_ENABLE=1` on master, the compassmot calibration loop writes
the throttle passthrough while the rate thread writes its own output, so
the motors do not follow the calibration throttle. In SITL, CompassMot with
the rate thread on learns `COMPASS_MOT_X` 0.748 against an injected 10 and
fails. With the PR it passes (head `eb73dccad2`, 2026-09-29). The
master figure's commit was not recorded; re-run to pin it.

## The earlier head's bug (12fc294dfb)

At `12fc294dfb`, with the rate thread **off** (the default), nothing drove
the motors during compassmot: SITL learned `COMPASS_MOT_X` 0.000 against 10.
Found by AP-Review and confirmed in SITL, and it matches rmackay9's
2025-11-05 hardware report on a CubeOrangePlus (tier 1, an operator report).

## The conclusion and why

At `eb73dccad2`:

- The calibration loop calls `motors_output()` itself when
  `!using_rate_thread`, so the default path drives the motors as master did.
- `ap.compass_mot` is set on entry (the restart guard, as on master) and
  cleared at the end.
- `compassmot_output()` holds `output_min` while disarmed.
- The main thread skips `output_min` while the rate thread runs, so the two
  threads no longer both write the outputs.
- Compassmot and the motor test each refuse to start while the other runs.

The heli guard was folded into the first commit: after the squash, heli did
not build at that commit otherwise.

## Key findings

| Case | Head | COMPASS_MOT_X (injected 10) |
|---|---|---|
| master, `FSTRATE_ENABLE=1` | master (the PR's base) | 0.748, fails |
| PR, rate thread off (default) | `12fc294dfb` | 0.000, fails |
| PR, rate thread on and off | `eb73dccad2` (2026-09-29) | CompassMot and CompassMotFastRate pass |

New autotest CompassMotFastRate: `FSTRATE_ENABLE=1`, reboot, then the
CompassMot sequence.

## What is here

```
30980/
  README.md    <- this file
```

No logs committed.

## Reproduce

```
git checkout pr-compassmot-fastrate
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.CompassMot
Tools/autotest/autotest.py --no-configure test.Copter.CompassMotFastRate
Tools/autotest/autotest.py --no-configure test.Copter.MotorTest
```

For the master figure, run CompassMotFastRate's steps (`FSTRATE_ENABLE=1`,
reboot, CompassMot) on master.

## Branches and people

- `pr-compassmot-fastrate` - the PR branch (two commits).
- Author: @andyp1per. Hardware report: @rmackay9 (2025-11-05).
