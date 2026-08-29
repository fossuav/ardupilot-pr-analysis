# PR #32514 - Reset the EKF failsafe gate on a source-set change

Analysis archive for [ArduPilot/ardupilot#32514](https://github.com/ArduPilot/ardupilot/pull/32514).
Branch `ekf-check-source-reset` (andyp1per fork), base `master`. No logs
committed; the field numbers are from real throws.

## Status (one line)

Open, awaiting review. Four commits: the gate reset, a 12 s holdoff for the
EKF's aiding-mode transition, the EKFSourceSetFailsafe autotest, and
clearing a failsafe latched under the old set. Flown on the SmallFastDrone
4.7 branch on every throw since 2026-03; the 4.6 branch without it shows
the failure.

## The problem

ekf_check latches has_ever_passed once position is available. An
intentional switch to a source set with no position (THROW_SRC_INI on a
GPS vehicle, or the RC/Lua/MAVLink selector on a flow vehicle) then reads
as a loss of position and the failsafe fires within 1 s of the switch.

## The conclusion and why

Treat a source-set change as a new start for the gate. On a MambaH743v4
quad without the fix (log3/log4, not committed) the failsafe fired within
1 s of the throw-entry switch with SV=0.00 and SP=0.00: the filter was
healthy, only has_position had dropped. On a MicoAir743v2 quad on the 4.6
branch (log22) the same switch at 159.2 s produced "EKF variance: position
lost" at 160.2 s while disarmed, then "EKF3 core 0 unhealthy" at 202.9 s,
and the pilot waited 145 s before the first arm. With the reset, the
identical configuration on the 4.7 branch produced no failsafe on the next
session (drop session 2, log2), none on a flow vehicle with
THROW_SRC_INI=3, and none across seven throws in a later session.

## Key finding: protection resumes when a position set returns

The gate re-latches when the new set provides position, and it does. After
a throw that ran unaided through a heavy spin, THROW_SRC_SET restored the
GPS set at completion and the failsafe fired 3.4 s after disarm as the
diverged filter failed against the re-latched gate (MambaH743v4 quad,
2026-05-23 session, log1). That is the designed behaviour, and it was
harmless on the ground. The holdoff and the latched-failsafe clear in this
PR have not been exercised in flight.

Not this PR's problem, for anyone matching field reports: a Loiter to
AltHold demotion on an unchanged source set, where has_position dropped
because the terrain offset validity times out 5 s after the rangefinder
ceiling, is #33585's territory; has_ever_passed is not involved.

## What is here

```
32514/
  README.md          <- this file
```

No logs committed. The autotest BIN could be added under data/.

## Reproduce

```
git checkout ekf-check-source-reset
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.EKFSourceSetFailsafe
```

## Branches and people

- `ekf-check-source-reset` - the PR branch.
- Related: #32475 (THROW_SRC_INI/THROW_SRC_SET, which is what exposed this
  on GPS vehicles).
